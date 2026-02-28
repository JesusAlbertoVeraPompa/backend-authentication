# apps/users/urls.py

from rest_framework.routers import DefaultRouter
from .views import UserViewSet

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='users')

urlpatterns = router.urls
# PATCH /api/users/me/ -> modificar mis datos
# DELETE /api/users/me/ -> eliminar mi cuenta (soft delete)
# POST /api/users/restore/ -> restaurar cuenta