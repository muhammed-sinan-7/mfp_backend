from datetime import date, timedelta

from django.conf import settings
from django.core.cache import cache
from django.db.models import Sum
from django.db.models.functions import TruncDate
from django.utils import timezone
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.organizations.mixins import OrganizationContextMixin
from apps.social_accounts.models import SocialProvider

from ..models import PostPlatformAnalytics, PostPlatformAnalyticsSnapshot

CACHE_TTL_SECONDS = 60
TRAFFIC_CACHE_TTL_SECONDS = 300


class YouTubeOverviewView(OrganizationContextMixin, APIView):

    def get(self, request):
        org = request.organization
        if org is None:
            return Response({"error": "Organization context missing"}, status=400)

        cache_key = f"analytics:youtube:overview:{org.id}"
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        qs = PostPlatformAnalytics.objects.filter(
            post_platform__post__organization_id=org.id,
            post_platform__publishing_target__provider=SocialProvider.YOUTUBE,
        )

        data = qs.aggregate(
            views=Sum("views"),
            likes=Sum("likes"),
            comments=Sum("comments"),
            watch_time=Sum("watch_time"),
        )

        account = org.social_accounts.filter(provider=SocialProvider.YOUTUBE).first()
        metadata = getattr(account, "metadata", {}) if account else {}
        subscribers = (
            metadata.get("subscriber_count")
            or metadata.get("subscribers")
            or metadata.get("subscriberCount")
            or 0
        )
        estimated_revenue = (
            metadata.get("estimated_revenue")
            or metadata.get("estimatedRevenue")
            or 0
        )

        payload = {
            "subscribers": int(subscribers or 0),
            "watch_time": data["watch_time"] or 0,
            "estimated_revenue": float(estimated_revenue or 0),
        }
        cache.set(cache_key, payload, timeout=CACHE_TTL_SECONDS)
        return Response(payload)


class YouTubeGrowthChartView(OrganizationContextMixin, APIView):

    def get(self, request):
        org = request.organization
        if org is None:
            return Response({"error": "Organization context missing"}, status=400)

        cache_key = f"analytics:youtube:growth:{org.id}"
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        start_date = timezone.now() - timedelta(days=30)

        qs = (
            PostPlatformAnalyticsSnapshot.objects.filter(
                post_platform__post__organization_id=org.id,
                post_platform__publishing_target__provider=SocialProvider.YOUTUBE,
                captured_at__gte=start_date,
            )
            .annotate(day=TruncDate("captured_at"))
            .order_by("day", "-captured_at")
            .distinct("day")
            .values("day", "views", "watch_time")
            .order_by("day")
        )

        payload = [
            {
                "day": row["day"],
                "views": row["views"],
                "duration": row["watch_time"],
            }
            for row in qs
        ]

        cache.set(cache_key, payload, timeout=CACHE_TTL_SECONDS)
        return Response(payload)


class YouTubeVideoAnalyticsView(OrganizationContextMixin, APIView):

    def get(self, request):
        org = request.organization
        if org is None:
            return Response({"error": "Organization context missing"}, status=400)

        cache_key = f"analytics:youtube:videos:{org.id}"
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        qs = (
            PostPlatformAnalytics.objects.filter(
                post_platform__post__organization_id=org.id,
                post_platform__publishing_target__provider=SocialProvider.YOUTUBE,
            )
            .prefetch_related("post_platform__media")
            .order_by("-id")[:20]
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

        for v in qs:
            thumbnail, media_type = resolve_media(v.post_platform)

            data.append(
                {
                    "video_id": v.post_platform.post.id,
                    "title": v.post_platform.caption or f"YouTube Video {v.post_platform.id}",
                    "views": v.views,
                    "ctr": round((v.likes / v.views * 100) if v.views else 0, 2),
                    "comments": v.comments,
                    "status": "Trending" if v.views > 50000 else "Published",
                    "thumbnail": thumbnail,
                    "media_type": media_type,
                }
            )

        cache.set(cache_key, data, timeout=CACHE_TTL_SECONDS)
        return Response(data)


class YouTubeTrafficSourcesView(OrganizationContextMixin, APIView):

    def get(self, request):
        org = request.organization

        if org is None:
            return Response({"error": "Organization context missing"}, status=400)

        cache_key = f"analytics:youtube:traffic:{org.id}"
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        account = org.social_accounts.filter(provider=SocialProvider.YOUTUBE).first()

        if not account:
            return Response([])

        credentials = Credentials(
            token=account.access_token,
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
        )

        yt_analytics = build("youtubeAnalytics", "v2", credentials=credentials)

        end = date.today()
        start = end - timedelta(days=30)

        report = (
            yt_analytics.reports()
            .query(
                ids="channel==MINE",
                startDate=start.isoformat(),
                endDate=end.isoformat(),
                metrics="views",
                dimensions="insightTrafficSourceType",
                sort="-views",
            )
            .execute()
        )

        rows = report.get("rows", [])

        traffic_labels = {
            "YT_SEARCH": "YouTube Search",
            "SUGGESTED_VIDEO": "Suggested Videos",
            "BROWSE": "Browse Features",
            "EXTERNAL": "External",
        }

        total = sum(r[1] for r in rows)

        data = []
        for src, views in rows:
            pct = round((views / total) * 100, 2) if total else 0
            data.append(
                {"label": traffic_labels.get(src, src), "value": pct, "views": views}
            )

        cache.set(cache_key, data, timeout=TRAFFIC_CACHE_TTL_SECONDS)
        return Response(data)
