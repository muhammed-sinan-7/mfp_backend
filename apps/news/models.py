from django.db import models

from apps.industries.models import Industry

# Create your models here.


class NewsSource(models.Model):
    name = models.CharField(max_length=100)
    rss_url = models.URLField(unique=True)
    industry = models.ForeignKey(
        Industry, on_delete=models.PROTECT, related_name="news_sources"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["industry"])]

    def __str__(self):
        return self.name


class NewsArticle(models.Model):
    title = models.TextField()
    summary = models.TextField()
    url = models.URLField(unique=True)
    image = models.URLField(blank=True, null=True)

    source = models.ForeignKey(
        NewsSource, on_delete=models.CASCADE, related_name="articles"
    )

    industry = models.ForeignKey(
        Industry, on_delete=models.PROTECT, related_name="news_articles"
    )

    content = models.TextField(blank=True)
    ai_summary = models.TextField(blank=True)

    published_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["industry", "-published_at"]),
            models.Index(fields=["source", "-published_at"]),
        ]
        ordering = ["-published_at"]

    def __str__(self):
        return f"{self.title} ({self.source.name})"
