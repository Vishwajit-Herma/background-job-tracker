import pytest
from rest_framework import status
from apps.teams.models import TeamMember, Team
from apps.incidents.models import Incident
from apps.projects.models import Project
from apps.jobs.models import Job
from django.contrib.auth import get_user_model


@pytest.fixture
def setup_data(db):
    User = get_user_model()
    user = User.objects.create(email="analytics3@example.com")
    user.set_password("password")
    user.save()

    team = Team.objects.create(name="Analytics Team 3", slug="analytics3", owner=user)
    project = Project.objects.create(team=team, name="Analytics Project 3")
    job1 = Job.objects.create(project=project, name="Job 1", task_identifier="task_1")

    return user, team, project, job1, None


@pytest.fixture
def incident_setup(api_client, setup_data):
    user, team, project, job1, _ = setup_data

    # Create a regular member
    from django.contrib.auth import get_user_model

    User = get_user_model()
    member_user = User.objects.create(email="member@example.com")
    member = TeamMember.objects.create(team=team, user=member_user, role="member")

    incident = Incident.objects.create(
        project=project,
        job=job1,
        status=Incident.Status.OPEN,
    )

    return user, member_user, member, incident


@pytest.mark.django_db
def test_tenant_isolation(api_client, setup_data, incident_setup):
    user, member_user, member, incident = incident_setup

    from django.contrib.auth import get_user_model

    User = get_user_model()
    hacker = User.objects.create(email="hacker@example.com")

    api_client.force_authenticate(user=hacker)
    response = api_client.get(f"/api/incidents/{incident.id}/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_assign_rbac(api_client, incident_setup):
    user, member_user, member, incident = incident_setup

    # Member cannot assign
    api_client.force_authenticate(user=member_user)
    response = api_client.post(f"/api/incidents/{incident.id}/assign/", {"member_id": member.id})
    assert response.status_code == status.HTTP_403_FORBIDDEN

    # Admin can assign
    api_client.force_authenticate(user=user)
    response = api_client.post(f"/api/incidents/{incident.id}/assign/", {"member_id": member.id})
    assert response.status_code == status.HTTP_200_OK

    incident.refresh_from_db()
    assert incident.assigned_to == member


@pytest.mark.django_db
def test_acknowledge_and_resolve_rbac(api_client, incident_setup):
    user, member_user, member, incident = incident_setup

    # Unassigned member cannot acknowledge
    api_client.force_authenticate(user=member_user)
    response = api_client.post(f"/api/incidents/{incident.id}/acknowledge/")
    assert response.status_code == status.HTTP_403_FORBIDDEN

    # Assign the member
    incident.assigned_to = member
    incident.save()

    # Assigned member CAN acknowledge
    response = api_client.post(f"/api/incidents/{incident.id}/acknowledge/")
    assert response.status_code == status.HTTP_200_OK
    incident.refresh_from_db()
    assert incident.status == Incident.Status.ACKNOWLEDGED

    # Assigned member CAN resolve
    response = api_client.post(f"/api/incidents/{incident.id}/resolve/")
    assert response.status_code == status.HTTP_200_OK
    incident.refresh_from_db()
    assert incident.status == Incident.Status.RESOLVED


@pytest.mark.django_db
def test_reopen_rbac(api_client, incident_setup):
    user, member_user, member, incident = incident_setup
    incident.status = Incident.Status.RESOLVED
    incident.assigned_to = member
    incident.save()

    # Assigned member CANNOT reopen
    api_client.force_authenticate(user=member_user)
    response = api_client.post(f"/api/incidents/{incident.id}/reopen/")
    assert response.status_code == status.HTTP_403_FORBIDDEN

    # Admin CAN reopen
    api_client.force_authenticate(user=user)
    response = api_client.post(f"/api/incidents/{incident.id}/reopen/")
    assert response.status_code == status.HTTP_200_OK
    incident.refresh_from_db()
    assert incident.status == Incident.Status.OPEN


@pytest.mark.django_db
def test_immutable_notes(api_client, incident_setup):
    user, member_user, member, incident = incident_setup
    api_client.force_authenticate(user=user)

    # Create note
    response = api_client.post(f"/api/incidents/{incident.id}/notes/", {"content": "Investigating"})
    assert response.status_code == status.HTTP_201_CREATED
    note_id = response.data.get("data", response.data)["id"]

    # Ensure no PUT/PATCH/DELETE allowed
    assert api_client.put(f"/api/incidents/{incident.id}/notes/{note_id}/").status_code in [
        403,
        404,
        405,
    ]
    assert api_client.delete(f"/api/incidents/{incident.id}/notes/{note_id}/").status_code in [
        403,
        404,
        405,
    ]
