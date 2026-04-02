from django.contrib.auth import get_user_model
from django.utils.text import slugify
from rest_framework import serializers

from apps.audit.models import AuditLog
from apps.industries.models import Industry
from apps.news.models import NewsSource
from apps.organizations.models import Organization, OrganizationMember
from apps.posts.models import Post, PostPlatform
from apps.social_accounts.models import SocialAccount

User = get_user_model()


class AdminUserSerializer(serializers.ModelSerializer):
    organization_id = serializers.SerializerMethodField()
    organization_name = serializers.SerializerMethodField()
    organization_role = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "is_active",
            "is_staff",
            "is_superuser",
            "is_email_verified",
            "is_deleted",
            "created_at",
            "organization_id",
            "organization_name",
            "organization_role",
        ]

    def _membership(self, obj):
        return (
            obj.organization_memberships.filter(is_deleted=False)
            .select_related("organization")
            .first()
        )

    def get_organization_id(self, obj):
        membership = self._membership(obj)
        return str(membership.organization_id) if membership else None

    def get_organization_name(self, obj):
        membership = self._membership(obj)
        return membership.organization.name if membership else None

    def get_organization_role(self, obj):
        membership = self._membership(obj)
        return membership.role if membership else None


class AdminUserWriteSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, min_length=8)

    class Meta:
        model = User
        fields = [
            "email",
            "password",
            "is_active",
            "is_staff",
            "is_superuser",
            "is_email_verified",
        ]

    def validate(self, attrs):
        if self.instance is None and not attrs.get("password"):
            raise serializers.ValidationError({"password": "Password is required."})

        if attrs.get("is_superuser"):
            attrs["is_staff"] = True

        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        user = User.objects.create_user(password=password, **validated_data)
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class AdminOrganizationSerializer(serializers.ModelSerializer):
    industry_name = serializers.CharField(source="industry.name", read_only=True)
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = [
            "id",
            "name",
            "slug",
            "tagline",
            "industry",
            "industry_name",
            "logo",
            "is_deleted",
            "created_at",
            "updated_at",
            "member_count",
        ]
        read_only_fields = ["slug", "is_deleted", "created_at", "updated_at", "member_count"]
        extra_kwargs = {
            "logo": {"required": False, "allow_null": True},
            "tagline": {"required": False, "allow_blank": True},
            "industry": {"required": False, "allow_null": True},
        }

    def get_member_count(self, obj):
        return obj.members.filter(is_deleted=False).count()


class AdminOrganizationMemberSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True)

    class Meta:
        model = OrganizationMember
        fields = ["id", "user", "user_email", "role", "joined_at", "is_deleted"]


class AdminSocialAccountSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    target_count = serializers.SerializerMethodField()

    class Meta:
        model = SocialAccount
        fields = [
            "id",
            "organization",
            "organization_name",
            "provider",
            "external_id",
            "account_name",
            "token_expires_at",
            "is_active",
            "created_at",
            "updated_at",
            "target_count",
        ]

    def get_target_count(self, obj):
        return obj.publishing_targets.filter(is_active=True).count()


class AdminPostPlatformSerializer(serializers.ModelSerializer):
    provider = serializers.CharField(source="publishing_target.provider", read_only=True)
    target_name = serializers.CharField(source="publishing_target.display_name", read_only=True)

    class Meta:
        model = PostPlatform
        fields = [
            "id",
            "provider",
            "target_name",
            "caption",
            "scheduled_time",
            "publish_status",
            "failure_reason",
        ]


class AdminPostSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    author_email = serializers.CharField(source="created_by.email", read_only=True)
    platforms = AdminPostPlatformSerializer(many=True, read_only=True)

    class Meta:
        model = Post
        fields = [
            "id",
            "organization",
            "organization_name",
            "author_email",
            "created_at",
            "updated_at",
            "is_deleted",
            "deleted_at",
            "platforms",
        ]


class AdminPostWriteSerializer(serializers.Serializer):
    is_deleted = serializers.BooleanField(required=False)
    deleted_at = serializers.DateTimeField(required=False, allow_null=True)


class AdminAuditLogSerializer(serializers.ModelSerializer):
    actor_email = serializers.CharField(source="actor.email", read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "severity",
            "actor_email",
            "organization_name",
            "action",
            "target_model",
            "target_id",
            "metadata",
            "created_at",
        ]


class AdminIndustrySerializer(serializers.ModelSerializer):
    source_count = serializers.SerializerMethodField()

    class Meta:
        model = Industry
        fields = [
            "id",
            "name",
            "slug",
            "created_at",
            "updated_at",
            "source_count",
        ]

    def get_source_count(self, obj):
        return obj.news_sources.count()


class AdminIndustryWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Industry
        fields = ["name", "slug"]

    def validate(self, attrs):
        name = attrs.get("name", getattr(self.instance, "name", ""))
        slug = attrs.get("slug") or slugify(name)

        queryset = Industry.objects.filter(slug=slug)
        if self.instance:
            queryset = queryset.exclude(id=self.instance.id)

        if queryset.exists():
            raise serializers.ValidationError({"slug": "Slug already exists."})

        attrs["slug"] = slug
        return attrs


class AdminNewsSourceSerializer(serializers.ModelSerializer):
    industry_name = serializers.CharField(source="industry.name", read_only=True)
    article_count = serializers.SerializerMethodField()

    class Meta:
        model = NewsSource
        fields = [
            "id",
            "name",
            "rss_url",
            "industry",
            "industry_name",
            "is_active",
            "created_at",
            "updated_at",
            "article_count",
        ]

    def get_article_count(self, obj):
        return obj.articles.count()


class AdminNewsSourceWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = NewsSource
        fields = ["name", "rss_url", "industry", "is_active"]
