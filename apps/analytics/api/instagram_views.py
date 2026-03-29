from datetime import timedelta

from django.core.cache import cache
from django.db.models import F, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.organizations.mixins import OrganizationContextMixin
from apps.social_accounts.models import SocialProvider

from ..models import PostPlatformAnalytics, PostPlatformAnalyticsSnapshot

CACHE_TTL_SECONDS = 60


class InstagramOverviewView(OrganizationContextMixin, APIView):

    def get(self, request):
        org = request.organization
        cache_key = f"analytics:instagram:overview:{org.id}"
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        qs = PostPlatformAnalytics.objects.filter(
            post_platform__post__organization=org,
            post_platform__publishing_target__provider=SocialProvider.INSTAGRAM,
        )

        data = qs.aggregate(
            impressions=Sum("impressions"),
            views=Sum("views"),
            likes=Sum("likes"),
            comments=Sum("comments"),
            saves=Sum("saves"),
        )

        payload = {
            "accounts_reached": data["impressions"] or 0,
            "profile_visits": data["views"] or 0,
            "likes": data["likes"] or 0,
            "story_completion": data["saves"] or 0,
        }
        cache.set(cache_key, payload, timeout=CACHE_TTL_SECONDS)
        return Response(payload)


class InstagramGrowthChartView(OrganizationContextMixin, APIView):

    def get(self, request):
        org = request.organization
        cache_key = f"analytics:instagram:growth:{org.id}"
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        start_date = timezone.now() - timedelta(days=30)

        qs = (
            PostPlatformAnalyticsSnapshot.objects.filter(
                post_platform__post__organization_id=org.id,
                post_platform__publishing_target__provider=SocialProvider.INSTAGRAM,
                captured_at__gte=start_date,
            )
            .annotate(day=TruncDate("captured_at"))
            .order_by("day", "-captured_at")
            .distinct("day")
            .values("day", "likes", "comments")
            .order_by("day")
        )

        payload = list(qs)
        cache.set(cache_key, payload, timeout=CACHE_TTL_SECONDS)
        return Response(payload)


class InstagramTopPostsView(OrganizationContextMixin, APIView):

    def get(self, request):
        org = request.organization
        cache_key = f"analytics:instagram:top-posts:{org.id}"
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        qs = (
            PostPlatformAnalytics.objects.filter(
                post_platform__post__organization=org,
                post_platform__publishing_target__provider=SocialProvider.INSTAGRAM,
            )
            .prefetch_related("post_platform__media")
            .annotate(engagement=F("likes") + F("comments") + F("shares"))
            .order_by("-engagement")[:5]
        )

        data = []

        def resolve_media(post_platform):
            media = post_platform.media.order_by("order").first()
            if not media:
                return None, None
            file_url = media.file.url if media.file else None
            if file_url and not str(file_url).startswith("http"):
                file_url = request.build_absolute_uri(file_url)
            return file_url, media.media_type

        for p in qs:
            thumbnail, media_type = resolve_media(p.post_platform)

            data.append(
                {
                    "post_id": p.post_platform.post.id,
                    "title": p.post_platform.caption,
                    "likes": p.likes,
                    "comments": p.comments,
                    "engagement": p.engagement,
                    "thumbnail": thumbnail,
                    "media_type": media_type,
                }
            )

        cache.set(cache_key, data, timeout=CACHE_TTL_SECONDS)
        return Response(data)


class InstagramPostPerformanceView(OrganizationContextMixin, APIView):

    def get(self, request):
        org = request.organization
        cache_key = f"analytics:instagram:performance:{org.id}"
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        qs = (
            PostPlatformAnalytics.objects.filter(
                post_platform__post__organization=org,
                post_platform__publishing_target__provider=SocialProvider.INSTAGRAM,
            )
            .prefetch_related("post_platform__media")
            .order_by("-created_at")[:20]
        )

        data = []

        def resolve_media(post_platform):
            media = post_platform.media.order_by("order").first()
            if not media:
                return None, None
            file_url = media.file.url if media.file else None
            if file_url and not str(file_url).startswith("http"):
                file_url = request.build_absolute_uri(file_url)
            return file_url, media.media_type

        for p in qs:
            engagement = p.likes + p.comments + p.shares
            thumbnail, media_type = resolve_media(p.post_platform)

            data.append(
                {
                    "post_id": p.post_platform.post.id,
                    "title": p.post_platform.caption,
                    "engagement": engagement,
                    "reach": p.impressions,
                    "date": p.created_at,
                    "thumbnail": thumbnail,
                    "media_type": media_type,
                }
            )

        cache.set(cache_key, data, timeout=CACHE_TTL_SECONDS)
        return Response(data)
