from django.core.cache import cache
from django.db.models import F, Sum
from django.utils.timezone import now, timedelta
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.news.selectors import get_industry_news
from apps.organizations.mixins import OrganizationContextMixin
from apps.posts.models import PostPlatform, PublishStatus
from apps.social_accounts.models import SocialAccount, SocialProvider

from ..models import PostPlatformAnalytics, PostPlatformAnalyticsSnapshot
from .serializers import PostAnalyticsSerializer

CACHE_TTL_SECONDS = 60


def _cache_key(org_id, scope, extra=""):
    return f"analytics:{scope}:org:{org_id}:{extra}"


class AnalyticsListView(APIView):

    def get(self, request):

        analytics = PostPlatformAnalytics.objects.select_related("post_platform")

        serializer = PostAnalyticsSerializer(analytics, many=True)

        return Response(serializer.data)


class AnalyticsOverviewView(OrganizationContextMixin, APIView):

    def get(self, request):

        org = request.organization
        platform = request.query_params.get("platform")
        key = _cache_key(org.id, "overview", platform or "all")
        cached = cache.get(key)
        if cached is not None:
            return Response(cached)

        analytics = PostPlatformAnalytics.objects.filter(
            post_platform__post__organization=org
        )

        if platform:
            analytics = analytics.filter(
                post_platform__publishing_target__provider=platform
            )

        data = analytics.aggregate(
            impressions=Sum("impressions"),
            views=Sum("views"),
            likes=Sum("likes"),
            comments=Sum("comments"),
            shares=Sum("shares"),
        )

        impressions = data["impressions"] or 0
        views = data["views"] or 0
        likes = data["likes"] or 0
        comments = data["comments"] or 0
        shares = data["shares"] or 0

        engagement = likes + comments + shares

        base = impressions if impressions > 0 else views
        engagement_rate = (engagement / base * 100) if base else 0

        payload = {
            "total_impressions": impressions,
            "total_views": views,
            "total_likes": likes,
            "total_comments": comments,
            "engagement_rate": round(engagement_rate, 2),
        }
        cache.set(key, payload, timeout=CACHE_TTL_SECONDS)
        return Response(payload)


class TopPostsAnalyticsView(OrganizationContextMixin, APIView):

    def get(self, request):

        org = request.organization
        key = _cache_key(org.id, "top-posts")
        cached = cache.get(key)
        if cached is not None:
            return Response(cached)

        posts = (
            PostPlatformAnalytics.objects.filter(post_platform__post__organization=org)
            .annotate(engagement=F("likes") + F("comments") + F("shares"))
            .order_by("-engagement")[:10]
        )

        data = []

        for p in posts:

            data.append(
                {
                    "post_id": p.post_platform.post_id,
                    "platform": p.post_platform.publishing_target.provider,
                    "likes": p.likes,
                    "comments": p.comments,
                    "shares": p.shares,
                    "views": p.views,
                }
            )

        cache.set(key, data, timeout=CACHE_TTL_SECONDS)
        return Response(data)


class PlatformAnalyticsView(OrganizationContextMixin, APIView):

    def get(self, request):

        org = request.organization
        key = _cache_key(org.id, "platform-performance")
        cached = cache.get(key)
        if cached is not None:
            return Response(cached)

        analytics = (
            PostPlatformAnalytics.objects.filter(post_platform__post__organization=org)
            .values("post_platform__publishing_target__provider")
            .annotate(likes=Sum("likes"), comments=Sum("comments"), views=Sum("views"))
        )

        result = list(analytics)
        cache.set(key, result, timeout=CACHE_TTL_SECONDS)
        return Response(result)


