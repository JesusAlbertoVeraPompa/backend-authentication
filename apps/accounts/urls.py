# apps/accounts/urls.py

from django.urls import path
from .views import (
    LogoutView,
    RegisterView,
    CustomTokenObtainPairView,
    SendCodeView,
    VerifyEmailView,
    RequestPasswordResetView,
    ConfirmPasswordResetView,
    GoogleLoginView,
)

urlpatterns = [
    # -------------------------
    # REGISTRO
    # -------------------------
    path("register/", RegisterView.as_view(), name="register"),
    # -------------------------
    # LOGIN JWT
    # -------------------------
    path("login/", CustomTokenObtainPairView.as_view(), name="login"),
    # -------------------------
    # LOGIN CON GOOGLE
    # -------------------------
    path("google/", GoogleLoginView.as_view(), name="google_login"),
    # -------------------------
    # LOGOUT
    # -------------------------
    path("logout/", LogoutView.as_view(), name="logout"),
    # -------------------------
    # ENVIO DE CODIGO
    # -------------------------
    path("send-code/", SendCodeView.as_view(), name="send-code"),
    # -------------------------
    # VERIFICACIÓN DE EMAIL
    # -------------------------
    path("verify-code/", VerifyEmailView.as_view(), name="verify-code"),
    # -------------------------
    # RECUPERACIÓN DE PASSWORD
    # -------------------------
    path(
        "send-reset-code/",
        RequestPasswordResetView.as_view(),
        name="send-reset-code",
    ),
    path(
        "reset-password/",
        ConfirmPasswordResetView.as_view(),
        name="reset-password",
    ),
]
