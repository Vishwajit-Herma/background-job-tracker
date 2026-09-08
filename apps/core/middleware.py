import logging
import time

from django.db import connection

logger = logging.getLogger(__name__)


class RequestTimingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Skip timing instrumentation for health checks and readiness pings
        if request.path.startswith(("/health", "/alive", "/ready")) or request.path.rstrip(
            "/"
        ).endswith("health"):
            return self.get_response(request)

        start = time.perf_counter()
        sql_total = 0.0
        sql_count = 0
        queries_detail = []
        is_resolve_request = request.path.endswith("/resolve/") and request.method == "POST"

        def sql_wrapper(execute, sql, params, many, context):
            nonlocal sql_total, sql_count
            query_start = time.perf_counter()

            try:
                return execute(sql, params, many, context)
            finally:
                q_dur = time.perf_counter() - query_start
                sql_total += q_dur
                sql_count += 1

                if is_resolve_request:
                    dur_ms = q_dur * 1000
                    sql_upper = sql.upper()
                    if "AUTHTOKEN_TOKEN" in sql_upper or "USERS_USER" in sql_upper:
                        purpose = "Auth / User lookup"
                    elif "FOR UPDATE" in sql_upper:
                        purpose = "SELECT FOR UPDATE incident"
                    elif "UPDATE" in sql_upper and "INCIDENTS_INCIDENT" in sql_upper:
                        purpose = "UPDATE incident status & metadata"
                    elif "INSERT INTO" in sql_upper and "INCIDENTS_INCIDENTEVENT" in sql_upper:
                        purpose = "INSERT IncidentEvent (MANUALLY_RESOLVED)"
                    elif "FROM \"INCIDENTS_INCIDENT\"" in sql_upper or "FROM INCIDENTS_INCIDENT" in sql_upper:
                        if "PROJECTS_PROJECT" in sql_upper and "TEAMS_TEAMMEMBER" in sql_upper:
                            purpose = "Access check incident + project + team"
                        elif "ASSIGNED_TO" in sql_upper or "ALERT_RULE" in sql_upper:
                            purpose = "Fetch incident with preloaded relations for response"
                        else:
                            purpose = "Fetch incident"
                    elif "SESSION" in sql_upper:
                        purpose = "Session lookup / save"
                    else:
                        purpose = f"SQL query ({sql[:40]}...)"

                    queries_detail.append((sql_count, dur_ms, purpose))

        with connection.execute_wrapper(sql_wrapper):
            response = self.get_response(request)

        django_total = time.perf_counter() - start
        django_ms = django_total * 1000
        sql_ms = sql_total * 1000

        if is_resolve_request and hasattr(request, "_resolve_perf"):
            p = request._resolve_perf
            check_access_ms = p.get("check_access_ms", 0.0)
            service_total_ms = p.get("service_total_ms", 0.0)
            select_for_update_ms = p.get("select_for_update_ms", 0.0)
            update_ms = p.get("update_ms", 0.0)
            event_insert_ms = p.get("event_insert_ms", 0.0)
            commit_on_commit_ms = p.get("commit_on_commit_ms", 0.0)
            response_fetch_ms = p.get("response_fetch_ms", 0.0)
            serializer_ms = p.get("serializer_ms", 0.0)
            response_create_ms = p.get("response_create_ms", 0.0)
            finalize_ms = p.get("finalize_ms", 0.0)
            render_ms = p.get("render_ms", 0.0)
            action_total_ms = p.get("action_total_ms", 0.0)

            measured_inside_view = (
                check_access_ms
                + service_total_ms
                + response_fetch_ms
                + serializer_ms
                + response_create_ms
            )
            other_request_ms = django_ms - (measured_inside_view + finalize_ms + render_ms)

            logger.info(
                "RESOLVE_DETAILED_TIMING "
                "check_access_ms=%.2fms "
                "service_total_ms=%.2fms "
                "select_for_update_ms=%.2fms "
                "update_ms=%.2fms "
                "event_insert_ms=%.2fms "
                "commit_on_commit_ms=%.2fms "
                "response_fetch_ms=%.2fms "
                "serializer_ms=%.2fms "
                "finalize_ms=%.2fms "
                "render_ms=%.2fms "
                "other_request_ms=%.2fms "
                "total_sql_ms=%.2fms "
                "django_total_ms=%.2fms "
                "action_total_ms=%.2fms",
                check_access_ms,
                service_total_ms,
                select_for_update_ms,
                update_ms,
                event_insert_ms,
                commit_on_commit_ms,
                response_fetch_ms,
                serializer_ms,
                finalize_ms,
                render_ms,
                other_request_ms,
                sql_ms,
                django_ms,
                action_total_ms,
            )

            for num, dur_ms, purpose in queries_detail:
                logger.info(
                    "RESOLVE_SQL query_num=%d duration_ms=%.2fms purpose='%s'",
                    num,
                    dur_ms,
                    purpose,
                )

        # Node.js v24's llhttp HTTP parser rejects the Server-Timing header
        # when it proxies responses through the Next.js dev server, raising
        # HPE_INVALID_HEADER_TOKEN.  Skip the header on API responses (which
        # are always proxied); it is still logged below for server-side
        # observability.  Non-API paths (admin, debug toolbar) are unaffected.
        if not request.path.startswith("/api/"):
            response["Server-Timing"] = f"django;dur={django_ms:.2f},sql;dur={sql_ms:.2f}"

        logger.info(
            "REQUEST_TIMING method=%s path=%s status=%s django=%.2fms sql=%.2fms queries=%d",
            request.method,
            request.path,
            response.status_code,
            django_ms,
            sql_ms,
            sql_count,
        )

        return response
