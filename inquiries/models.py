from django.db import models


class Inquiry(models.Model):
    NEW = 'new'
    CONTACTED = 'contacted'
    CONVERTED = 'converted'
    CLOSED = 'closed'

    STATUS_CHOICES = [
        (NEW, 'New'),
        (CONTACTED, 'Contacted'),
        (CONVERTED, 'Converted'),
        (CLOSED, 'Closed'),
    ]

    name = models.CharField(max_length=255)
    email = models.EmailField()
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=NEW)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} <{self.email}>"
