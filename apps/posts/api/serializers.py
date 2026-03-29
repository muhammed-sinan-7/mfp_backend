from django.db import transaction
from django.utils import timezone
from PIL import Image
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from apps.posts.models import MediaType, Post, PostPlatform, PostPlatformMedia
from apps.social_accounts.models import PublishingTarget


def validate_instagram_image(file):
    file.seek(0)

    img = Image.open(file).convert("RGB")
    width, height = img.size

    if height == 0:
        raise ValidationError("Invalid image file.")

    ratio = width / height

    print("INSTAGRAM IMAGE DEBUG:", width, height, ratio)  # temporary debug

    if ratio < 0.8 or ratio > 1.91:
        raise ValidationError(
            f"Instagram aspect ratio invalid ({ratio:.2f}). "
            "Allowed range: 4:5 – 1.91:1. "
            "Recommended: 1080x1080, 1080x1350, 1080x566."
        )

    file.seek(0)


class PostCreateSerializer(serializers.Serializer):

    caption = serializers.CharField(required=False, allow_blank=True)
    scheduled_time = serializers.DateTimeField()
    publishing_target_ids = serializers.ListField(
        child=serializers.UUIDField(), allow_empty=False
    )

    def validate(self, attrs):

        request = self.context["request"]
        org_id = request.organization.id

        targets = PublishingTarget.objects.filter(
            id__in=attrs["publishing_target_ids"],
            social_account__organization_id=org_id,
            is_active=True,
        )

        if targets.count() != len(attrs["publishing_target_ids"]):
            raise serializers.ValidationError("Invalid publishing targets.")

        if attrs["scheduled_time"] < timezone.now():
            raise serializers.ValidationError("Cannot schedule in the past.")

        return attrs

    @transaction.atomic
    def create(self, validated_data):

        request = self.context["request"]
        organization = request.organization

        caption = validated_data.get("caption", "")
        scheduled_time = validated_data["scheduled_time"]
        target_ids = validated_data["publishing_target_ids"]

        post = Post.objects.create(organization=organization, created_by=request.user)

        targets = PublishingTarget.objects.filter(id__in=target_ids)

        for target in targets:

            platform = PostPlatform.objects.create(
                post=post,
                publishing_target=target,
                caption=caption,
                scheduled_time=scheduled_time,
            )

            target_id_str = str(target.id)
            order = 0

            for key, file in request.FILES.items():

                # Instagram max media
                if target.provider == "instagram" and order >= 10:
                    raise ValidationError("Instagram allows max 10 media items.")

                # IMAGE
                if key.startswith(f"image_{target_id_str}"):

                    if target.provider == "youtube":
                        raise ValidationError("YouTube only supports video uploads.")

                    if target.provider == "instagram":
                        validate_instagram_image(file)

                    PostPlatformMedia.objects.create(
                        post_platform=platform,
                        file=file,
                        media_type=MediaType.IMAGE,
                        order=order,
                    )

                    order += 1

                # VIDEO
                elif key.startswith(f"video_{target_id_str}"):

                    PostPlatformMedia.objects.create(
                        post_platform=platform,
                        file=file,
                        media_type=MediaType.VIDEO,
                        order=order,
                    )

                    order += 1

        return post


class MediaSerializer(serializers.ModelSerializer):

    class Meta:
        model = PostPlatformMedia
        fields = [
            "id",
            "file",
            "media_type",
            "order",
        ]


class PlatformSummarySerializer(serializers.ModelSerializer):
    provider = serializers.CharField(source="publishing_target.provider")
    media = MediaSerializer(many=True, read_only=True)

    class Meta:
        model = PostPlatform
        fields = [
            "id",
            "provider",
            "publish_status",
            "scheduled_time",
            "external_post_id",
            "caption",
            "media",
        ]


class PostListSerializer(serializers.ModelSerializer):

    platforms = PlatformSummarySerializer(many=True, read_only=True)
    author = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            "id",
            "created_at",
            "updated_at",
            "deleted_at",
            "author",
            "platforms",
        ]

    def get_author(self, obj):
        if obj.created_by:
            return obj.created_by.email
        return None


class PlatformDetailSerializer(serializers.ModelSerializer):

    provider = serializers.CharField(source="publishing_target.provider")

    media = MediaSerializer(many=True)

    class Meta:
        model = PostPlatform
        fields = [
            "id",
            "provider",
            "caption",
            "scheduled_time",
            "publish_status",
            "external_post_id",
            "failure_reason",
            "media",
        ]


class PostDetailSerializer(serializers.ModelSerializer):

    platforms = PlatformDetailSerializer(many=True)

    class Meta:
        model = Post
        fields = [
            "id",
            "created_at",
            "updated_at",
            "platforms",
        ]


class PlatformUpdateSerializer(serializers.Serializer):

    id = serializers.UUIDField()
    caption = serializers.CharField(required=False)
    scheduled_time = serializers.DateTimeField(required=False)

    def validate(self, attrs):

        platform = PostPlatform.objects.get(id=attrs["id"])

        if platform.publish_status != "pending":
            raise serializers.ValidationError(
                "Cannot edit already processing/published posts."
            )

        if "scheduled_time" in attrs:
            if attrs["scheduled_time"] < timezone.now():
                raise serializers.ValidationError("Scheduled time must be in future.")

        return attrs