class EngagementChartView(OrganizationContextMixin, APIView):

    def get(self, request):

        org = request.organization
        platform = request.query_params.get("platform")
        key = _cache_key(org.id, "engagement-chart", platform or "overview")
        cached = cache.get(key)
        if cached is not None:
            return Response(cached)

        snapshots = PostPlatformAnalyticsSnapshot.objects.filter(
            post_platform__post__organization=org,
            captured_at__gte=now() - timedelta(days=30),
        )

        if platform and platform != "overview":
            snapshots = snapshots.filter(
                post_platform__publishing_target__provider=platform
            )

        # Keep the latest snapshot per post per hour in Python.
        # This avoids relying on DISTINCT with an annotated field across DB backends.
        rows = (
            snapshots.values(
                "post_platform_id",
                "post_platform__publishing_target__provider",
                "captured_at",
                "views",
            )
            .order_by("post_platform_id", "captured_at")
            .iterator(chunk_size=1000)
        )

        latest_per_post_hour = {}
        for row in rows:
            captured_at = row["captured_at"]
            hour = captured_at.replace(minute=0, second=0, microsecond=0)
            latest_per_post_hour[(row["post_platform_id"], hour)] = row

        data = {}
        for row in latest_per_post_hour.values():
            captured_at = row["captured_at"]
            hour = captured_at.replace(minute=0, second=0, microsecond=0)
            provider = row["post_platform__publishing_target__provider"]
            provider = "instagram" if provider == "meta" else provider
            views = row["views"] or 0

            if hour not in data:
                data[hour] = {
                    "date": hour,
                    "instagram": 0,
                    "youtube": 0,
                    "linkedin": 0,
                }

            if provider in data[hour]:
                data[hour][provider] += views

        payload = [data[k] for k in sorted(data.keys())]
        cache.set(key, payload, timeout=CACHE_TTL_SECONDS)
        return Response(payload)


class EngagementDistributionAPIView(OrganizationContextMixin, APIView):

    def get(self, request):

        org = request.organization
        key = _cache_key(org.id, "engagement-distribution")
        cached = cache.get(key)
        if cached is not None:
            return Response(cached)

        qs = PostPlatformAnalyticsSnapshot.objects.filter(
            post_platform__post__organization=org,
            captured_at__gte=now() - timedelta(days=30),
        )

        # latest snapshot per post
        latest_ids = (
            qs.order_by("post_platform", "-captured_at")
            .distinct("post_platform")
            .values_list("id", flat=True)
        )

        latest = PostPlatformAnalyticsSnapshot.objects.filter(id__in=latest_ids)

        platform_data = latest.values(
            "post_platform__publishing_target__provider"
        ).annotate(
            engagement=Sum(F("likes") + F("comments") + F("shares") + F("saves"))
        )

        total = sum(item["engagement"] or 0 for item in platform_data)

        data = []

        for item in platform_data:

            platform = item["post_platform__publishing_target__provider"]
            engagement = item["engagement"] or 0

            percent = (engagement / total * 100) if total else 0

            data.append(
                {
                    "platform": platform,
                    "engagement": engagement,
                    "percentage": round(percent, 1),
                }
            )

        cache.set(key, data, timeout=CACHE_TTL_SECONDS)
        return Response(data)


