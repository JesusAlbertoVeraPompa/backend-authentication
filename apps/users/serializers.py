# apps/users/serializers.py

from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models_deleted import DeletedUser
from django.utils import timezone

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer base para lectura y creación de usuarios.
    """

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "role",
            "is_verified",
            "is_active",
            "date_joined",
        ]
        read_only_fields = ["id", "date_joined"]


class UserUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer especializado en actualizaciones con lógica de auditoría.
    """

    class Meta:
        model = User
        fields = ["username", "email", "role", "is_verified"]
        # Por defecto, estos campos son de solo lectura para usuarios normales
        read_only_fields = ["role", "is_verified"]

    def validate_email(self, value):
        """
        Validación de seguridad: Evita errores 500 por emails duplicados.
        """
        user = self.instance
        if User.objects.exclude(pk=user.pk).filter(email=value).exists():
            raise serializers.ValidationError(
                "Este email ya está siendo usado por otra cuenta."
            )
        return value

    def update(self, instance, validated_data):
        # 1. SEGURIDAD: Verificar si realmente hay cambios antes de actuar
        has_changes = any(
            getattr(instance, attr) != value for attr, value in validated_data.items()
        )

        if not has_changes:
            return instance

        # 2. AUDITORÍA: Crear snapshot del estado ANTES de los cambios
        DeletedUser.objects.create(
            original_user_id=instance.id,
            username=instance.username,
            email=instance.email,
            role=instance.role,
            is_verified=instance.is_verified,
            deleted_at=timezone.now(),
        )

        # 3. LÓGICA DE ESCALADA: Permitir a Admins editar campos protegidos
        request = self.context.get("request")
        if request and request.user.role == "admin":
            # Si el admin envió estos campos en el JSON, los aplicamos manualmente
            if "role" in request.data:
                instance.role = request.data["role"]
            if "is_verified" in request.data:
                instance.is_verified = request.data["is_verified"]

        # 4. Aplicar cambios validados (username, email, etc.)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance
