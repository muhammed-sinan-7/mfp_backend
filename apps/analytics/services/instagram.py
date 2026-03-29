import requests

from .base import empty_metrics

GRAPH_VERSION = "v25.0"
GRAPH_URL = f"https://graph.facebook.com/{GRAPH_VERSION}"


def fetch(post_platform):

    access_token = post_platform.publishing_target.social_account.access_token
    media_id = post_platform.external_post_id

    metrics = empty_metrics()

    # 1️⃣ Fetch media metadata
    media_res = requests.get(
        f"{GRAPH_URL}/{media_id}",
        params={
            "fields": "media_type,like_count,comments_count",
            "access_token": access_token,
        },
        timeout=10,
    )

    if media_res.status_code != 200:

        return metrics

    media = media_res.json()

    media_type = media.get("media_type")

    metrics["likes"] = media.get("like_count", 0)
    metrics["comments"] = media.get("comments_count", 0)

    # 2️⃣ Fetch insights
    insights_res = requests.get(
        f"{GRAPH_URL}/{media_id}/insights",
        params={
            "metric": "views,reach,saved",
            "access_token": access_token,
        },
        timeout=10,
    )

    if insights_res.status_code != 200:

        return metrics

    data = insights_res.json().get("data", [])

    views = 0
    reach = 0
    saves = 0

    for metric in data:

        name = metric.get("name")
        values = metric.get("values", [])

        if not values:
            continue

        value = values[0].get("value", 0)

        if name == "views":
            views = value

        elif name == "reach":
            reach = value

        elif name == "saved":
            saves = value

    # 3️⃣ Normalize metrics
    metrics["views"] = views
    metrics["reach"] = reach
    metrics["saves"] = saves

    return metrics
