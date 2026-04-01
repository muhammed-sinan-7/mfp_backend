from django.urls import path

from .views import (
    LoginView,
    LogoutView,
    MeView,
    RequestPasswordResetView,
    RegisterUserView,
    ResetPasswordView,
    RequestEmailOTPView,
    SafeTokenRefreshView,
    VerifyEmailOTPView,
)

urlpatterns = [
    path("request-email-verification-otp/", RequestEmailOTPView.as_view()),
    path("verify-email-otp/", VerifyEmailOTPView.as_view()),
    path("request-password-reset/", RequestPasswordResetView.as_view()),
    path("reset-password/", ResetPasswordView.as_view()),
    path("register/", RegisterUserView.as_view()),
    path("login/", LoginView.as_view()),
    path("me/", MeView.as_view(), name="me"),
    path("token/refresh/", SafeTokenRefreshView.as_view(), name="token_refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
    # path("test-dashboard/", TestDashboardView.as_view()),
]
