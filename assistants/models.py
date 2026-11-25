from django.db import models
from django.utils import timezone


class AccessKey(models.Model):
    """An app's key for the MCP server. Only the SHA-256 of the key is stored."""

    name = models.CharField(max_length=40)
    prefix = models.CharField(max_length=8)  # first 8 chars after "tly_mcp_"
    key_hash = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return self.name

    @classmethod
    def active(cls):
        return cls.objects.filter(revoked_at__isnull=True)


class AssistantActivity(models.Model):
    READ, CHANGE = "read", "change"

    key = models.ForeignKey(
        AccessKey, on_delete=models.CASCADE, related_name="activity"
    )
    what = models.CharField(max_length=120)
    kind = models.CharField(max_length=6, choices=[(READ, "Read"), (CHANGE, "Change")])
    order = models.ForeignKey(
        "orders.Order",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-at", "-id"]
        verbose_name_plural = "assistant activity"

    def __str__(self):
        return self.what
