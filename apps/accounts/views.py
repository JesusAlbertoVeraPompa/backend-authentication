from rest_framework import generics, status
from django.contrib.auth import authenticate, get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.mail import send_mail
from rest_framework.permissions import AllowAny

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from .serializers import RegisterSerializer
from apps.core.generators import generate_verification_code
from apps.core.utils.responses import success_response, error_response

from django.db import transaction
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

User = get_user_model()


class RegisterView(generics.GenericAPIView):
    """
    Registro de nuevos usuarios
    - Crea el usuario
    - Envía código de verificación al correo
    """

    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if not serializer.is_valid():
            return error_response(
                message="Error en el registro",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            user = serializer.save()

            # Generar código de verificación
            code = generate_verification_code()
            user.verification_code = str(code)
            user.save()

            # Enviar correo
            try:
                send_mail(
                    "Código de verificación",
                    f"Tu código de verificación es: {code}",
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                    fail_silently=False,
                )
            except Exception as e:
                logger.error(f"Error enviando email de verificación: {str(e)}")

        return success_response(
            message="Usuario registrado correctamente. Revisa tu correo para verificar la cuenta.",
            data={
                "id": user.id,
                "username": user.username,
                "email": user.email,
            },
            status_code=status.HTTP_201_CREATED,
        )


class LoginView(generics.GenericAPIView):
    """
    Login con JWT
    - Valida email y contraseña
    - Verifica que el usuario haya confirmado su correo
    - Devuelve access y refresh tokens
    """

    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")
        password = request.data.get("password")

        # Validar campos obligatorios
        if not email or not password:
            return error_response(
                "Email y contraseña son obligatorios",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Buscar usuario por email
        try:
            user_obj = User.objects.get(email=email)
        except User.DoesNotExist:
            return error_response(
                "Credenciales inválidas",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Autenticar usuario
        user = authenticate(username=user_obj.username, password=password)

        if not user:
            return error_response(
                "Credenciales inválidas",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Verificar si el correo fue confirmado
        if not user.is_verified:
            return error_response(
                "Debes verificar tu correo antes de iniciar sesión",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        # Generar tokens JWT
        refresh = RefreshToken.for_user(user)

        return success_response(
            message="Inicio de sesión exitoso",
            data={
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status_code=status.HTTP_200_OK,
        )


class SendVerificationCodeView(generics.GenericAPIView):
    """
    Envía código de verificación al email
    - Reenvío de código si el usuario no lo recibió
    """

    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")

        if not email:
            return error_response(
                "El email es obligatorio",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return error_response(
                "Usuario no encontrado",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        # Generar nuevo código
        code = generate_verification_code()
        user.verification_code = str(code)
        user.save()

        # Enviar correo
        send_mail(
            "Código de verificación",
            f"Tu código de verificación es: {code}",
            None,
            [email],
        )

        return success_response(
            message="Código de verificación enviado al correo",
            status_code=status.HTTP_200_OK,
        )


class VerifyCodeView(generics.GenericAPIView):
    """
    Verifica el código enviado al correo
    - Activa el usuario (is_verified=True)
    """

    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")
        code = request.data.get("code")

        if not email or not code:
            return error_response(
                "Email y código son obligatorios",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(email=email, verification_code=code)
        except User.DoesNotExist:
            return error_response(
                "Código inválido",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Activar usuario
        user.is_verified = True
        user.verification_code = None
        user.save()

        return success_response(
            message="Usuario verificado correctamente",
            status_code=status.HTTP_200_OK,
        )


class SendResetPasswordCodeView(generics.GenericAPIView):
    """
    Envía código para recuperación de contraseña
    """

    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")

        if not email:
            return error_response(
                "El email es obligatorio",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return error_response(
                "Usuario no encontrado",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        # Generar código de recuperación
        code = generate_verification_code()
        user.reset_code = str(code)
        user.save()

        send_mail(
            "Recuperación de contraseña",
            f"Tu código para restablecer contraseña es: {code}",
            None,
            [email],
        )

        return success_response(
            message="Código de recuperación enviado al correo",
            status_code=status.HTTP_200_OK,
        )


class ResetPasswordView(generics.GenericAPIView):
    """
    Restablecer contraseña con código
    - Valida código
    - Actualiza la contraseña
    """

    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")
        code = request.data.get("code")
        new_password = request.data.get("new_password")

        if not email or not code or not new_password:
            return error_response(
                "Email, código y nueva contraseña son obligatorios",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(email=email, reset_code=code)
        except User.DoesNotExist:
            return error_response(
                "Código inválido",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Cambiar contraseña
        user.set_password(new_password)
        user.reset_code = None
        user.save()

        return success_response(
            message="Contraseña actualizada correctamente",
            status_code=status.HTTP_200_OK,
        )

class LogoutView(APIView):
    """
    Cierra sesión invalidando el refresh token (blacklist)
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")

        if not refresh_token:
            return error_response(
                "Refresh token es obligatorio",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception:
            return error_response(
                "Token inválido o ya fue invalidado",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        return success_response(
            message="Sesión cerrada correctamente",
            status_code=status.HTTP_200_OK,
        )