# apps/users/views.py

from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.core.mail import send_mail

# Importación de tus utilitarios de respuesta personalizada
# Asegúrate de que la ruta sea correcta según tu estructura de carpetas
from apps.core.utils.responses import success_response, error_response

# Importaciones locales del módulo de usuarios
from .serializers import UserSerializer, UserUpdateSerializer
from .permissions import IsAdmin, IsStaff
from .models_deleted import DeletedUser

User = get_user_model()


class UserViewSet(viewsets.ModelViewSet):
    """
    Controlador de Usuarios con respuestas estandarizadas y sistema de auditoría.
    Maneja el CRUD de administradores y las acciones de perfil de usuario.
    """

    queryset = User.objects.all()
    filter_backends = [filters.SearchFilter]
    search_fields = ["username", "email"]

    # --------------------------------------------------------
    # CONFIGURACIÓN DINÁMICA
    # --------------------------------------------------------

    def get_serializer_class(self):
        """Selecciona el serializador según la acción para proteger campos sensibles"""
        if self.action in ["update", "partial_update", "me"]:
            return UserUpdateSerializer
        return UserSerializer

    def get_permissions(self):
        """Define quién puede hacer qué en la API"""
        if self.action in ["list", "retrieve"]:
            return [IsStaff()]  # Staff puede ver pero no editar todo
        if self.action in ["me", "delete_me"]:
            return [IsAuthenticated()]  # Cualquier logueado maneja su perfil
        if self.action in ["restore", "set_initial_password"]:
            return [AllowAny()]  # Acciones de recuperación/invitación
        return [IsAdmin()]  # Por defecto solo Admin (Create/Delete/Update global)

    # --------------------------------------------------------
    # MÉTODOS CRUD ESTÁNDAR (ADAPTADOS)
    # --------------------------------------------------------

    def list(self, request, *args, **kwargs):
        """Obtiene todos los usuarios y devuelve respuesta unificada"""
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        custom_data = {"count": queryset.count(), "users": serializer.data}
        return success_response("Lista de usuarios obtenida", custom_data)

    def retrieve(self, request, *args, **kwargs):
        """Detalle de un usuario específico por ID"""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return success_response("Detalle del usuario obtenido", serializer.data)

    def create(self, request, *args, **kwargs):
        """[ADMIN] Crea un usuario sin password y envía invitación por email"""
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return error_response("Datos de usuario inválidos", serializer.errors)

        # Crear usuario con password inutilizable inicialmente
        user = serializer.save()
        user.set_unusable_password()
        user.save()

        # Generar tokens de seguridad para el enlace de invitación
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        # URL que el frontend procesará para pedir la nueva contraseña
        setup_url = f"https://tu-frontend.com/set-password/{uid}/{token}/"

        # Envío de correo (Debería ser asíncrono en producción)
        try:
            send_mail(
                subject="Invitación a la plataforma",
                message=f"Hola, se ha creado tu cuenta. Establece tu contraseña aquí: {setup_url}",
                from_email="admin@tuapp.com",
                recipient_list=[user.email],
            )
        except Exception as e:
            # Si falla el correo, igual informamos que el usuario se creó
            return success_response(
                "Usuario creado, pero hubo un error al enviar el email",
                serializer.data,
                201,
            )

        return success_response(
            "Usuario creado e invitación enviada exitosamente",
            serializer.data,
            status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        """[ADMIN] Actualización total o parcial de un usuario"""
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)

        if not serializer.is_valid():
            return error_response("Error al actualizar usuario", serializer.errors)

        self.perform_update(serializer)
        return success_response("Usuario actualizado correctamente", serializer.data)

    def destroy(self, request, *args, **kwargs):
        """[ADMIN] Borrado físico pero guardando respaldo en DeletedUser"""
        instance = self.get_object()
        self._create_deleted_snapshot(instance)  # Respaldo para auditoría/restauración
        instance.delete()
        return success_response(
            "Usuario eliminado correctamente", status_code=status.HTTP_200_OK
        )

    # --------------------------------------------------------
    # ACCIONES DE PERFIL (ACCESO PARA EL USUARIO LOGUEADO)
    # --------------------------------------------------------

    @action(detail=False, methods=["get", "patch", "delete"], url_path="me")
    def me(self, request):
        """Permite al usuario gestionar su propia cuenta"""
        user = request.user

        if request.method == "GET":
            serializer = UserSerializer(user)
            return success_response("Tu perfil ha sido obtenido", serializer.data)

        if request.method == "PATCH":
            serializer = self.get_serializer(user, data=request.data, partial=True)
            if not serializer.is_valid():
                return error_response(
                    "Error al actualizar tu perfil", serializer.errors
                )
            serializer.save()
            return success_response("Tu perfil se actualizó con éxito", serializer.data)

        if request.method == "DELETE":
            # Autodeleción: El usuario borra su cuenta pero se guarda backup
            self._create_deleted_snapshot(user)
            user.delete()
            return success_response(
                "Tu cuenta ha sido eliminada. Tienes 15 días para restaurarla."
            )

    # --------------------------------------------------------
    # ACCIONES PÚBLICAS
    # --------------------------------------------------------

    @action(detail=False, methods=["post"])
    def set_initial_password(self, request):
        """Procesa el token enviado por email para establecer la contraseña inicial"""
        uidb64 = request.data.get("uid")
        token = request.data.get("token")
        password = request.data.get("password")

        if not all([uidb64, token, password]):
            return error_response("Faltan datos requeridos (uid, token, password)")

        try:
            # Decodificar el ID del usuario desde base64
            uid = urlsafe_base64_decode(uidb64).decode()
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return error_response(
                "Enlace de invitación inválido o corrupto", status_code=400
            )

        # Validar el token de Django contra el usuario
        if default_token_generator.check_token(user, token):
            user.set_password(password)
            user.is_verified = True  # Se marca como verificado al poner su clave
            user.save()
            return success_response(
                "Contraseña establecida correctamente. Ya puedes iniciar sesión."
            )

        return error_response(
            "El enlace ha expirado o ya fue utilizado", status_code=400
        )

    @action(detail=False, methods=["post"])
    def restore(self, request):
        """Intenta restaurar una cuenta borrada si está dentro del periodo de gracia"""
        email = request.data.get("email")
        if not email:
            return error_response("El email es necesario para la restauración")

        try:
            deleted = DeletedUser.objects.get(email=email)

            # Verificar si han pasado más de 15 días (u otro tiempo definido en el modelo)
            if not deleted.is_within_recovery_period():
                deleted.delete()  # Limpieza definitiva
                return error_response(
                    "El periodo de recuperación ha expirado", status_code=400
                )

            # Re-crear el usuario con los datos guardados en el backup
            user = User.objects.create(
                id=deleted.original_user_id,
                username=deleted.username,
                email=deleted.email,
                role=deleted.role,
                is_verified=deleted.is_verified,
            )
            deleted.delete()  # Borrar del backup una vez restaurado

            return success_response(
                "Cuenta restaurada exitosamente",
                UserSerializer(user).data,
                status_code=status.HTTP_201_CREATED,
            )

        except DeletedUser.DoesNotExist:
            return error_response(
                "No se encontró una cuenta eliminada vinculada a este email",
                status_code=404,
            )

    # --------------------------------------------------------
    # HELPERS PRIVADOS
    # --------------------------------------------------------

    def _create_deleted_snapshot(self, user_instance):
        """
        Copia de seguridad interna.
        Mueve los datos críticos del usuario a la tabla DeletedUser antes de borrarlo.
        """
        return DeletedUser.objects.create(
            original_user_id=user_instance.id,
            username=user_instance.username,
            email=user_instance.email,
            role=user_instance.role,
            is_verified=user_instance.is_verified,
            deleted_at=timezone.now(),
        )
