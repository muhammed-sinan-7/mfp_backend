# apps/authentication/api/views.py

from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework.exceptions import Throttled
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from apps.audit.models import AuditLog
from apps.audit.services import log_event
from apps.authentication.api.serializers import (
    LoginSerializer,
    OTPRequestSerializer,
    OTPVerifySerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegistrationSerializer,
)
from apps.authentication.exceptions import (
    OTPCooldownException,
    OTPInvalidException,
    OTPLockedException,
)
from apps.authentication.services.auth_service import verify_email
from apps.authentication.services.otp_service import (
    create_otp,
    verify_otp,
)
from apps.authentication.services.throttle_service import throttle_request
from apps.organizations.models import OrganizationMember

User = get_user_model()


def get_refresh_cookie_max_age(refresh_token):
    remember_me = bool(refresh_token.get("remember_me"))
    lifetime = (
        settings.REMEMBER_ME_REFRESH_TOKEN_LIFETIME
        if remember_me
        else settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"]
    )
    return int(lifetime.total_seconds())


def set_refresh_cookie(response, refresh_token):
    response.set_cookie(
        key=settings.AUTH_REFRESH_COOKIE_NAME,
        value=str(refresh_token),
        max_age=get_refresh_cookie_max_age(refresh_token),
        httponly=True,
        secure=settings.AUTH_REFRESH_COOKIE_SECURE,
        samesite=settings.AUTH_REFRESH_COOKIE_SAMESITE,
        domain=settings.AUTH_REFRESH_COOKIE_DOMAIN,
        path=settings.AUTH_REFRESH_COOKIE_PATH,
    )


def clear_refresh_cookie(response):
    response.delete_cookie(
        key=settings.AUTH_REFRESH_COOKIE_NAME,
        domain=settings.AUTH_REFRESH_COOKIE_DOMAIN,
        path=settings.AUTH_REFRESH_COOKIE_PATH,
        samesite=settings.AUTH_REFRESH_COOKIE_SAMESITE,
    )


# ---------------- REGISTER ---------------- #


class RegisterUserView(APIView):
    def post(self, request):
        serializer = RegistrationSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        serializer.save()

        return Response(
            {"message": "Registration successful. Verify your email."},
            status=201,
        )


# ---------------- OTP REQUEST ---------------- #


class RequestEmailOTPView(APIView):
    def post(self, request):
        serializer = OTPRequestSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        email = serializer.validated_data["email"]

        try:
            throttle_request(request, "otp_request", email)

            user = User.objects.get(email=email)
            create_otp(user=user, purpose="email_verification")

        except User.DoesNotExist:
            pass  # prevent enumeration

        except OTPCooldownException:
            return Response(
                {"error": "Please wait before requesting another OTP"},
                status=429,
            )

        except Throttled:
            return Response(
                {"error": "Too many requests"},
                status=429,
            )

        return Response({"message": "OTP sent"}, status=200)


class RequestPasswordResetView(APIView):
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        email = serializer.validated_data["email"]

        try:
            throttle_request(request, "otp_request", email)
            user = User.objects.get(email=email)
            create_otp(user=user, purpose="password_reset")
        except User.DoesNotExist:
            pass  # prevent account enumeration
        except OTPCooldownException:
            return Response(
                {"error": "Please wait before requesting another OTP"},
                status=429,
            )
        except Throttled:
            return Response({"error": "Too many requests"}, status=429)

        return Response(
            {"message": "If the account exists, a reset OTP has been sent."},
            status=200,
        )


class ResetPasswordView(APIView):
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        email = serializer.validated_data["email"]
        otp = serializer.validated_data["otp"]
        new_password = serializer.validated_data["new_password"]

        try:
            throttle_request(request, "otp_verify", email)
            user = User.objects.get(email=email)
            verify_otp(user, "password_reset", otp)
            user.set_password(new_password)
            user.save(update_fields=["password"])
        except User.DoesNotExist:
            return Response({"error": "Invalid reset code"}, status=400)
        except OTPLockedException:
            return Response({"error": "Too many attempts", "locked": True}, status=400)
        except OTPInvalidException as e:
            remaining = str(e) if str(e) else None
            return Response(
                {"error": "Invalid reset code", "attempts_left": remaining},
                status=400,
            )
        except Throttled:
            return Response({"error": "Too many requests"}, status=429)

        return Response(
            {"message": "Password reset successful. Please login with your new password."},
            status=200,
        )


