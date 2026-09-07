import logging
import time

from django.db import connection

logger = logging.getLogger(__name__)


class RequestTimingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.perf_counter()

        sql_total = 0.0
        sql_count = 0

        def sql_wrapper(execute, sql, params, many, context):
            nonlocal sql_total, sql_count

            query_start = time.perf_counter()

            try:
                return execute(sql, params, many, context)
            finally:
                sql_total += time.perf_counter() - query_start
                sql_count += 1

        with connection.execute_wrapper(sql_wrapper):
            response = self.get_response(request)

        django_total = time.perf_counter() - start

        django_ms = django_total * 1000
        sql_ms = sql_total * 1000

        response["Server-Timing"] = (
            f"django;dur={django_ms:.2f},"
            f"sql;dur={sql_ms:.2f}"
        )

        logger.info(
            "REQUEST_TIMING method=%s path=%s status=%s "
            "django=%.2fms sql=%.2fms queries=%d",
            request.method,
            request.path,
            response.status_code,
            django_ms,
            sql_ms,
            sql_count,
        )

        return response
