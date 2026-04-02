from django.contrib.auth import get_user_model
from django.db.models.deletion import ProtectedError
from django.db.models import Count, Q
from datetime import timedelta
from django.utils import timezone
from django.utils.text import slugify
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.models import AuditLog
from apps.industries.models import Industry
from apps.news.models import NewsSource
from apps.organizations.models import Organization, OrganizationMember
from apps.posts.models import Post
from apps.social_accounts.api.views import disconnect_social_account
from apps.social_accounts.models import SocialAccount
from common.pagination import StandardResultsSetPagination

from .permissions import IsPlatformAdmin
from .serializers import (
    AdminAuditLogSerializer,
    AdminOrganizationSerializer,
    AdminIndustrySerializer,
    AdminIndustryWriteSerializer,
    AdminNewsSourceSerializer,
    AdminNewsSourceWriteSerializer,
    AdminPostSerializer,
    AdminSocialAccountSerializer,
    AdminUserSerializer,
    AdminUserWriteSerializer,
)

User = get_user_model()


class AdminPaginationMixin:
    pagination_class = StandardResultsSetPagination

    def paginate(self, request, queryset, serializer_class):
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, view=self)
        serializer = serializer_class(page, many=True, context={"request": request})
        return paginator.get_paginated_response(serializer.data)


class AdminOverviewView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformAdmin]

    def get(self, request):
        now = timezone.now()
        payload = {
            "users": {
                "total": User.objects.count(),
                "active": User.objects.filter(is_active=True, is_deleted=False).count(),
                "staff": User.objects.filter(is_staff=True).count(),
            },
            "organizations": {
                "total": Organization.all_objects.count(),
                "active": Organization.objects.count(),
                "deleted": Organization.all_objects.filter(is_deleted=True).count(),
            },
            "posts": {
                "total": Post.objects.count(),
                "active": Post.objects.filter(is_deleted=False).count(),
                "deleted": Post.objects.filter(is_deleted=True).count(),
            },
            "social_accounts": {
                "total": SocialAccount.objects.count(),
                "active": SocialAccount.objects.filter(is_active=True).count(),
                "expired": SocialAccount.objects.filter(
                    token_expires_at__isnull=False,
                    token_expires_at__lt=now,
                ).count(),
            },
            "audit_logs": {
                "last_24h": AuditLog.objects.filter(
                    created_at__gte=now - timedelta(days=1)
                ).count()
            },
            "recent_users": AdminUserSerializer(
                User.objects.order_by("-created_at")[:5],
                many=True,
            ).data,
            "recent_organizations": AdminOrganizationSerializer(
                Organization.all_objects.order_by("-created_at")[:5],
                many=True,
                context={"request": request},
            ).data,
        }
        return Response(payload)


class AdminUserListCreateView(AdminPaginationMixin, APIView):
    permission_classes = [IsAuthenticated, IsPlatformAdmin]

    def get(self, request):
        query = request.query_params.get("q", "").strip()
        queryset = User.objects.all().order_by("-created_at")
        if query:
            queryset = queryset.filter(email__icontains=query)
        return self.paginate(request, queryset, AdminUserSerializer)

    def post(self, request):
        serializer = AdminUserWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            AdminUserSerializer(user).data,
            status=status.HTTP_201_CREATED,
        )


class AdminUserDetailView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformAdmin]

    def get_object(self, user_id):
        return User.objects.filter(id=user_id).first()

    def patch(self, request, user_id):
        user = self.get_object(user_id)
        if not user:
            return Response({"error": "User not found"}, status=404)

        serializer = AdminUserWriteSerializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(AdminUserSerializer(user).data)

    def delete(self, request, user_id):
        user = self.get_object(user_id)
        if not user:
            return Response({"error": "User not found"}, status=404)

        user.is_active = False
        user.is_deleted = True
        user.save(update_fields=["is_active", "is_deleted", "updated_at"])
        return Response({"message": "User deactivated"})


