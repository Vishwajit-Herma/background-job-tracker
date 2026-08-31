import json
from datetime import timedelta
import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from django.test import override_settings

from apps.alerts.models import AlertRule
from apps.incidents.models import (
    Incident,
    IncidentPostmortem,
    IncidentRunbookExecution,
    PostmortemActionItem,
    Runbook,
)
from apps.incidents.services import (
    build_incident_knowledge,
    get_reliability_report,
)
from apps.jobs.models import Job
from apps.projects.models import Project
from apps.teams.models import Team, TeamMember

pytestmark = pytest.mark.django_db


@pytest.fixture
def setup_data():
    User = get_user_model()
    user = User.objects.create(email="admin_rl@example.com")
    user.set_password("password")
    user.save()

    team = Team.objects.create(name="RL Team", slug="rl-team", owner=user)
    admin_member, _ = TeamMember.objects.get_or_create(
        team=team, user=user, defaults={"role": "admin", "is_active": True}
    )

    # Regular member
    member_user = User.objects.create(email="member_rl@example.com")
    reg_member = TeamMember.objects.create(
        team=team, user=member_user, role="member", is_active=True
    )

    # Project and Job
    project = Project.objects.create(team=team, name="RL Project")
    job1 = Job.objects.create(project=project, name="Job 1", task_identifier="task_1")
    job2 = Job.objects.create(project=project, name="Job 2", task_identifier="task_2")

    # Another project for cross-tenant tests
    other_team = Team.objects.create(name="Other Team", slug="other-team", owner=user)
    other_project = Project.objects.create(team=other_team, name="Other Project")
    other_job = Job.objects.create(
        project=other_project, name="Other Job", task_identifier="task_other"
    )

    return {
        "user": user,
        "admin_member": admin_member,
        "member_user": member_user,
        "reg_member": reg_member,
        "team": team,
        "project": project,
        "job1": job1,
        "job2": job2,
        "other_project": other_project,
        "other_job": other_job,
    }


@pytest.fixture
def alert_rule(setup_data):
    return AlertRule.objects.create(
        project=setup_data["project"],
        metric=AlertRule.MetricType.STALLED_EXECUTION,
        threshold=10,
    )


@pytest.fixture
def incident(setup_data, alert_rule):
    return Incident.objects.create(
        project=setup_data["project"],
        job=setup_data["job1"],
        alert_rule=alert_rule,
        severity=Incident.Severity.CRITICAL,
        status=Incident.Status.OPEN,
    )


@pytest.fixture
def runbook(setup_data):
    return Runbook.objects.create(
        project=setup_data["project"],
        name="Restart Worker",
        trigger_type=Runbook.TriggerType.STALLED_EXECUTION,
        created_by=setup_data["user"],
        steps=[
            {"id": "step_1", "desc": "Restart celery worker"},
            {"id": "step_2", "desc": "Check queue latency"},
        ],
    )