class CustomTokenRefreshView(TokenRefreshView):
    def post(self, request, *args, **kwargs):
        refresh_token = request.COOKIES.get(settings.AUTH_REFRESH_COOKIE_NAME)
        if not refresh_token:
            return Response({"detail": "Refresh token missing"}, status=401)

        if hasattr(request.data, "_mutable"):
            request.data._mutable = True
        request.data["refresh"] = refresh_token
        response = super().post(request, *args, **kwargs)

        # ⚠️ user not available here → log minimal info
        if response.status_code == 200:
            new_refresh = response.data.pop("refresh", None)
            if new_refresh:
                rotated_refresh = RefreshToken(new_refresh)
                try:
                    previous_refresh = RefreshToken(refresh_token)
                    if previous_refresh.get("remember_me"):
                        rotated_refresh["remember_me"] = True
                        rotated_refresh.set_exp(
                            lifetime=settings.REMEMBER_ME_REFRESH_TOKEN_LIFETIME
                        )
                except Exception:
                    pass
                set_refresh_cookie(response, rotated_refresh)

            log_event(
                actor=None,
                organization=None,
                action=AuditLog.ActionType.TOKEN_REFRESH,
                request=request,
            )

        return response


class VerifyEmailOTPView(APIView):
    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        email = serializer.validated_data["email"]
        otp = serializer.validated_data["otp"]

        try:
            throttle_request(request, "otp_verify", email)

            user = User.objects.get(email=email)

            verify_otp(user, "email_verification", otp)
            verify_email(user)

            refresh = RefreshToken.for_user(user)

        except User.DoesNotExist:
            return Response({"error": "Invalid OTP"}, status=400)

        except OTPLockedException:
            return Response({"error": "Too many attempts", "locked": True}, status=400)

        except OTPInvalidException as e:
            remaining = str(e) if str(e) else None

            return Response(
                {
                    "error": "Invalid OTP",
                    "attempts_left": remaining,
                },
                status=400,
            )

        except Throttled:
            return Response({"error": "Too many requests"}, status=429)

        response = Response(
            {
                "message": "Email verified",
                "access": str(refresh.access_token),
                "id": str(user.id),
                "email": user.email,
            },
            status=200,
        )
        set_refresh_cookie(response, refresh)
        return response


class LoginView(APIView):
    def post(self, request):
        serializer = LoginSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        email = serializer.validated_data["email"]
        password = serializer.validated_data["password"]
        remember_me = serializer.validated_data.get("remember_me", False)

        try:
            throttle_request(request, "login", email)

            user = User.objects.get(email=email)
            if not user.check_password(password):
                return Response({"error": "Invalid credentials"}, status=401)

            if not user.is_email_verified:
                try:
                    create_otp(user=user, purpose="email_verification")
                except OTPCooldownException:
                    pass

                return Response(
                    {
                        "requires_verification": True,
                        "email": user.email,
                        "message": "Please verify your email",
                    },
                    status=200,
                )

            refresh = RefreshToken.for_user(user)
            if remember_me:
                refresh["remember_me"] = True
                refresh.set_exp(lifetime=settings.REMEMBER_ME_REFRESH_TOKEN_LIFETIME)

        except User.DoesNotExist:
            return Response({"error": "Invalid credentials"}, status=401)

        except Throttled:
            return Response({"error": "Too many requests"}, status=429)

        org = (
            OrganizationMember.objects.select_related("organization")
            .filter(user=user, is_deleted=False)
            .first()
        )
        response = Response(
            {
                "access": str(refresh.access_token),
                "id": str(user.id),
                "email": user.email,
                "org_id": org.organization.id if org else None,
                "org_name": org.organization.name if org else None,
                "role": org.role if org else None,
            }
        )
        set_refresh_cookie(response, refresh)
        return response


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org = (
            OrganizationMember.objects.select_related("organization")
            .filter(user=request.user, is_deleted=False)
            .first()
        )

        return Response(
            {
                "id": str(request.user.id),
                "email": request.user.email,
                "is_authenticated": True,
                "org_id": org.organization.id if org else None,
                "org_name": org.organization.name if org else None,
                "role": org.role if org else None,
            }
        )


class LogoutView(APIView):
    def post(self, request):
        try:
            refresh_token = request.COOKIES.get(settings.AUTH_REFRESH_COOKIE_NAME)

            if not refresh_token:
                response = Response({"message": "Logged out successfully"}, status=200)
                clear_refresh_cookie(response)
                return response

            token = RefreshToken(refresh_token)
            token.blacklist()

            response = Response({"message": "Logged out successfully"}, status=200)
            clear_refresh_cookie(response)
            return response

        except Exception:
            response = Response({"error": "Invalid token"}, status=400)
            clear_refresh_cookie(response)
            return response