class AdminOrganizationListCreateView(AdminPaginationMixin, APIView):
    permission_classes = [IsAuthenticated, IsPlatformAdmin]

    def get(self, request):
        query = request.query_params.get("q", "").strip()
        include_deleted = request.query_params.get("include_deleted") == "1"
        queryset = (
            Organization.all_objects.all() if include_deleted else Organization.objects.all()
        ).select_related("industry").order_by("-created_at")
        if query:
            queryset = queryset.filter(name__icontains=query)
        return self.paginate(request, queryset, AdminOrganizationSerializer)

    def post(self, request):
        serializer = AdminOrganizationSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        name = serializer.validated_data["name"]
        base_slug = slugify(name)
        slug = base_slug
        counter = 1
        while Organization.all_objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1

        org = serializer.save(slug=slug)
        return Response(
            AdminOrganizationSerializer(org, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class AdminOrganizationDetailView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformAdmin]

    def get_object(self, organization_id):
        return Organization.all_objects.filter(id=organization_id).select_related("industry").first()

    def patch(self, request, organization_id):
        organization = self.get_object(organization_id)
        if not organization:
            return Response({"error": "Organization not found"}, status=404)

        serializer = AdminOrganizationSerializer(
            organization,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(AdminOrganizationSerializer(organization, context={"request": request}).data)

    def delete(self, request, organization_id):
        organization = self.get_object(organization_id)
        if not organization:
            return Response({"error": "Organization not found"}, status=404)

        organization.delete(user=request.user)
        return Response({"message": "Organization archived"})


class AdminOrganizationRestoreView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformAdmin]

    def post(self, request, organization_id):
        organization = Organization.all_objects.filter(id=organization_id).first()
        if not organization:
            return Response({"error": "Organization not found"}, status=404)
        organization.restore()
        return Response({"message": "Organization restored"})


class AdminSocialAccountListView(AdminPaginationMixin, APIView):
    permission_classes = [IsAuthenticated, IsPlatformAdmin]

    def get(self, request):
        query = request.query_params.get("q", "").strip()
        queryset = (
            SocialAccount.objects.select_related("organization")
            .annotate(active_targets=Count("publishing_targets"))
            .order_by("-created_at")
        )
        if query:
            queryset = queryset.filter(
                Q(account_name__icontains=query)
                | Q(organization__name__icontains=query)
                | Q(provider__icontains=query)
            )
        return self.paginate(request, queryset, AdminSocialAccountSerializer)


class AdminSocialAccountDetailView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformAdmin]

    def get_object(self, account_id):
        return SocialAccount.objects.select_related("organization").filter(id=account_id).first()

    def patch(self, request, account_id):
        account = self.get_object(account_id)
        if not account:
            return Response({"error": "Social account not found"}, status=404)

        account_name = request.data.get("account_name")
        is_active = request.data.get("is_active")

        if account_name is not None:
            account.account_name = account_name

        if is_active is not None:
            desired_active = str(is_active).lower() in ["1", "true", "yes"]
            if not desired_active and account.is_active:
                disconnect_social_account(account)
                account.refresh_from_db()
            else:
                account.is_active = desired_active
                account.save(update_fields=["is_active", "updated_at"])
        elif account_name is not None:
            account.save(update_fields=["account_name", "updated_at"])

        return Response(AdminSocialAccountSerializer(account).data)

    def delete(self, request, account_id):
        account = self.get_object(account_id)
        if not account:
            return Response({"error": "Social account not found"}, status=404)
        disconnect_social_account(account)
        return Response({"message": "Social account disconnected"})


class AdminPostListView(AdminPaginationMixin, APIView):
    permission_classes = [IsAuthenticated, IsPlatformAdmin]

    def get(self, request):
        query = request.query_params.get("q", "").strip()
        include_deleted = request.query_params.get("include_deleted") == "1"
        queryset = (
            Post.objects.select_related("organization", "created_by")
            .prefetch_related("platforms", "platforms__publishing_target")
            .order_by("-created_at")
        )
        if not include_deleted:
            queryset = queryset.filter(is_deleted=False)
        if query:
            queryset = queryset.filter(
                Q(organization__name__icontains=query)
                | Q(created_by__email__icontains=query)
                | Q(platforms__caption__icontains=query)
            ).distinct()
        return self.paginate(request, queryset, AdminPostSerializer)


