# apps/accounts/urls.py

from django.urls import path
from .views import (
    RegisterView,
    LoginView,
    SendVerificationCodeView,
    VerifyCodeView,
    SendResetPasswordCodeView,
    ResetPasswordView,
    LogoutView,
    GoogleLoginView,
)

urlpatterns = [
    # Registro
    path("register/", RegisterView.as_view(), name="register"),
    # Login
    path("login/", LoginView.as_view(), name="login"),
    # Google Login
    path('google/', GoogleLoginView.as_view(), name='google_login'),
    # Logout
    path("logout/", LogoutView.as_view(), name="logout"),
    # Verificación de usuario
    path("send-code/", SendVerificationCodeView.as_view(), name="send-code"),
    path("verify-code/", VerifyCodeView.as_view(), name="verify-code"),
    # Recuperación de contraseña
    path(
        "send-reset-code/", SendResetPasswordCodeView.as_view(), name="send-reset-code"
    ),
    path("reset-password/", ResetPasswordView.as_view(), name="reset-password"),
]