class TestRunbookAPI:
    def test_create_runbook_as_admin(self, api_client, setup_data):
        api_client.force_authenticate(user=setup_data["user"])
        url = reverse("api:incidents:runbooks-list")

        data = {
            "project": setup_data["project"].id,
            "name": "General Stalled Worker Runbook",
            "trigger_type": "STALLED_EXECUTION",
            "steps": [{"id": "s1", "text": "restart"}],
        }

        response = api_client.post(url, data, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert Runbook.objects.filter(name="General Stalled Worker Runbook").exists()

    def test_create_runbook_as_member_fails(self, api_client, setup_data):
        api_client.force_authenticate(user=setup_data["member_user"])
        url = reverse("api:incidents:runbooks-list")

        data = {
            "project": setup_data["project"].id,
            "name": "Member Runbook",
            "trigger_type": "STALLED_EXECUTION",
            "steps": [{"id": "s1", "text": "restart"}],
        }

        response = api_client.post(url, data, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_execute_runbook_success(self, api_client, setup_data, incident, runbook):
        api_client.force_authenticate(user=setup_data["user"])
        url = reverse("api:incidents:incidents-execute-runbook", kwargs={"pk": incident.id})

        response = api_client.post(url, {"runbook_id": runbook.id}, format="json")
        assert response.status_code == status.HTTP_201_CREATED

        data = response.data.get("data", response.data)
        execution_id = data["id"]
        execution = IncidentRunbookExecution.objects.get(id=execution_id)
        assert execution.status == "IN_PROGRESS"
        assert incident.events.filter(event_type="RUNBOOK_STARTED").exists()

    def test_execute_inactive_runbook_fails(self, api_client, setup_data, incident, runbook):
        runbook.is_active = False
        runbook.save()

        api_client.force_authenticate(user=setup_data["user"])
        url = reverse("api:incidents:incidents-execute-runbook", kwargs={"pk": incident.id})

        response = api_client.post(url, {"runbook_id": runbook.id}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "not active" in str(response.data.get("errors"))

    def test_execute_runbook_from_another_project_fails(self, api_client, setup_data, incident):
        other_runbook = Runbook.objects.create(
            project=setup_data["other_project"],
            name="Other Project Runbook",
            created_by=setup_data["user"],
            steps=[{"id": "step_1"}],
        )

        api_client.force_authenticate(user=setup_data["user"])
        url = reverse("api:incidents:incidents-execute-runbook", kwargs={"pk": incident.id})

        response = api_client.post(url, {"runbook_id": other_runbook.id}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "different project" in str(response.data.get("errors"))

    def test_execute_job_specific_runbook_on_different_job_fails(
        self, api_client, setup_data, incident
    ):
        # Runbook is specific to job2, while incident is on job1
        job2_runbook = Runbook.objects.create(
            project=setup_data["project"],
            job=setup_data["job2"],
            name="Job 2 Runbook",
            created_by=setup_data["user"],
            steps=[{"id": "step_1"}],
        )

        api_client.force_authenticate(user=setup_data["user"])
        url = reverse("api:incidents:incidents-execute-runbook", kwargs={"pk": incident.id})

        response = api_client.post(url, {"runbook_id": job2_runbook.id}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "different job" in str(response.data.get("errors"))

    def test_runbook_execution_status_lifecycle_and_terminal_protection(
        self, api_client, setup_data, incident, runbook
    ):
        api_client.force_authenticate(user=setup_data["user"])
        execution = IncidentRunbookExecution.objects.create(
            incident=incident, runbook=runbook, status="IN_PROGRESS"
        )

        url = reverse(
            "api:incidents:incidents-runbook-execution-status",
            kwargs={"pk": incident.id, "execution_id": execution.id},
        )

        # 1. IN_PROGRESS -> COMPLETED (valid)
        res = api_client.post(url, {"status": "COMPLETED"}, format="json")
        assert res.status_code == status.HTTP_200_OK
        execution.refresh_from_db()
        assert execution.status == "COMPLETED"
        assert execution.completed_at is not None
        assert incident.events.filter(event_type="RUNBOOK_COMPLETED").exists()

        # 2. COMPLETED -> IN_PROGRESS (invalid: terminal state)
        res_invalid = api_client.post(url, {"status": "IN_PROGRESS"}, format="json")
        assert res_invalid.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid runbook execution status transition" in str(res_invalid.data.get("errors"))

    def test_runbook_execution_status_cancellation(self, api_client, setup_data, incident, runbook):
        api_client.force_authenticate(user=setup_data["user"])
        execution = IncidentRunbookExecution.objects.create(
            incident=incident, runbook=runbook, status="IN_PROGRESS"
        )

        url = reverse(
            "api:incidents:incidents-runbook-execution-status",
            kwargs={"pk": incident.id, "execution_id": execution.id},
        )

        # IN_PROGRESS -> CANCELLED
        res = api_client.post(url, {"status": "CANCELLED"}, format="json")
        assert res.status_code == status.HTTP_200_OK
        execution.refresh_from_db()
        assert execution.status == "CANCELLED"
        assert execution.completed_at is not None
        assert incident.events.filter(event_type="RUNBOOK_CANCELLED").exists()

    def test_runbook_execution_status_cross_incident_mismatch_fails(
        self, api_client, setup_data, incident, runbook
    ):
        incident2 = Incident.objects.create(
            project=setup_data["project"], status=Incident.Status.OPEN
        )
        execution = IncidentRunbookExecution.objects.create(
            incident=incident, runbook=runbook, status="IN_PROGRESS"
        )

        api_client.force_authenticate(user=setup_data["user"])
        # Call with incident2 in URL while execution belongs to incident1
        url = reverse(
            "api:incidents:incidents-runbook-execution-status",
            kwargs={"pk": incident2.id, "execution_id": execution.id},
        )
        res = api_client.post(url, {"status": "COMPLETED"}, format="json")
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "does not belong" in str(res.data.get("errors"))

    def test_transition_runbook_step_strict_lifecycle(
        self, api_client, setup_data, incident, runbook
    ):
        api_client.force_authenticate(user=setup_data["user"])
        execution = IncidentRunbookExecution.objects.create(
            incident=incident, runbook=runbook, status="IN_PROGRESS"
        )

        url = reverse("api:incidents:incidents-transition-step", kwargs={"pk": incident.id})

        # 1. PENDING -> IN_PROGRESS (valid)
        res1 = api_client.post(
            url,
            {
                "execution_id": execution.id,
                "step_id": "step_1",
                "from_state": "PENDING",
                "to_state": "IN_PROGRESS",
            },
            format="json",
        )
        assert res1.status_code == status.HTTP_200_OK

        # 2. IN_PROGRESS -> COMPLETED (valid)
        res2 = api_client.post(
            url,
            {
                "execution_id": execution.id,
                "step_id": "step_1",
                "from_state": "IN_PROGRESS",
                "to_state": "COMPLETED",
            },
            format="json",
        )
        assert res2.status_code == status.HTTP_200_OK

        # 3. COMPLETED -> PENDING (invalid transition)
        res3 = api_client.post(
            url,
            {
                "execution_id": execution.id,
                "step_id": "step_1",
                "from_state": "COMPLETED",
                "to_state": "PENDING",
            },
            format="json",
        )
        assert res3.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid step state transition" in str(res3.data.get("errors"))

        # 4. PENDING -> SKIPPED (valid for step_2)
        res4 = api_client.post(
            url,
            {
                "execution_id": execution.id,
                "step_id": "step_2",
                "from_state": "PENDING",
                "to_state": "SKIPPED",
            },
            format="json",
        )
        assert res4.status_code == status.HTTP_200_OK

        # 5. SKIPPED -> IN_PROGRESS (invalid transition from terminal SKIPPED)
        res5 = api_client.post(
            url,
            {
                "execution_id": execution.id,
                "step_id": "step_2",
                "from_state": "SKIPPED",
                "to_state": "IN_PROGRESS",
            },
            format="json",
        )
        assert res5.status_code == status.HTTP_400_BAD_REQUEST

    def test_transition_step_terminal_execution_status_fails(
        self, api_client, setup_data, incident, runbook
    ):
        api_client.force_authenticate(user=setup_data["user"])

        execution = IncidentRunbookExecution.objects.create(
            incident=incident, runbook=runbook, status="COMPLETED"
        )
        url = reverse("api:incidents:incidents-transition-step", kwargs={"pk": incident.id})

        # Transition step when execution is COMPLETED
        res_completed = api_client.post(
            url,
            {
                "execution_id": execution.id,
                "step_id": "step_1",
                "from_state": "PENDING",
                "to_state": "IN_PROGRESS",
            },
            format="json",
        )
        assert res_completed.status_code == status.HTTP_400_BAD_REQUEST
        assert "Cannot transition step" in str(res_completed.data.get("errors"))

        # Transition step when execution is CANCELLED
        execution.status = "CANCELLED"
        execution.save()
        res_cancelled = api_client.post(
            url,
            {
                "execution_id": execution.id,
                "step_id": "step_1",
                "from_state": "PENDING",
                "to_state": "IN_PROGRESS",
            },
            format="json",
        )
        assert res_cancelled.status_code == status.HTTP_400_BAD_REQUEST
        assert "Cannot transition step" in str(res_cancelled.data.get("errors"))

    def test_transition_step_invalid_incident_fails(self, api_client, setup_data, runbook):
        api_client.force_authenticate(user=setup_data["user"])

        incident1 = Incident.objects.create(
            project=setup_data["project"], status=Incident.Status.OPEN
        )
        incident2 = Incident.objects.create(
            project=setup_data["project"], status=Incident.Status.OPEN
        )

        execution = IncidentRunbookExecution.objects.create(
            incident=incident1, runbook=runbook, status="IN_PROGRESS"
        )

        url = reverse("api:incidents:incidents-transition-step", kwargs={"pk": incident2.id})
        data = {
            "execution_id": execution.id,
            "step_id": "step_1",
            "from_state": "PENDING",
            "to_state": "IN_PROGRESS",
        }

        response = api_client.post(url, data, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "does not belong" in str(response.data.get("errors"))

    def test_transition_step_nonexistent_step_id_fails(
        self, api_client, setup_data, incident, runbook
    ):
        api_client.force_authenticate(user=setup_data["user"])
        execution = IncidentRunbookExecution.objects.create(
            incident=incident, runbook=runbook, status="IN_PROGRESS"
        )

        url = reverse("api:incidents:incidents-transition-step", kwargs={"pk": incident.id})
        data = {
            "execution_id": execution.id,
            "step_id": "nonexistent_step_xyz",
            "from_state": "PENDING",
            "to_state": "IN_PROGRESS",
        }

        response = api_client.post(url, data, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "does not exist in runbook" in str(response.data.get("errors"))

    def test_runbook_delete_with_executions_deactivates_softly(
        self, api_client, setup_data, incident, runbook
    ):
        api_client.force_authenticate(user=setup_data["user"])
        IncidentRunbookExecution.objects.create(
            incident=incident, runbook=runbook, status="IN_PROGRESS"
        )

        url = reverse("api:incidents:runbooks-detail", kwargs={"pk": runbook.id})
        response = api_client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT

        runbook.refresh_from_db()
        assert runbook.is_active is False

    def test_runbook_delete_without_executions_deletes_physically(
        self, api_client, setup_data, runbook
    ):
        api_client.force_authenticate(user=setup_data["user"])
        url = reverse("api:incidents:runbooks-detail", kwargs={"pk": runbook.id})
        response = api_client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT

        assert not Runbook.objects.filter(id=runbook.id).exists()

    def test_recommended_runbooks_priority_and_metadata(self, api_client, setup_data, incident):
        # 1. Exact job + exact trigger
        rb1 = Runbook.objects.create(
            project=setup_data["project"],
            job=setup_data["job1"],
            trigger_type=Runbook.TriggerType.STALLED_EXECUTION,
            name="Exact Job & Trigger",
            created_by=setup_data["user"],
        )
        # 2. Exact job + general trigger
        rb2 = Runbook.objects.create(
            project=setup_data["project"],
            job=setup_data["job1"],
            trigger_type=None,
            name="Exact Job General Trigger",
            created_by=setup_data["user"],
        )
        # 3. Project wide + exact trigger
        rb3 = Runbook.objects.create(
            project=setup_data["project"],
            job=None,
            trigger_type=Runbook.TriggerType.STALLED_EXECUTION,
            name="Project Exact Trigger",
            created_by=setup_data["user"],
        )
        # 4. Project wide + general trigger
        rb4 = Runbook.objects.create(
            project=setup_data["project"],
            job=None,
            trigger_type=None,
            name="Project General Trigger",
            created_by=setup_data["user"],
        )
        # 5. Inactive runbook (should be excluded)
        Runbook.objects.create(
            project=setup_data["project"],
            job=setup_data["job1"],
            trigger_type=Runbook.TriggerType.STALLED_EXECUTION,
            name="Inactive Runbook",
            is_active=False,
            created_by=setup_data["user"],
        )

        api_client.force_authenticate(user=setup_data["user"])
        url = reverse("api:incidents:incidents-recommended-runbooks", kwargs={"pk": incident.id})
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK

        res_data = response.data.get("data", response.data)
        ids = [item["id"] for item in res_data]
        assert ids == [rb1.id, rb2.id, rb3.id, rb4.id]
        assert res_data[0]["match_reason"] == "EXACT_JOB_AND_TRIGGER"
        assert res_data[1]["match_reason"] == "EXACT_JOB_GENERAL_TRIGGER"
        assert res_data[2]["match_reason"] == "PROJECT_EXACT_TRIGGER"
        assert res_data[3]["match_reason"] == "PROJECT_GENERAL_TRIGGER"


class TestPostmortemAPI:
    def test_save_postmortem_draft(self, api_client, setup_data, incident):
        api_client.force_authenticate(user=setup_data["user"])
        url = reverse("api:incidents:incidents-postmortem", kwargs={"pk": incident.id})

        data = {
            "summary": "Worker ran out of memory, killing queue.",
            "impact_summary": "500 jobs stalled for 15 minutes.",
            "probable_cause": "OOM in celery worker process.",
            "confirmed_root_cause": "Memory leak in image processing task.",
            "resolution": "Increased worker memory limit and patched leak.",
            "contributing_factors": ["High traffic spike", "Unbounded buffer size"],
            "timeline": [{"time": "12:00", "event": "crash"}],
            "what_went_well": "Incident detected quickly.",
            "what_went_wrong": "Runbook step was initially missing.",
        }

        response = api_client.post(url, data, format="json")
        assert response.status_code == status.HTTP_200_OK

        postmortem = IncidentPostmortem.objects.get(incident=incident)
        assert postmortem.status == IncidentPostmortem.Status.PENDING
        assert postmortem.confirmed_root_cause == "Memory leak in image processing task."
        assert postmortem.reviewed_by is None
        assert postmortem.reviewed_at is None

    def test_postmortem_explicit_lifecycle_endpoints(self, api_client, setup_data, incident):
        api_client.force_authenticate(user=setup_data["user"])

        # 1. Save draft in PENDING
        postmortem_url = reverse("api:incidents:incidents-postmortem", kwargs={"pk": incident.id})
        api_client.post(postmortem_url, {"summary": "Initial draft"}, format="json")

        # 2. Cannot complete directly from PENDING
        complete_url = reverse(
            "api:incidents:incidents-postmortem-complete", kwargs={"pk": incident.id}
        )
        res_bad_comp = api_client.post(complete_url, format="json")
        assert res_bad_comp.status_code == status.HTTP_400_BAD_REQUEST
        assert "must be in IN_REVIEW status" in str(res_bad_comp.data.get("errors"))

        # 3. Submit for review: PENDING -> IN_REVIEW
        submit_url = reverse(
            "api:incidents:incidents-postmortem-submit-review", kwargs={"pk": incident.id}
        )
        res_sub = api_client.post(submit_url, format="json")
        assert res_sub.status_code == status.HTTP_200_OK

        postmortem = IncidentPostmortem.objects.get(incident=incident)
        assert postmortem.status == IncidentPostmortem.Status.IN_REVIEW
        assert postmortem.reviewed_by == setup_data["user"]
        assert postmortem.reviewed_at is not None
        initial_reviewed_at = postmortem.reviewed_at

        # 4. Ordinary edit in IN_REVIEW should NOT overwrite reviewed_at
        api_client.post(postmortem_url, {"summary": "Refined summary"}, format="json")
        postmortem.refresh_from_db()
        assert postmortem.reviewed_at == initial_reviewed_at

        # 5. Complete review: IN_REVIEW -> COMPLETED
        res_comp = api_client.post(complete_url, format="json")
        assert res_comp.status_code == status.HTTP_200_OK

        postmortem.refresh_from_db()
        assert postmortem.status == IncidentPostmortem.Status.COMPLETED

        # 6. Edits on COMPLETED postmortem are blocked (terminal state)
        res_edit_comp = api_client.post(postmortem_url, {"summary": "Illegal edit"}, format="json")
        assert res_edit_comp.status_code == status.HTTP_400_BAD_REQUEST
        assert "completed and cannot be modified" in str(res_edit_comp.data.get("errors"))

    def test_postmortem_complete_requires_admin_rbac(self, api_client, setup_data, incident):
        # 1. Member creates & submits postmortem
        api_client.force_authenticate(user=setup_data["member_user"])
        postmortem_url = reverse("api:incidents:incidents-postmortem", kwargs={"pk": incident.id})
        submit_url = reverse(
            "api:incidents:incidents-postmortem-submit-review", kwargs={"pk": incident.id}
        )
        complete_url = reverse(
            "api:incidents:incidents-postmortem-complete", kwargs={"pk": incident.id}
        )

        api_client.post(postmortem_url, {"summary": "Member draft"}, format="json")
        res_sub = api_client.post(submit_url, format="json")
        assert res_sub.status_code == status.HTTP_200_OK

        # 2. Member trying to complete review -> 403 Forbidden
        res_member_complete = api_client.post(complete_url, format="json")
        assert res_member_complete.status_code == status.HTTP_403_FORBIDDEN

        # 3. Admin completing review -> 200 OK
        api_client.force_authenticate(user=setup_data["user"])
        res_admin_complete = api_client.post(complete_url, format="json")
        assert res_admin_complete.status_code == status.HTTP_200_OK

    def test_submit_blank_postmortem_fails(self, api_client, setup_data, incident):
        api_client.force_authenticate(user=setup_data["user"])
        submit_url = reverse(
            "api:incidents:incidents-postmortem-submit-review", kwargs={"pk": incident.id}
        )
        res_blank = api_client.post(submit_url, format="json")
        assert res_blank.status_code == status.HTTP_400_BAD_REQUEST
        assert "must have a summary" in str(res_blank.data.get("errors"))

    def test_postmortem_action_items_admin_vs_member_rbac(self, api_client, setup_data, incident):
        # Admin creates postmortem
        IncidentPostmortem.objects.create(incident=incident, created_by=setup_data["user"])

        url = reverse("api:incidents:incidents-postmortem-action-items", kwargs={"pk": incident.id})

        # Regular member attempting to create action item -> 403 Forbidden
        api_client.force_authenticate(user=setup_data["member_user"])
        res_member_create = api_client.post(
            url,
            {"title": "Member item", "owner": setup_data["admin_member"].id},
            format="json",
        )
        assert res_member_create.status_code == status.HTTP_403_FORBIDDEN

        # Regular member viewing action items -> 200 OK
        res_member_get = api_client.get(url)
        assert res_member_get.status_code == status.HTTP_200_OK

        # Admin creating action item -> 201 Created
        api_client.force_authenticate(user=setup_data["user"])
        data = {
            "title": "Admin item",
            "description": "Ensure bounded memory queue size",
            "owner": setup_data["admin_member"].id,
            "status": "PENDING",
        }
        res_admin_create = api_client.post(url, data, format="json")
        assert res_admin_create.status_code == status.HTTP_201_CREATED

        res_data = res_admin_create.data.get("data", res_admin_create.data)
        item_id = res_data["id"]
        detail_url = reverse(
            "api:incidents:incidents-postmortem-action-item-detail",
            kwargs={"pk": incident.id, "item_id": item_id},
        )

        # Member patching action item -> 403 Forbidden
        api_client.force_authenticate(user=setup_data["member_user"])
        res_member_patch = api_client.patch(detail_url, {"status": "COMPLETED"}, format="json")
        assert res_member_patch.status_code == status.HTTP_403_FORBIDDEN

        # Admin patching action item -> 200 OK and completed_at is set
        api_client.force_authenticate(user=setup_data["user"])
        res_admin_patch = api_client.patch(detail_url, {"status": "COMPLETED"}, format="json")
        assert res_admin_patch.status_code == status.HTTP_200_OK

        item = PostmortemActionItem.objects.get(id=item_id)
        assert item.status == "COMPLETED"
        assert item.completed_at is not None

        # Admin moving status back to IN_PROGRESS clears completed_at
        api_client.patch(detail_url, {"status": "IN_PROGRESS"}, format="json")
        item.refresh_from_db()
        assert item.status == "IN_PROGRESS"
        assert item.completed_at is None

    def test_postmortem_action_item_invalid_owner_fails(self, api_client, setup_data, incident):
        # Create a member from another team
        other_user = get_user_model().objects.create(email="alien@example.com")
        alien_member = TeamMember.objects.create(
            team=setup_data["other_project"].team, user=other_user, role="member"
        )

        api_client.force_authenticate(user=setup_data["user"])
        url = reverse("api:incidents:incidents-postmortem-action-items", kwargs={"pk": incident.id})

        data = {
            "title": "Cross team task",
            "owner": alien_member.id,
        }

        response = api_client.post(url, data, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "owner must be an active member" in str(response.data.get("errors"))

    def test_postmortem_action_items_completed_postmortem_immutable(
        self, api_client, setup_data, incident
    ):
        api_client.force_authenticate(user=setup_data["user"])
        postmortem = IncidentPostmortem.objects.create(
            incident=incident,
            status=IncidentPostmortem.Status.COMPLETED,
            created_by=setup_data["user"],
        )
        item = PostmortemActionItem.objects.create(
            postmortem=postmortem,
            title="Existing item",
            owner=setup_data["admin_member"],
            status="PENDING",
        )

        url = reverse("api:incidents:incidents-postmortem-action-items", kwargs={"pk": incident.id})
        detail_url = reverse(
            "api:incidents:incidents-postmortem-action-item-detail",
            kwargs={"pk": incident.id, "item_id": item.id},
        )

        # 1. Create on completed postmortem fails
        res_create = api_client.post(
            url, {"title": "New item", "owner": setup_data["admin_member"].id}, format="json"
        )
        assert res_create.status_code == status.HTTP_400_BAD_REQUEST
        assert "completed" in str(res_create.data.get("errors"))

        # 2. Patch on completed postmortem fails
        res_patch = api_client.patch(detail_url, {"title": "Updated title"}, format="json")
        assert res_patch.status_code == status.HTTP_400_BAD_REQUEST
        assert "completed" in str(res_patch.data.get("errors"))

        # 3. Delete on completed postmortem fails
        res_delete = api_client.delete(detail_url)
        assert res_delete.status_code == status.HTTP_400_BAD_REQUEST
        assert "completed" in str(res_delete.data.get("errors"))


class TestReliabilityReportService:
    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    )
    def test_get_reliability_report_and_caching(self, setup_data, api_client):
        user = setup_data["user"]
        project = setup_data["project"]
        api_client.force_authenticate(user=user)

        now = timezone.now()

        # Incident 1
        i1 = Incident.objects.create(
            project=project,
            status=Incident.Status.RESOLVED,
            severity=Incident.Severity.CRITICAL,
        )
        i1.created_at = now - timedelta(hours=24)
        i1.resolved_at = now - timedelta(hours=23)
        i1.save(update_fields=["created_at", "resolved_at"])

        # Incident 2
        i2 = Incident.objects.create(
            project=project,
            status=Incident.Status.RESOLVED,
            severity=Incident.Severity.CRITICAL,
        )
        i2.created_at = now - timedelta(hours=12)
        i2.resolved_at = now - timedelta(hours=10)
        i2.save(update_fields=["created_at", "resolved_at"])

        # Clear cache first
        cache.clear()

        # MTTR = (1h + 2h) / 2 = 1.5h = 5400s
        # MTBF = 12h = 43200s (from T-24h to T-12h)
        start_time = now - timedelta(days=2)
        end_time = now

        report = get_reliability_report(project.id, start_time, end_time)

        assert report["total_incidents"] == 2
        assert report["mttr_seconds"] == 5400.0
        assert report["mtbf_seconds"] == 43200.0

        # Verify cache hit
        cache_key = (
            f"reliability_report_{project.id}_{start_time.isoformat()}_{end_time.isoformat()}"
        )
        cached = cache.get(cache_key)
        assert cached is not None
        assert cached["mttr_seconds"] == 5400.0


class TestAIIncidentKnowledge:
    def test_build_incident_knowledge_structure_and_determinism(
        self, setup_data, incident, runbook
    ):
        # 1. Attach Runbook execution
        execution = IncidentRunbookExecution.objects.create(
            incident=incident, runbook=runbook, status="IN_PROGRESS"
        )
        execution.step_states = {"step_1": "COMPLETED"}
        execution.save()

        # 2. Attach Postmortem & Action Item
        postmortem = IncidentPostmortem.objects.create(
            incident=incident,
            status="IN_REVIEW",
            summary="Worker OOM incident",
            confirmed_root_cause="Leaked buffer array",
            resolution="Patched buffer lifecycle",
            created_by=setup_data["user"],
        )
        PostmortemActionItem.objects.create(
            postmortem=postmortem,
            title="Deploy buffer patch",
            owner=setup_data["admin_member"],
            status="PENDING",
        )

        knowledge = build_incident_knowledge(incident)

        # Check top-level keys
        assert "incident" in knowledge
        assert "events" in knowledge
        assert "intelligence" in knowledge
        assert "runbook_executions" in knowledge
        assert "postmortem" in knowledge

        # Check values
        assert knowledge["incident"]["id"] == incident.id
        assert knowledge["runbook_executions"][0]["id"] == execution.id
        assert knowledge["postmortem"]["confirmed_root_cause"] == "Leaked buffer array"
        assert len(knowledge["postmortem"]["action_items"]) == 1
        assert knowledge["postmortem"]["action_items"][0]["title"] == "Deploy buffer patch"

        # Verify serializability to pure JSON
        json_output = json.dumps(knowledge)
        assert len(json_output) > 0

    def test_build_incident_knowledge_query_count_regression(
        self, django_assert_num_queries, setup_data, incident, runbook
    ):
        from apps.incidents.models import IncidentEvent

        # Populate multiple related models to ensure no N+1 query regression
        for i in range(5):
            IncidentEvent.objects.create(
                incident=incident,
                event_type="NOTE_ADDED",
                actor=setup_data["user"],
                metadata={"index": i},
            )

        for _ in range(3):
            IncidentRunbookExecution.objects.create(
                incident=incident,
                runbook=runbook,
                status="IN_PROGRESS",
            )

        postmortem = IncidentPostmortem.objects.create(
            incident=incident,
            status="IN_REVIEW",
            summary="Multi item postmortem",
            created_by=setup_data["user"],
        )

        for i in range(4):
            PostmortemActionItem.objects.create(
                postmortem=postmortem,
                title=f"Action item {i}",
                owner=setup_data["admin_member"],
            )

        # The query count must be strictly constant (4 queries total)
        with django_assert_num_queries(4):
            knowledge = build_incident_knowledge(incident)

        assert len(knowledge["events"]) == 5
        assert len(knowledge["runbook_executions"]) == 3
        assert len(knowledge["postmortem"]["action_items"]) == 4
