# apps/users/permissions.py

from rest_framework.permissions import BasePermission

class IsAdmin(BasePermission):
    """
    Permite acceso solo a usuarios con rol 'admin'
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == "admin"

class IsStaff(BasePermission):
    """
    Permite acceso a 'admin' y 'staff'
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ["admin", "staff"]