class AdminPostDetailView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformAdmin]

    def get_object(self, post_id):
        return (
            Post.objects.select_related("organization", "created_by")
            .prefetch_related("platforms", "platforms__publishing_target")
            .filter(id=post_id)
            .first()
        )

    def patch(self, request, post_id):
        post = self.get_object(post_id)
        if not post:
            return Response({"error": "Post not found"}, status=404)

        should_delete = request.data.get("is_deleted")
        if should_delete is not None:
            if str(should_delete).lower() in ["1", "true", "yes"] and not post.is_deleted:
                post.is_deleted = True
                post.deleted_at = timezone.now()
            elif str(should_delete).lower() in ["0", "false", "no"] and post.is_deleted:
                post.is_deleted = False
                post.deleted_at = None
            post.save(update_fields=["is_deleted", "deleted_at", "updated_at"])

        return Response(AdminPostSerializer(post).data)

    def delete(self, request, post_id):
        post = self.get_object(post_id)
        if not post:
            return Response({"error": "Post not found"}, status=404)
        if not post.is_deleted:
            post.is_deleted = True
            post.deleted_at = timezone.now()
            post.save(update_fields=["is_deleted", "deleted_at", "updated_at"])
        return Response({"message": "Post moved to recycle state"})


class AdminPostRestoreView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformAdmin]

    def post(self, request, post_id):
        post = Post.objects.filter(id=post_id).first()
        if not post:
            return Response({"error": "Post not found"}, status=404)
        post.is_deleted = False
        post.deleted_at = None
        post.save(update_fields=["is_deleted", "deleted_at", "updated_at"])
        return Response({"message": "Post restored"})


class AdminAuditLogListView(AdminPaginationMixin, APIView):
    permission_classes = [IsAuthenticated, IsPlatformAdmin]

    def get(self, request):
        query = request.query_params.get("q", "").strip()
        queryset = AuditLog.objects.select_related("actor", "organization").order_by("-created_at")
        if query:
            queryset = queryset.filter(
                Q(action__icontains=query)
                | Q(actor__email__icontains=query)
                | Q(organization__name__icontains=query)
            )
        return self.paginate(request, queryset, AdminAuditLogSerializer)


class AdminIndustryListCreateView(AdminPaginationMixin, APIView):
    permission_classes = [IsAuthenticated, IsPlatformAdmin]

    def get(self, request):
        query = request.query_params.get("q", "").strip()
        queryset = Industry.objects.all().order_by("name")
        if query:
            queryset = queryset.filter(Q(name__icontains=query) | Q(slug__icontains=query))
        return self.paginate(request, queryset, AdminIndustrySerializer)

    def post(self, request):
        serializer = AdminIndustryWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        industry = serializer.save()
        return Response(AdminIndustrySerializer(industry).data, status=status.HTTP_201_CREATED)


class AdminIndustryDetailView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformAdmin]

    def get_object(self, industry_id):
        return Industry.objects.filter(id=industry_id).first()

    def patch(self, request, industry_id):
        industry = self.get_object(industry_id)
        if not industry:
            return Response({"error": "Industry not found"}, status=404)

        serializer = AdminIndustryWriteSerializer(industry, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(AdminIndustrySerializer(industry).data)

    def delete(self, request, industry_id):
        industry = self.get_object(industry_id)
        if not industry:
            return Response({"error": "Industry not found"}, status=404)
        try:
            industry.delete()
        except ProtectedError:
            return Response(
                {"error": "Industry is linked to active records. Remove linked records first."},
                status=400,
            )
        return Response({"message": "Industry deleted"})


class AdminNewsSourceListCreateView(AdminPaginationMixin, APIView):
    permission_classes = [IsAuthenticated, IsPlatformAdmin]

    def get(self, request):
        query = request.query_params.get("q", "").strip()
        include_inactive = request.query_params.get("include_inactive") == "1"

        queryset = NewsSource.objects.select_related("industry").order_by("-created_at")
        if not include_inactive:
            queryset = queryset.filter(is_active=True)

        if query:
            queryset = queryset.filter(
                Q(name__icontains=query)
                | Q(rss_url__icontains=query)
                | Q(industry__name__icontains=query)
            )

        return self.paginate(request, queryset, AdminNewsSourceSerializer)

    def post(self, request):
        serializer = AdminNewsSourceWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        source = serializer.save()
        return Response(AdminNewsSourceSerializer(source).data, status=status.HTTP_201_CREATED)


class AdminNewsSourceDetailView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformAdmin]

    def get_object(self, source_id):
        return NewsSource.objects.select_related("industry").filter(id=source_id).first()

    def patch(self, request, source_id):
        source = self.get_object(source_id)
        if not source:
            return Response({"error": "News source not found"}, status=404)

        serializer = AdminNewsSourceWriteSerializer(source, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(AdminNewsSourceSerializer(source).data)

    def delete(self, request, source_id):
        source = self.get_object(source_id)
        if not source:
            return Response({"error": "News source not found"}, status=404)
        source.delete()
        return Response({"message": "News source deleted"})
