from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    CustomTokenRefreshView,
    LoginView,
    LogoutView,
    RequestPasswordResetView,
    RegisterUserView,
    ResetPasswordView,
    RequestEmailOTPView,
    VerifyEmailOTPView,
)

urlpatterns = [
    path("request-email-verification-otp/", RequestEmailOTPView.as_view()),
    path("verify-email-otp/", VerifyEmailOTPView.as_view()),
    path("request-password-reset/", RequestPasswordResetView.as_view()),
    path("reset-password/", ResetPasswordView.as_view()),
    path("register/", RegisterUserView.as_view()),
    path("login/", LoginView.as_view()),
    path("token/refresh/", CustomTokenRefreshView.as_view(), name="token_refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
    # path("test-dashboard/", TestDashboardView.as_view()),
]
