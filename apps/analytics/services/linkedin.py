# apps/analytics/services/linkedin.py

from urllib.parse import quote

import requests

from .base import empty_metrics


def fetch(post_platform):

    account = post_platform.publishing_target.social_account
    access_token = account.access_token

    post_urn = post_platform.external_post_id

    # Encode URN for LinkedIn API
    encoded_urn = quote(post_urn, safe="")

    url = f"https://api.linkedin.com/v2/socialActions/{encoded_urn}"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "X-Restli-Protocol-Version": "2.0.0",
    }

    res = requests.get(url, headers=headers, timeout=10)

    if res.status_code != 200:
        print("LinkedIn API ERROR:", res.text)
        return empty_metrics()

    data = res.json()

    metrics = empty_metrics()

    metrics["likes"] = data.get("likesSummary", {}).get("totalLikes", 0)
    metrics["comments"] = data.get("commentsSummary", {}).get(
        "totalFirstLevelComments", 0
    )

    return metrics
