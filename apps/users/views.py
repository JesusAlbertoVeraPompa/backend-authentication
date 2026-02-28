# apps/users/views.py

from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes

# Importación de tus utilitarios de respuesta
from apps.core.utils.responses import success_response, error_response
from .serializers import UserSerializer, UserUpdateSerializer
from .permissions import IsAdmin, IsStaff
from .models_deleted import DeletedUser
from django.core.mail import send_mail

User = get_user_model()


class UserViewSet(viewsets.ModelViewSet):
    """
    Controlador de Usuarios con respuestas estandarizadas y auditoría.
    """

    queryset = User.objects.all()
    filter_backends = [filters.SearchFilter]
    search_fields = ["username", "email"]

    # --------------------------------------------------------
    # CONFIGURACIÓN DINÁMICA (SERIALIZADORES Y PERMISOS)
    # --------------------------------------------------------

    def get_serializer_class(self):
        if self.action in ["update", "partial_update", "me"]:
            return UserUpdateSerializer
        return UserSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [IsStaff()]
        if self.action in ["me", "delete_me"]:
            return [IsAuthenticated()]
        if self.action in ["restore", "set_initial_password"]:
            return [AllowAny()]
        return [IsAdmin()]

    # --------------------------------------------------------
    # SOBRESCRITURA DE MÉTODOS CRUD ESTÁNDAR
    # (Para que usen success_response)
    # --------------------------------------------------------

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        custom_data = {"count": queryset.count(), "users": serializer.data}
        return success_response("Lista de usuarios obtenida", custom_data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return success_response("Detalle del usuario obtenido", serializer.data)

    def create(self, request, *args, **kwargs):
        """[ADMIN] Crea usuario y dispara invitación."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Guardar y configurar invitación
        user = serializer.save()
        user.set_unusable_password()
        user.save()

        # Lógica de envío de email (UID y Token)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        setup_url = f"https://tu-frontend.com/set-password/{uid}/{token}/"

        send_mail(
            subject="Invitación a la plataforma",
            message=f"Establece tu contraseña aquí: {setup_url}",
            from_email="admin@tuapp.com",
            recipient_list=[user.email],
        )

        return success_response(
            "Usuario creado e invitación enviada",
            serializer.data,
            status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        """
        [ADMIN] Maneja tanto PUT como PATCH (/api/users/{id}/).
        Sobrescribimos para devolver tu success_response.
        """
        partial = kwargs.pop("partial", False)  # Detecta si es PATCH
        instance = self.get_object()

        # Usamos el serializer de actualización (UserUpdateSerializer)
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        # perform_update ya tiene la lógica de snapshot en el serializer
        self.perform_update(serializer)

        return success_response(
            message="Usuario actualizado correctamente por el administrador",
            data=serializer.data,
        )

    def destroy(self, request, *args, **kwargs):
        """[ADMIN] Borrado con backup y respuesta personalizada."""
        instance = self.get_object()
        self._create_deleted_snapshot(instance)
        username = instance.username
        instance.delete()
        return success_response(f"Usuario '{username}' eliminado correctamente")

    # --------------------------------------------------------
    # ACCIONES DE PERFIL (ME / DELETE_ME)
    # --------------------------------------------------------

    @action(detail=False, methods=["get", "patch"], url_path="me")
    def me(self, request):
        """
        [USUARIO] Gestión de cuenta propia.
        GET: Retorna los datos del usuario autenticado.
        PATCH: Actualiza datos (username/email) y genera snapshot.
        """
        user = request.user

        if request.method == "GET":
            # Usamos el serializer de lectura para mostrar datos completos
            serializer = UserSerializer(user)
            return success_response("Datos de tu perfil obtenidos", serializer.data)

        if request.method == "PATCH":
            # Usamos el serializer de actualización para procesar el snapshot
            serializer = self.get_serializer(user, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return success_response(
                "Tu perfil ha sido actualizado con éxito", serializer.data
            )

    @action(detail=False, methods=["delete"])
    def delete_me(self, request):
        """[USUARIO] El propio usuario solicita darse de baja (Soft delete)."""
        self._create_deleted_snapshot(request.user)
        request.user.delete()
        return success_response(
            "Tu cuenta ha sido eliminada. Tienes 15 días para restaurarla."
        )

    # --------------------------------------------------------
    # ACCIONES PÚBLICAS (PASSWORD / RESTORE)
    # --------------------------------------------------------

    @action(detail=False, methods=["post"])
    def set_initial_password(self, request):
        """[PÚBLICO] Establecer contraseña mediante token de invitación."""
        uidb64 = request.data.get("uid")
        token = request.data.get("token")
        password = request.data.get("password")

        if not all([uidb64, token, password]):
            return error_response("Datos incompletos (uid, token, password requeridos)")

        try:
            uid = urlsafe_base64_decode(uidb64).decode()
            user = User.objects.get(pk=uid)
        except:
            return error_response("Enlace de invitación inválido", 400)

        if default_token_generator.check_token(user, token):
            user.set_password(password)
            user.is_verified = True
            user.save()
            return success_response(
                "Contraseña establecida con éxito. Ya puedes iniciar sesión."
            )

        return error_response("El enlace ha expirado o ya fue utilizado", 400)

    @action(detail=False, methods=["post"])
    def restore(self, request):
        """[PÚBLICO] Recupera una cuenta dentro del periodo de gracia."""
        email = request.data.get("email")
        if not email:
            return error_response("El email es requerido")

        try:
            deleted = DeletedUser.objects.get(email=email)

            if not deleted.is_within_recovery_period():
                deleted.delete()
                return error_response("El periodo de recuperación ha expirado", 400)

            user = User.objects.create(
                id=deleted.original_user_id,
                username=deleted.username,
                email=deleted.email,
                role=deleted.role,
                is_verified=deleted.is_verified,
            )
            deleted.delete()
            return success_response(
                "Tu cuenta ha sido restaurada con éxito", UserSerializer(user).data, 201
            )

        except DeletedUser.DoesNotExist:
            return error_response(
                "No se encontró registro de eliminación para este email", 404
            )

    # --------------------------------------------------------
    # HELPERS
    # --------------------------------------------------------

    def _create_deleted_snapshot(self, user_instance):
        """Crea una copia de los datos en la tabla de auditoría."""
        return DeletedUser.objects.create(
            original_user_id=user_instance.id,
            username=user_instance.username,
            email=user_instance.email,
            role=user_instance.role,
            is_verified=user_instance.is_verified,
            deleted_at=timezone.now(),
        )
