import random
from django.utils import timezone
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth import get_user_model
from django.db import transaction
from django.conf import settings
from django.core.mail import send_mail

# Rest Framework
from rest_framework.views import APIView
from rest_framework import status, serializers
from rest_framework.permissions import IsAuthenticated

# JWT
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

# Google Auth
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

# Importación de tus respuestas personalizadas
from apps.core.utils.responses import success_response, error_response
from .throttles import LoginThrottle

User = get_user_model()

# =====================================================
# FUNCIÓN AUXILIAR PARA GENERAR CÓDIGOS NUMÉRICOS
# =====================================================


def generate_numeric_code(length=6):
    """Genera un código de N dígitos para verificaciones"""
    return "".join(str(random.randint(0, 9)) for _ in range(length))


# =====================================================
# REGISTRO DE USUARIO
# =====================================================


class RegisterView(APIView):
    """Maneja la creación de nuevos usuarios y envío de código inicial"""

    @transaction.atomic  # Asegura que si algo falla, no se cree el usuario a medias
    def post(self, request):
        email = request.data.get("email")
        password = request.data.get("password")

        # Validación de campos obligatorios
        if not email or not password:
            return error_response(
                "Email y password son requeridos",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Verificar si el usuario ya existe para evitar duplicados
        if User.objects.filter(email=email).exists():
            return error_response(
                "El usuario ya existe", status_code=status.HTTP_400_BAD_REQUEST
            )

        # Crear el usuario
        user = User.objects.create_user(username=email, email=email, password=password)

        # Generar código de verificación aleatorio
        raw_code = generate_numeric_code()

        # Guardar el hash del código (por seguridad) y la fecha de creación
        user.verification_code = make_password(raw_code)
        user.verification_code_created_at = timezone.now()
        user.save()

        # Envío real de correo electrónico
        try:
            send_mail(
                subject="Verifica tu cuenta",
                message=f"Tu código de verificación es: {raw_code}",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )
        except Exception as e:
            # Si falla el envío de correo, podrías imprimir el error para debug
            print(f"Error enviando correo: {str(e)}")
            # Opcionalmente devolver un error si el correo es crítico
            # return error_response("Error al enviar el email de verificación", 500)

        return success_response(
            message="Usuario creado. Revisa tu email para verificar.",
            status_code=status.HTTP_201_CREATED,
        )


# =====================================================
# ENVIO DE CODIGO DE VERIFICACIÓN
# =====================================================


class SendCodeView(APIView):
    """Permite al usuario solicitar un nuevo código si el anterior expiró"""

    def post(self, request):
        email = request.data.get("email")

        if not email:
            return error_response(
                "Email requerido", status_code=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return error_response(
                "Usuario no encontrado", status_code=status.HTTP_404_NOT_FOUND
            )

        # Generar y hashear nuevo código
        raw_code = generate_numeric_code()
        user.verification_code = make_password(raw_code)
        user.verification_code_created_at = timezone.now()
        user.save()

        # Envío real de correo electrónico
        try:
            send_mail(
                subject="Verifica tu cuenta",
                message=f"Tu código de verificación es: {raw_code}",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )
        except Exception as e:
            # Si falla el envío de correo, podrías imprimir el error para debug
            print(f"Error enviando correo: {str(e)}")
            # Opcionalmente devolver un error si el correo es crítico
            # return error_response("Error al enviar el email de verificación", 500)

        return success_response(
            message="Código enviado exitosamente.",
            status_code=status.HTTP_200_OK,
        )


# =====================================================
# VERIFICAR EMAIL
# =====================================================


class VerifyEmailView(APIView):
    """Compara el código ingresado por el usuario con el guardado en BD"""

    def post(self, request):
        email = request.data.get("email")
        code = request.data.get("code")

        if not email or not code:
            return error_response(
                "Email y código son requeridos", status_code=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return error_response(
                "Usuario no encontrado", status_code=status.HTTP_404_NOT_FOUND
            )

        # Validar si el código ha expirado (usando el método del modelo)
        if user.verification_code_is_expired():
            return error_response(
                "El código expiró", status_code=status.HTTP_400_BAD_REQUEST
            )

        # Validar si el código es correcto comparando el hash
        if not check_password(code, user.verification_code):
            return error_response(
                "Código inválido", status_code=status.HTTP_400_BAD_REQUEST
            )

        # Activar usuario y limpiar campos de verificación
        user.is_verified = True
        user.verification_code = None
        user.verification_code_created_at = None
        user.save()

        return success_response(
            message="Email verificado correctamente.",
            status_code=status.HTTP_200_OK,
        )

# =====================================================
# SOLICITAR RESET DE PASSWORD
# =====================================================


class RequestPasswordResetView(APIView):
    """Genera un código de recuperación para usuarios que olvidaron su clave"""

    def post(self, request):
        email = request.data.get("email")

        if not email:
            return error_response(
                "Email requerido", status_code=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(email=email)
            # Si existe, generamos el código
            raw_code = generate_numeric_code()
            user.reset_code = make_password(raw_code)
            user.reset_code_created_at = timezone.now()
            user.save()
            # ENVÍO REAL DE CORREO DE RECUPERACIÓN
            try:
                send_mail(
                    subject="Recuperación de contraseña",
                    message=f"Tu código para restablecer tu contraseña es: {raw_code}. Si no solicitaste este cambio, ignora este correo.",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                    fail_silently=False,
                )
            except Exception as e:
                print(f"Error enviando correo de reset: {str(e)}")
        except User.DoesNotExist:
            # Por seguridad, no decimos si el email existe o no
            pass

        return success_response(
            message="Si el usuario existe, se enviará un código de recuperación.",
            status_code=status.HTTP_200_OK,
        )

# =====================================================
# CONFIRMAR RESET DE PASSWORD
# =====================================================


class ConfirmPasswordResetView(APIView):
    """Procesa el cambio de contraseña tras validar el código de recuperación"""

    def post(self, request):
        email = request.data.get("email")
        code = request.data.get("code")
        new_password = request.data.get("new_password")

        if not email or not code or not new_password:
            return error_response(
                "Datos incompletos", status_code=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return error_response(
                "Usuario no encontrado", status_code=status.HTTP_404_NOT_FOUND
            )

        # Verificación de expiración y validez del código de reset
        if user.reset_code_is_expired():
            return error_response(
                "El código expiró", status_code=status.HTTP_400_BAD_REQUEST
            )

        if not check_password(code, user.reset_code):
            return error_response(
                "Código inválido", status_code=status.HTTP_400_BAD_REQUEST
            )

        # Cambiar contraseña y limpiar códigos
        user.set_password(new_password)
        user.reset_code = None
        user.reset_code_created_at = None
        user.save()

        return success_response(
                message="Contraseña actualizada correctamente.",
                status_code=status.HTTP_200_OK,
            )



# =====================================================
# LOGIN CON GOOGLE
# =====================================================


class GoogleLoginView(APIView):
    """Autenticación mediante Google OAuth2"""

    def post(self, request):
        token = request.data.get("id_token")

        if not token:
            return error_response(
                "id_token es requerido", status_code=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Validar el token directamente con los servidores de Google
            idinfo = id_token.verify_oauth2_token(
                token,
                google_requests.Request(),
                settings.SOCIALACCOUNT_PROVIDERS["google"]["APP"]["client_id"],
            )

            # Validar el emisor del token
            if idinfo["iss"] not in [
                "accounts.google.com",
                "https://accounts.google.com",
            ]:
                raise ValueError("Issuer inválido")

            email = idinfo.get("email")
            if not email:
                return error_response(
                    "Google no retornó email", status_code=status.HTTP_400_BAD_REQUEST
                )

            # Obtener usuario o crearlo si es nuevo
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "username": email,
                    "is_verified": True,  # Si viene de Google, ya está verificado
                },
            )

            # Forzar verificación si ya existía pero no estaba verificado
            if not user.is_verified:
                user.is_verified = True
                user.save()

            # Generar tokens JWT para nuestra app
            refresh = RefreshToken.for_user(user)
            data = {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            }
            return success_response("Login exitoso", data=data)

        except ValueError as e:
            print(f"Error detallado de Google: {str(e)}")
            return error_response(
                "Token de Google inválido", status_code=status.HTTP_400_BAD_REQUEST
            )
        # AGREGA ESTE BLOQUE JUSTO DEBAJO:
        except Exception as e:
            print(f"--- ERROR CRÍTICO EN GOOGLE LOGIN ---")
            print(f"Tipo de error: {type(e).__name__}")
            print(f"Mensaje: {str(e)}")
            return error_response(
                f"Error interno: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# =====================================================
# LOGIN TRADICIONAL (JWT)
# =====================================================


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Serializador que añade una validación extra: El usuario debe estar verificado"""

    def validate(self, attrs):
        data = super().validate(attrs)
        if not self.user.is_verified:
            raise serializers.ValidationError(
                "Debes verificar tu email antes de iniciar sesión."
            )
        return data


class CustomTokenObtainPairView(TokenObtainPairView):
    """Vista de Login que usa el serializador personalizado y aplica Throttling"""

    serializer_class = CustomTokenObtainPairSerializer
    throttle_classes = [LoginThrottle]

    def post(self, request, *args, **kwargs):
        # El método super().post realiza la autenticación estándar
        response = super().post(request, *args, **kwargs)

        # Adaptamos la respuesta al formato unificado
        return success_response(
            message="Login exitoso",
            data={
                "access": response.data["access"],
                "refresh": response.data["refresh"],
            },
        )


# =====================================================
# LOGOUT
# =====================================================


class LogoutView(APIView):
    """Invalida el refresh token del usuario (Blacklist)"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            if not refresh_token:
                return error_response("Refresh token es requerido")

            token = RefreshToken(refresh_token)
            token.blacklist()  # Agrega el token a la lista negra

            return success_response("Logout exitoso")
        except Exception:
            return error_response(
                "Token inválido o ya expirado", status_code=status.HTTP_400_BAD_REQUEST
            )
