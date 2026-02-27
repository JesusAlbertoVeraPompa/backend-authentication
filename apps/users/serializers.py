# apps/users/serializers.py

from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    """
    Serializer para gestión de usuarios por admin/staff.
    Permite ver y editar información básica del usuario.
    """

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'role',
            'is_verified',
            'is_active',
            'date_joined'
        ]
        read_only_fields = ['id', 'date_joined']