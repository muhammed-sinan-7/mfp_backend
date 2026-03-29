# apps/authentication/api/views.py

from django.contrib.auth import get_user_model
from rest_framework import status
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
from apps.authentication.services.auth_service import (
    login_user,
    verify_email,
)
from apps.authentication.services.otp_service import (
    create_otp,
    verify_otp,
)
from apps.authentication.services.throttle_service import throttle_request
from apps.organizations.models import OrganizationMember

User = get_user_model()


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
        response = super().post(request, *args, **kwargs)

        # ⚠️ user not available here → log minimal info
        if response.status_code == 200:
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

        return Response(
            {
                "message": "Email verified",
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=200,
        )


class LoginView(APIView):
    def post(self, request):
        serializer = LoginSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        email = serializer.validated_data["email"]
        password = serializer.validated_data["password"]

        try:
            throttle_request(request, "login", email)

            user = User.objects.get(email=email)
            print("LOGIN EMAIL:", email)
            print("USER FOUND:", user.id, user.email)
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

        except User.DoesNotExist:
            return Response({"error": "Invalid credentials"}, status=401)

        except Throttled:
            return Response({"error": "Too many requests"}, status=429)

        org = (
            OrganizationMember.objects.select_related("organization")
            .filter(user=user, is_deleted=False)
            .first()
        )
        memberships = OrganizationMember.objects.filter(user=user)
        print("ALL MEMBERSHIPS:", list(memberships.values()))

        active_memberships = memberships.filter(is_deleted=False)
        print("ACTIVE MEMBERSHIPS:", list(active_memberships.values()))

        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "org_id": org.organization.id if org else None,
                "org_name": org.organization.name if org else None,
                "role": org.role if org else None,
            }
        )


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")

            if not refresh_token:
                return Response({"error": "Refresh token required"}, status=400)

            token = RefreshToken(refresh_token)
            token.blacklist()

            return Response({"message": "Logged out successfully"}, status=200)

        except Exception:
            return Response({"error": "Invalid token"}, status=400)
