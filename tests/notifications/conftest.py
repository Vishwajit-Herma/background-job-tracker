import pytest
from apps.projects.models import Project
from apps.incidents.models import Incident


@pytest.fixture
def project(team):
    return Project.objects.create(team=team, name="Test Project")


@pytest.fixture
def incident(project):
    return Incident.objects.create(
        project=project,
        status=Incident.Status.OPEN,
        severity=Incident.Severity.CRITICAL,
    )
