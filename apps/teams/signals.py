"""Signal handlers for teams app."""

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.teams.models import Team, TeamMember


@receiver(post_save, sender=Team)
def create_owner_membership(sender, instance, created, **kwargs):
    """Automatically create owner membership when team is created."""
    if created:
        TeamMember.objects.get_or_create(
            team=instance,
            user=instance.owner,
            defaults={
                "role": "owner",
                "added_by": instance.owner,
            },
        )
