from django.db import transaction
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.models import AuditLog
from apps.audit.services import log_event
from apps.industries.api.serializers import IndustrySerializer
from apps.industries.models import Industry
from apps.organizations.api.serializers import OrganizationSerializer
from apps.organizations.mixins import OrganizationContextMixin
from apps.organizations.models import Organization, OrganizationMember
from apps.organizations.permissions import HasOrganization, IsAdminOrOwner, IsOwner

from .serializers import OrganizationCreateSerializer


class CreateOrganizationView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        user = request.user

        if OrganizationMember.objects.filter(user=user).exists():
            return Response(
                {"error": "User already belongs to an organization."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = OrganizationCreateSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        organization = serializer.save()

        OrganizationMember.objects.create(
            organization=organization, user=user, role="OWNER"
        )
        log_event(
            actor=request.user,
            organization=organization,
            action=AuditLog.ActionType.ORG_CREATED,
            request=request,
            target_model="Organization",
            target_id=str(organization.id),
            metadata={"organization_name": organization.name},
        )

        return Response(
            {
                "message": "Organization created successfully",
                "organization_id": organization.id,
            },
            status=status.HTTP_201_CREATED,
        )


class DeleteOrganizationView(APIView):
    permission_classes = [IsAuthenticated, HasOrganization, IsOwner]

    def delete(self, request):
        organization = request.organization

        log_event(
            actor=request.user,
            organization=organization,
            action=AuditLog.ActionType.ORG_DELETED,
            request=request,
            target_model="Organization",
            target_id=str(organization.id),
            metadata={"organization_name": organization.name},
        )

        organization.delete()
        return Response({"message": "Organization deleted"})


class ListMembersView(OrganizationContextMixin, APIView):
    permission_classes = [IsAuthenticated, HasOrganization, IsAdminOrOwner]

    def get(self, request):
        members = OrganizationMember.objects.filter(
            organization=request.organization, is_deleted=False
        )

        data = [{"id": m.id, "email": m.user.email, "role": m.role} for m in members]

        return Response(data)


class RemoveMemberView(APIView):
    permission_classes = [IsAuthenticated, HasOrganization, IsOwner]

    @transaction.atomic
    def delete(self, request, member_id):
        try:
            member = OrganizationMember.objects.get(
                id=member_id, organization=request.organization, is_deleted=False
            )
        except OrganizationMember.DoesNotExist:
            return Response({"error": "Member not found"}, status=404)

        if member.role == "OWNER":
            active_owner_count = OrganizationMember.objects.filter(
                organization=request.organization,
                role="OWNER",
            ).count()

            if active_owner_count <= 1:
                return Response(
                    {"error": "You are the owner. Assign a new owner before leaving."},
                    status=400,
                )

        log_event(
            actor=request.user,
            organization=request.organization,
            action=AuditLog.ActionType.MEMBER_REMOVED,
            request=request,
            target_model="OrganizationMember",
            target_id=str(member.id),
            metadata={"member_email": member.user.email},
        )
        member.delete(user=request.user)
        return Response({"message": "Member removed"})


class ChangeRoleView(APIView):
    permission_classes = [IsAuthenticated, HasOrganization, IsOwner]

    def patch(self, request, member_id):
        new_role = request.data.get("role")

        if new_role not in ["ADMIN", "EDITOR", "VIEWER"]:
            return Response({"error": "Invalid role"}, status=400)

        try:
            member = OrganizationMember.objects.get(
                id=member_id, organization=request.organization, is_deleted=False
            )
        except OrganizationMember.DoesNotExist:
            return Response({"error": "Member not found"}, status=404)

        if member.role == "OWNER":
            return Response({"error": "Cannot change owner role"}, status=400)

        member.role = new_role
        member.save()
        log_event(
            actor=request.user,
            organization=request.organization,
            action=AuditLog.ActionType.ROLE_CHANGED,
            request=request,
            target_model="OrganizationMember",
            target_id=str(member.id),
            metadata={
                "member_email": member.user.email,
                "new_role": new_role,
            },
        )

        return Response({"message": "Role updated"})


class TransferOwnershipView(APIView):
    permission_classes = [IsAuthenticated, HasOrganization, IsOwner]

    @transaction.atomic
    def patch(self, request, member_id):
        try:
            new_owner = OrganizationMember.objects.get(
                id=member_id,
                organization=request.organization,
                is_deleted=False,
            )
        except OrganizationMember.DoesNotExist:
            return Response({"error": "Member not found"}, status=404)

        if new_owner.role == "OWNER":
            return Response({"error": "User is already owner"}, status=400)

        try:
            current_owner = OrganizationMember.objects.get(
                organization=request.organization,
                role="OWNER",
                is_deleted=False,
            )
        except OrganizationMember.DoesNotExist:
            return Response({"error": "No active owner found"}, status=400)

        # Transfer ownership
        new_owner.role = "OWNER"
        new_owner.save(update_fields=["role"])

        current_owner.role = "ADMIN"
        current_owner.save(update_fields=["role"])

        # Audit log
        log_event(
            actor=request.user,
            organization=request.organization,
            action=AuditLog.ActionType.ROLE_CHANGED,
            request=request,
            target_model="OrganizationMember",
            target_id=str(new_owner.id),
            metadata={
                "previous_owner": current_owner.user.email,
                "new_owner": new_owner.user.email,
                "action": "OWNER_TRANSFERRED",
            },
        )

        return Response({"message": "Ownership transferred successfully"})


class OrganizationSettingsView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        membership = (
            OrganizationMember.objects.select_related("organization__industry")
            .filter(user=request.user, is_deleted=False)
            .first()
        )

        if not membership:
            return Response({"error": "No organization"}, status=404)

        org = membership.organization
        serializer = OrganizationSerializer(org, context={"request": request})

        return Response(serializer.data)

    def patch(self, request):
        membership = (
            OrganizationMember.objects.select_related("organization__industry")
            .filter(user=request.user, is_deleted=False)
            .first()
        )

        if not membership:
            return Response({"error": "No organization"}, status=404)

        org = membership.organization

        serializer = OrganizationSerializer(
            org, data=request.data, partial=True, context={"request": request}
        )

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)

        return Response(serializer.errors, status=400)
