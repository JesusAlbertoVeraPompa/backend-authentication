# apps/users/models_deleted.py

from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import timedelta

User = get_user_model()

class DeletedUser(models.Model):
    """
    Guarda usuarios eliminados o históricos.
    - original_user_id: id del usuario original
    - username, email, role, is_verified: snapshot de datos
    - deleted_at: fecha de eliminación
    """
    original_user_id = models.IntegerField()
    username = models.CharField(max_length=150)
    email = models.EmailField()
    role = models.CharField(max_length=10)
    is_verified = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(auto_now_add=True)

    def is_within_recovery_period(self):
        """True si está dentro de los 15 días"""
        return timezone.now() <= self.deleted_at + timedelta(days=15)

    def __str__(self):
        return f"{self.username} ({self.email}) - Deleted at {self.deleted_at}"