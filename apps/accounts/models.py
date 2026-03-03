# apps/accounts/models.py

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from datetime import timedelta


class User(AbstractUser):
    """
    Modelo de usuario personalizado.

    Extiende AbstractUser y añade:
    - role: rol del usuario en el sistema
    - is_verified: indica si verificó su correo
    - verification_code: código HASHED para verificación
    - verification_code_created_at: fecha de creación del código
    - reset_code: código HASHED para recuperación de contraseña
    - reset_code_created_at: fecha de creación del código
    """

    # Email único (se usará como identificador principal)
    email = models.EmailField(unique=True)

    # Eliminamos dependencia fuerte del username si deseas usar solo email
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    ROLE_CHOICES = (
        ("admin", "Admin"),
        ("staff", "Personal"),
        ("user", "Usuario"),
    )

    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="user")
    is_verified = models.BooleanField(default=False)

    # ==============================
    # VERIFICACIÓN DE EMAIL
    # ==============================

    verification_code = models.CharField(max_length=128, null=True, blank=True)
    verification_code_created_at = models.DateTimeField(null=True, blank=True)

    # ==============================
    # RECUPERACIÓN DE CONTRASEÑA
    # ==============================

    reset_code = models.CharField(max_length=128, null=True, blank=True)
    reset_code_created_at = models.DateTimeField(null=True, blank=True)

    # Tiempo de expiración (10 minutos)
    CODE_EXPIRATION_MINUTES = 10

    def verification_code_is_expired(self):
        """
        Verifica si el código de verificación expiró.
        """
        if not self.verification_code_created_at:
            return True

        return timezone.now() > (
            self.verification_code_created_at +
            timedelta(minutes=self.CODE_EXPIRATION_MINUTES)
        )

    def reset_code_is_expired(self):
        """
        Verifica si el código de recuperación expiró.
        """
        if not self.reset_code_created_at:
            return True

        return timezone.now() > (
            self.reset_code_created_at +
            timedelta(minutes=self.CODE_EXPIRATION_MINUTES)
        )

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        """
        Si el usuario no tiene contraseña,
        se asigna una contraseña inutilizable.
        """
        if not self.password:
            self.set_unusable_password()
        super().save(*args, **kwargs)