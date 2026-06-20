from django.conf import settings
from django.db import models


class Conversation(models.Model):
    """A model-chat conversation owned by a user. Distinct from projects/tasks —
    this is for talking to an AI model, not submitting coding work."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="conversations"
    )
    title = models.CharField(max_length=120, default="New chat")
    model = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.title} (#{self.pk})"


class Message(models.Model):
    ROLE_CHOICES = [("user", "user"), ("assistant", "assistant")]

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    role = models.CharField(max_length=12, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.role}: {self.content[:40]}"
