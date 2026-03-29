from datetime import date, timedelta

from django.conf import settings
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from .base import empty_metrics

TRAFFIC_LABELS = {
    "YT_SEARCH": "YouTube Search",
    "SUGGESTED_VIDEO": "Suggested Videos",
    "BROWSE": "Browse Features",
    "EXTERNAL": "External",
    "CHANNEL_PAGE": "Channel Page",
    "PLAYLIST": "Playlist",
}


def fetch(post_platform):

    account = post_platform.publishing_target.social_account

    credentials = Credentials(
        token=account.access_token,
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
    )

    youtube = build("youtube", "v3", credentials=credentials)
    yt_analytics = build("youtubeAnalytics", "v2", credentials=credentials)

    video_id = post_platform.external_post_id

    metrics = empty_metrics()

    res = youtube.videos().list(part="statistics", id=video_id).execute()

    items = res.get("items")

    if not items:
        return None

    stats = items[0]["statistics"]

    metrics["views"] = int(stats.get("viewCount", 0))
    metrics["likes"] = int(stats.get("likeCount", 0))
    metrics["comments"] = int(stats.get("commentCount", 0))

    end = date.today()
    start = end - timedelta(days=30)

    report = (
        yt_analytics.reports()
        .query(
            ids="channel==MINE",
            startDate=start.isoformat(),
            endDate=end.isoformat(),
            metrics="averageViewDuration,estimatedMinutesWatched",
            dimensions="video",
            filters=f"video=={video_id}",
        )
        .execute()
    )

    rows = report.get("rows")

    if rows:
        avg_duration = rows[0][0]
        minutes_watched = rows[0][1]

        metrics["avg_view_duration"] = avg_duration
        metrics["watch_time"] = round(minutes_watched / 60, 2)

    traffic_report = (
        yt_analytics.reports()
        .query(
            ids="channel==MINE",
            startDate=start.isoformat(),
            endDate=end.isoformat(),
            metrics="views",
            dimensions="insightTrafficSourceType",
            filters=f"video=={video_id}",
            sort="-views",
        )
        .execute()
    )

    traffic_rows = traffic_report.get("rows", [])

    total_views = sum(r[1] for r in traffic_rows) if traffic_rows else 0

    traffic_sources = []

    for src, views in traffic_rows:

        pct = round((views / total_views) * 100, 2) if total_views else 0

        traffic_sources.append(
            {
                "label": TRAFFIC_LABELS.get(src, src),
                "views": views,
                "percentage": pct,
            }
        )

    metrics["traffic_sources"] = traffic_sources

    return metrics
