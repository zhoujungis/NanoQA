"""组织域（§9.2）。"""
from django.conf import settings
from django.db import models

from common.models import TimestampedModel


class Organization(TimestampedModel):
    name = models.CharField(max_length=128)
    slug = models.SlugField(max_length=64, unique=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_organizations"
    )

    class Meta:
        db_table = "organizations_organization"
        ordering = ["id"]

    def __str__(self):
        return self.name


class OrganizationMember(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="org_memberships")
    role = models.ForeignKey("accounts.Role", on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "organizations_member"
        unique_together = [("organization", "user")]
