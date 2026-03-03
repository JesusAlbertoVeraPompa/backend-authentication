# apps/accounts/tests.py

"""
Test suite completo del sistema de autenticación.

Incluye pruebas de:
- Registro
- Login
- Bloqueo si no está verificado
- Envío de código de verificación
- Verificación de email
- Expiración de código
- Reset de contraseña
- Logout
- Throttling (anti brute force)
- Login con Google (mockeado)
"""

from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth.hashers import make_password

User = get_user_model()


class AuthFlowTests(APITestCase):

    def setUp(self):
        """
        Se ejecuta antes de cada test.
        Define URLs y datos base.
        """
        User.objects.all().delete()

        self.register_url = "/api/auth/register/"
        self.login_url = "/api/auth/login/"
        self.verify_url = "/api/auth/verify-code/"
        self.send_code_url = "/api/auth/send-code/"
        self.send_reset_url = "/api/auth/send-reset-code/"
        self.reset_password_url = "/api/auth/reset-password/"
        self.logout_url = "/api/auth/logout/"
        self.google_login_url = "/api/auth/google/"

        self.user_data = {
            "username": "testuser",
            "email": "test@email.com",
            "password": "12345678",
        }

    # =====================================================
    # REGISTRO
    # =====================================================

    def test_user_registration(self):
        """Debe registrar un usuario correctamente"""
        response = self.client.post(self.register_url, self.user_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(User.objects.count(), 1)

    # =====================================================
    # LOGIN
    # =====================================================

    def test_user_login_success(self):
        """Debe hacer login si el usuario está verificado"""
        user = User.objects.create_user(**self.user_data)
        user.is_verified = True
        user.save()

        response = self.client.post(
            self.login_url,
            {"email": "test@email.com", "password": "12345678"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data["data"])
        self.assertIn("refresh", response.data["data"])

    def test_login_blocked_if_not_verified(self):
        """No debe permitir login si no está verificado"""
        User.objects.create_user(**self.user_data)

        response = self.client.post(
            self.login_url,
            {"email": "test@email.com", "password": "12345678"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # =====================================================
    # ENVÍO DE CÓDIGO
    # =====================================================

    def test_send_verification_code(self):
        """Debe generar y guardar código de verificación"""
        User.objects.create_user(**self.user_data)

        response = self.client.post(
            self.send_code_url,
            {"email": "test@email.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user = User.objects.get(email="test@email.com")
        self.assertIsNotNone(user.verification_code)

    # =====================================================
    # VERIFICACIÓN
    # =====================================================

    def test_verify_code_success(self):
        """Debe verificar usuario con código válido"""
        user = User.objects.create_user(**self.user_data)
        user.verification_code = make_password("1234")
        user.verification_code_created_at = timezone.now()
        user.save()

        response = self.client.post(
            self.verify_url,
            {"email": "test@email.com", "code": "1234"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertTrue(user.is_verified)

    def test_verify_code_invalid(self):
        """Debe fallar si el código es incorrecto"""
        user = User.objects.create_user(**self.user_data)
        user.verification_code = make_password("1234")
        user.verification_code_created_at = timezone.now()
        user.save()

        response = self.client.post(
            self.verify_url,
            {"email": "test@email.com", "code": "9999"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_verify_code_expired(self):
        """Debe fallar si el código expiró"""
        user = User.objects.create_user(**self.user_data)
        user.verification_code = make_password("1234")
        user.verification_code_created_at = timezone.now() - timedelta(minutes=20)
        user.save()

        response = self.client.post(
            self.verify_url,
            {"email": "test@email.com", "code": "1234"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # =====================================================
    # RESET PASSWORD
    # =====================================================

    def test_reset_password_success(self):
        """Debe cambiar la contraseña usando código válido"""
        user = User.objects.create_user(**self.user_data)
        user.reset_code = make_password("5678")
        user.reset_code_created_at = timezone.now()
        user.save()

        response = self.client.post(
            self.reset_password_url,
            {
                "email": "test@email.com",
                "code": "5678",
                "new_password": "newpassword123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertTrue(user.check_password("newpassword123"))

    def test_reset_password_invalid_code(self):
        """Debe fallar si el código es incorrecto"""
        user = User.objects.create_user(**self.user_data)
        user.reset_code = make_password("5678")
        user.reset_code_created_at = timezone.now()
        user.save()

        response = self.client.post(
            self.reset_password_url,
            {
                "email": "test@email.com",
                "code": "0000",
                "new_password": "newpassword123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # =====================================================
    # LOGOUT
    # =====================================================

    def test_user_logout(self):
        """Debe cerrar sesión invalidando el refresh token"""
        user = User.objects.create_user(**self.user_data)
        user.is_verified = True
        user.save()

        login_response = self.client.post(
            self.login_url,
            {"email": "test@email.com", "password": "12345678"},
            format="json",
        )

        access = login_response.data["data"]["access"]
        refresh = login_response.data["data"]["refresh"]

        response = self.client.post(
            self.logout_url,
            {"refresh": refresh},
            HTTP_AUTHORIZATION=f"Bearer {access}",
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # =====================================================
    # THROTTLING
    # =====================================================

    def test_login_throttle(self):
        """Debe bloquear después de múltiples intentos fallidos"""
        for _ in range(6):
            response = self.client.post(
                self.login_url,
                {"email": "fake@email.com", "password": "wrong"},
                format="json",
            )

        self.assertEqual(response.status_code, 429)

    # =====================================================
    # GOOGLE LOGIN
    # =====================================================

    @patch("apps.accounts.views.id_token.verify_oauth2_token")
    def test_google_login(self, mock_verify):
        """Debe permitir login con Google válido"""

        mock_verify.return_value = {
            "email": "google@test.com",
            "iss": "accounts.google.com",
        }

        response = self.client.post(
            self.google_login_url,
            {"id_token": "fake-token"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data["data"])
