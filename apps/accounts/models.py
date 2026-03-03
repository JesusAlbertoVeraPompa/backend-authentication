# apps/accounts/models.py

from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    """
    Modelo de usuario personalizado.
    Extiende AbstractUser y añade:
    - role: rol del usuario en el sistema
    - is_verified: indica si verificó su correo
    - verification_code: código temporal para verificación
    - reset_code: código temporal para recuperación de contraseña
    """
    email = models.EmailField(unique=True)
    
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('staff', 'Personal'),
        ('user', 'Usuario'),
    )

    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='user')
    is_verified = models.BooleanField(default=False)

    # Código de verificación por email
    verification_code = models.CharField(max_length=6, null=True, blank=True)

    # Código para recuperación de contraseña
    reset_code = models.CharField(max_length=6, null=True, blank=True)

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        if not self.password:
            self.set_unusable_password()
        super().save(*args, **kwargs)