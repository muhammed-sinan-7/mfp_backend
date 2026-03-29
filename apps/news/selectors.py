from .models import NewsArticle


def get_industry_news(industry_id, page=1, limit=10):
    offset = (page - 1) * limit

    return (
        NewsArticle.objects.select_related("source")
        .only("id", "title", "summary", "image", "published_at", "source__name")
        .filter(industry_id=industry_id)
        .order_by("-published_at")[offset : offset + limit]
    )
