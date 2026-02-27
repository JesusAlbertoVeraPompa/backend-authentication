# apps/accounts/tests.py

from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model

User = get_user_model()


class AuthFlowTests(APITestCase):
    """
    Tests del flujo completo de autenticación:
    - Registro
    - Login
    - Verificación por código
    - Reset de contraseña
    """

    def setUp(self):
        User.objects.all().delete()
        self.register_url = "/api/auth/register/"
        self.login_url = "/api/auth/login/"
        self.send_code_url = "/api/auth/send-code/"
        self.verify_code_url = "/api/auth/verify-code/"
        self.send_reset_url = "/api/auth/send-reset-code/"
        self.reset_password_url = "/api/auth/reset-password/"

        self.user_data = {
            "username": "testuser",
            "email": "test@email.com",
            "password": "12345678",
        }

    # ---------------------------------------------------------
    # REGISTRO
    # ---------------------------------------------------------
    def test_user_registration(self):
        """Debe registrar un usuario correctamente"""
        response = self.client.post(self.register_url, self.user_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(User.objects.count(), 1)

    # ---------------------------------------------------------
    # LOGIN
    # ---------------------------------------------------------

    def test_user_login(self):
        """Debe hacer login y retornar tokens JWT"""
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

    # ---------------------------------------------------------
    # ENVÍO DE CÓDIGO DE VERIFICACIÓN
    # ---------------------------------------------------------
    def test_send_verification_code(self):
        """Debe enviar código de verificación"""
        User.objects.create_user(**self.user_data)

        response = self.client.post(
            self.send_code_url, {"email": "test@email.com"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user = User.objects.get(email="test@email.com")
        self.assertIsNotNone(user.verification_code)

    # ---------------------------------------------------------
    # VERIFICAR CÓDIGO
    # ---------------------------------------------------------
    def test_verify_code(self):
        """Debe verificar usuario con código correcto"""
        user = User.objects.create_user(**self.user_data)
        user.verification_code = "1234"
        user.save()

        response = self.client.post(
            self.verify_code_url,
            {"email": "test@email.com", "code": "1234"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertTrue(user.is_verified)

    # ---------------------------------------------------------
    # RESET PASSWORD
    # ---------------------------------------------------------
    def test_reset_password(self):
        """Debe cambiar la contraseña usando código"""
        user = User.objects.create_user(**self.user_data)
        user.reset_code = "5678"
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

    # ---------------------------------------------------------
    # LOGOUT
    # ---------------------------------------------------------
    def test_user_logout(self):
        """Debe cerrar sesión invalidando el refresh token"""
        user = User.objects.create_user(**self.user_data)
        user.is_verified = True
        user.save()

        # Login primero
        login_response = self.client.post(
            self.login_url,
            {"email": "test@email.com", "password": "12345678"},
            format="json",
        )

        self.assertEqual(login_response.status_code, status.HTTP_200_OK)

        access = login_response.data["data"]["access"]
        refresh = login_response.data["data"]["refresh"]

        # Logout
        response = self.client.post(
            "/api/auth/logout/",
            {"refresh": refresh},
            HTTP_AUTHORIZATION=f"Bearer {access}",
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