class RecentPostsAPIView(OrganizationContextMixin, APIView):

    def get(self, request):

        org = request.organization
        key = _cache_key(org.id, "recent-posts")
        cached = cache.get(key)
        if cached is not None:
            return Response(cached)

        qs = (
            PostPlatformAnalytics.objects.filter(post_platform__post__organization=org)
            .select_related(
                "post_platform",
                "post_platform__post",
                "post_platform__publishing_target",
            )
            .prefetch_related("post_platform__media")
            .order_by("-created_at")[:10]
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

        for item in qs:

            engagement = item.likes + item.comments + item.shares + item.saves

            platform = item.post_platform.publishing_target.provider

            impressions = item.impressions or item.views

            engagement_rate = (engagement / impressions * 100) if impressions else 0
            thumbnail, media_type = resolve_media(item.post_platform)

            data.append(
                {
                    "post_id": item.post_platform.post.id,
                    "title": item.post_platform.caption or "Post",
                    "platform": platform,
                    "impressions": impressions,
                    "engagement_rate": round(engagement_rate, 2),
                    "status": "High Growth" if engagement > 100 else "Standard",
                    "thumbnail": thumbnail,
                    "media_type": media_type,
                }
            )

        cache.set(key, data, timeout=CACHE_TTL_SECONDS)
        return Response(data)


class FullDashboardAPIView(OrganizationContextMixin, APIView):

    def get(self, request):

        org = request.organization
        cache_key = f"analytics:dashboard:full:{org.id}"
        force_refresh = request.query_params.get("force") == "1"
        cached_data = None if force_refresh else cache.get(cache_key)

        if cached_data is not None:
            return Response(cached_data)

        current_time = now()
        last_7_days = current_time - timedelta(days=7)
        last_14_days = current_time - timedelta(days=14)
        last_30_days = current_time - timedelta(days=30)

        def _normalize_totals(raw):
            reach_total = (raw.get("reach") or 0) or (raw.get("impressions") or 0) or (
                raw.get("views") or 0
            )
            engagement_total = (
                (raw.get("likes") or 0)
                + (raw.get("comments") or 0)
                + (raw.get("shares") or 0)
                + (raw.get("saves") or 0)
            )
            rate = (engagement_total / reach_total * 100) if reach_total else 0
            return {
                "reach": int(reach_total),
                "engagement": int(engagement_total),
                "engagement_rate": round(rate, 2),
                "impressions": int(raw.get("impressions") or 0),
                "views": int(raw.get("views") or 0),
                "likes": int(raw.get("likes") or 0),
                "comments": int(raw.get("comments") or 0),
                "shares": int(raw.get("shares") or 0),
                "saves": int(raw.get("saves") or 0),
            }

        def _pct_change(current, previous):
            if previous == 0:
                return 0.0 if current == 0 else 100.0
            return round(((current - previous) / previous) * 100, 2)

        base_analytics = PostPlatformAnalytics.objects.filter(
            post_platform__post__organization=org
        )

        current_analytics = base_analytics.filter(last_synced_at__gte=last_7_days)
        previous_analytics = base_analytics.filter(
            last_synced_at__lt=last_7_days,
            last_synced_at__gte=last_14_days,
        )

        metric_fields = [
            "reach",
            "impressions",
            "views",
            "likes",
            "comments",
            "shares",
            "saves",
        ]
        current_raw = current_analytics.aggregate(
            **{field: Sum(field) for field in metric_fields}
        )
        previous_raw = previous_analytics.aggregate(
            **{field: Sum(field) for field in metric_fields}
        )
        current_stats = _normalize_totals(current_raw)
        previous_stats = _normalize_totals(previous_raw)

        def _latest_snapshot_totals(start=None, end=None):
            qs = PostPlatformAnalyticsSnapshot.objects.filter(
                post_platform__post__organization=org
            )
            if start is not None:
                qs = qs.filter(captured_at__gte=start)
            if end is not None:
                qs = qs.filter(captured_at__lt=end)

            latest_ids = (
                qs.order_by("post_platform", "-captured_at")
                .distinct("post_platform")
                .values_list("id", flat=True)
            )
            return qs.model.objects.filter(id__in=latest_ids).aggregate(
                reach=Sum("reach"),
                impressions=Sum("impressions"),
                views=Sum("views"),
                likes=Sum("likes"),
                comments=Sum("comments"),
                shares=Sum("shares"),
                saves=Sum("saves"),
            )

        # Fallback chain to avoid zeroed dashboard when analytics rows are sparse:
        # 1) current 7-day analytics
        # 2) latest 7-day snapshots
        # 3) all-time analytics
        # 4) all-time latest snapshots
        if current_stats["reach"] == 0 and current_stats["engagement"] == 0:
            snapshot_7d = _normalize_totals(_latest_snapshot_totals(start=last_7_days))
            if snapshot_7d["reach"] > 0 or snapshot_7d["engagement"] > 0:
                current_stats = snapshot_7d
            else:
                all_time_analytics = _normalize_totals(
                    base_analytics.aggregate(
                        **{field: Sum(field) for field in metric_fields}
                    )
                )
                if (
                    all_time_analytics["reach"] > 0
                    or all_time_analytics["engagement"] > 0
                ):
                    current_stats = all_time_analytics
                else:
                    current_stats = _normalize_totals(_latest_snapshot_totals())

        if previous_stats["reach"] == 0 and previous_stats["engagement"] == 0:
            previous_stats = _normalize_totals(
                _latest_snapshot_totals(start=last_14_days, end=last_7_days)
            )

        posts_qs = PostPlatform.objects.filter(post__organization=org)
        posts_counts = {
            "scheduled": posts_qs.filter(
                publish_status=PublishStatus.PENDING, scheduled_time__gte=current_time
            ).count(),
            "processing": posts_qs.filter(publish_status=PublishStatus.PROCESSING).count(),
            "published_30d": posts_qs.filter(
                publish_status=PublishStatus.SUCCESS, scheduled_time__gte=last_30_days
            ).count(),
            "failed_30d": posts_qs.filter(
                publish_status=PublishStatus.FAILED, scheduled_time__gte=last_30_days
            ).count(),
        }

        # ------------------ TOP POSTS ------------------
        top_posts_qs = (
            base_analytics.select_related("post_platform__publishing_target")
            .prefetch_related("post_platform__media")
            .annotate(engagement=F("likes") + F("comments") + F("shares"))
            .order_by("-engagement")[:5]
        )

        top_posts = []
        for p in top_posts_qs:
            media = p.post_platform.media.order_by("order").first()
            thumbnail = media.file.url if media and media.file else None
            if thumbnail and not str(thumbnail).startswith("http"):
                thumbnail = request.build_absolute_uri(thumbnail)

            base_value = p.reach or p.impressions or p.views or 0
            engagement_rate = (p.engagement / base_value * 100) if base_value else 0

            top_posts.append(
                {
                    "title": p.post_platform.caption or "Untitled Post",
                    "platform": p.post_platform.publishing_target.provider,
                    "engagement": int(p.engagement or 0),
                    "impressions": int(base_value),
                    "engagement_rate": round(engagement_rate, 2),
                    "thumbnail": thumbnail,
                }
            )

        # Fallback top posts from latest snapshots when analytics table is empty.
        if not top_posts:
            snapshot_qs = PostPlatformAnalyticsSnapshot.objects.filter(
                post_platform__post__organization=org
            )
            latest_ids = (
                snapshot_qs.order_by("post_platform", "-captured_at")
                .distinct("post_platform")
                .values_list("id", flat=True)
            )
            snapshot_top = (
                PostPlatformAnalyticsSnapshot.objects.filter(id__in=latest_ids)
                .select_related("post_platform__publishing_target")
                .prefetch_related("post_platform__media")
                .annotate(engagement=F("likes") + F("comments") + F("shares"))
                .order_by("-engagement")[:5]
            )
            for p in snapshot_top:
                media = p.post_platform.media.order_by("order").first()
                thumbnail = media.file.url if media and media.file else None
                if thumbnail and not str(thumbnail).startswith("http"):
                    thumbnail = request.build_absolute_uri(thumbnail)

                base_value = p.reach or p.impressions or p.views or 0
                engagement_rate = (p.engagement / base_value * 100) if base_value else 0
                top_posts.append(
                    {
                        "title": p.post_platform.caption or "Untitled Post",
                        "platform": p.post_platform.publishing_target.provider,
                        "engagement": int(p.engagement or 0),
                        "impressions": int(base_value),
                        "engagement_rate": round(engagement_rate, 2),
                        "thumbnail": thumbnail,
                    }
                )

        # ------------------ RECENT POSTS ------------------
        recent_qs = (
            PostPlatform.objects.filter(post__organization=org)
            .select_related("publishing_target")
            .order_by("-scheduled_time")[:5]
        )

        recent_posts = []
        for p in recent_qs:
            recent_posts.append(
                {
                    "title": p.caption,
                    "platform": p.publishing_target.provider,
                    "status": p.publish_status,
                }
            )

        active_accounts = SocialAccount.objects.filter(organization=org, is_active=True)
        integrations = {
            "instagram": active_accounts.filter(provider=SocialProvider.INSTAGRAM).exists()
            or active_accounts.filter(provider=SocialProvider.META).exists(),
            "linkedin": active_accounts.filter(provider=SocialProvider.LINKEDIN).exists(),
            "youtube": active_accounts.filter(provider=SocialProvider.YOUTUBE).exists(),
        }

        # ------------------ NEWS ------------------
        news = []
        if org.industry:
            articles = get_industry_news(org.industry_id, page=1, limit=5)
            for a in articles:
                news.append(
                    {
                        "title": a.title,
                        "url": a.url,
                    }
                )

        # ------------------ RESPONSE ------------------
        payload = {
            "stats": current_stats,
            "trend": {
                "reach_pct": _pct_change(
                    current_stats["reach"], previous_stats["reach"]
                ),
                "engagement_pct": _pct_change(
                    current_stats["engagement"], previous_stats["engagement"]
                ),
                "engagement_rate_delta": round(
                    current_stats["engagement_rate"] - previous_stats["engagement_rate"],
                    2,
                ),
            },
            "posts": posts_counts,
            "top_posts": top_posts,
            "recent_posts": recent_posts,
            "news": news,
            "integrations": integrations,
            "updated_at": current_time.isoformat(),
        }

        
        cache.set(cache_key, payload, timeout=30)

        return Response(payload)
