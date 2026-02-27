# apps/users/views.py

from rest_framework import viewsets, filters
from django.contrib.auth import get_user_model
from .serializers import UserSerializer
from .permissions import IsAdmin, IsStaff

User = get_user_model()

class UserViewSet(viewsets.ModelViewSet):
    """
    CRUD completo de usuarios accesible por administradores.
    Permite búsqueda por username y email.
    Solo lectura para staff, edición y eliminación solo para admin.
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['username', 'email']

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsStaff()]
        return [IsAdmin()]