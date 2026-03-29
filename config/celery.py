import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("mfp_backend")


app.config_from_object("django.conf:settings", namespace="CELERY")


app.autodiscover_tasks()

app.conf.beat_schedule = {
    "dispatch-meta-refresh": {
        "task": "apps.social_accounts.tasks.dispatch_expiring_meta_refresh_tasks",
        "schedule": crontab(minute=0, hour="*/12"),
    },
    "refresh-youtube-tokens-every-15-minutes": {
        "task": "apps.social_accounts.tasks.dispatch_expiring_youtube_refresh_tasks",
        "schedule": crontab(minute="*/15"),
    },
    "dispatch-scheduled-platforms-every-minute": {
        "task": "apps.posts.tasks.dispatch_scheduled_platforms",
        "schedule": crontab(minute="*"),
    },
    "purge-recycle-bin-every-hour": {
        "task": "apps.posts.tasks.purge_recycle_bin",
        "schedule": 3600,
    },
    "sync-post-analytics": {
        "task": "apps.analytics.tasks.sync_post_analytics",
        "schedule": 1800,
    },
    "fetch-industry-news": {
        "task": "apps.news.tasks.ingest_all_news",
        "schedule": crontab(minute="*/30"),  # every 30 min
    },
    "cleanup-analytics-snapshots-daily": {
        "task": "apps.analytics.tasks.cleanup_old_analytics_snapshots",
        "schedule": crontab(minute=30, hour=2),
    },
}
