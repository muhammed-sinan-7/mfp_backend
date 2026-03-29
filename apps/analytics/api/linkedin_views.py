from datetime import timedelta

from django.core.cache import cache
from django.db.models import Sum
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.organizations.mixins import OrganizationContextMixin
from apps.social_accounts.models import SocialProvider

from ..models import PostPlatformAnalytics, PostPlatformAnalyticsSnapshot

CACHE_TTL_SECONDS = 60


class LinkedInOverviewView(OrganizationContextMixin, APIView):

    def get(self, request):
        org = request.organization
        cache_key = f"analytics:linkedin:overview:{org.id}"
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        qs = PostPlatformAnalytics.objects.filter(
            post_platform__post__organization=org,
            post_platform__publishing_target__provider=SocialProvider.LINKEDIN,
        )

        data = qs.aggregate(
            impressions=Sum("impressions"),
            views=Sum("views"),
            likes=Sum("likes"),
            comments=Sum("comments"),
            shares=Sum("shares"),
        )

        impressions = data["impressions"] or 0
        likes = data["likes"] or 0
        comments = data["comments"] or 0
        shares = data["shares"] or 0
        engagement = likes + comments + shares
        click_through_rate = round((engagement / impressions * 100), 2) if impressions else 0

        payload = {
            "connections": likes,
            "unique_visitors": data["views"] or 0,
            "post_impressions": impressions,
            "click_through_rate": click_through_rate,
        }
        cache.set(cache_key, payload, timeout=CACHE_TTL_SECONDS)
        return Response(payload)


class LinkedInGrowthChartView(OrganizationContextMixin, APIView):

    def get(self, request):
        org = request.organization
        cache_key = f"analytics:linkedin:growth:{org.id}"
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        start_date = timezone.now() - timedelta(days=30)

        qs = (
            PostPlatformAnalyticsSnapshot.objects.filter(
                post_platform__post__organization=org,
                post_platform__publishing_target__provider=SocialProvider.LINKEDIN,
                captured_at__gte=start_date,
            )
            .annotate(day=TruncDate("captured_at"))
            .values("day")
            .annotate(impressions=Sum("impressions"), clicks=Sum("likes"))
            .order_by("day")
        )

        payload = list(qs)
        cache.set(cache_key, payload, timeout=CACHE_TTL_SECONDS)
        return Response(payload)


class LinkedInPostAnalyticsView(OrganizationContextMixin, APIView):

    def get(self, request):
        org = request.organization
        cache_key = f"analytics:linkedin:posts:{org.id}"
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        qs = (
            PostPlatformAnalytics.objects.filter(
                post_platform__post__organization=org,
                post_platform__publishing_target__provider=SocialProvider.LINKEDIN,
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
            thumbnail, media_type = resolve_media(p.post_platform)

            data.append(
                {
                    "post_id": p.post_platform.post.id,
                    "title": p.post_platform.caption or "LinkedIn Post",
                    "type": "post",
                    "impressions": p.impressions,
                    "clicks": p.likes,
                    "ctr": round((p.likes / p.impressions * 100) if p.impressions else 0, 2),
                    "status": "High Engagement" if p.likes > 100 else "Normal",
                    "thumbnail": thumbnail,
                    "media_type": media_type,
                }
            )

        cache.set(cache_key, data, timeout=CACHE_TTL_SECONDS)
        return Response(data)
