from django.db import models


class Inquiry(models.Model):
    name = models.CharField(max_length=200)
    email = models.EmailField()
    message = models.TextField()
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'inquiries'
        ordering = ['-submitted_at']

    def __str__(self):
        return f'{self.name} <{self.email}>'
