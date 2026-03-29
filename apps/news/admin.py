from django.contrib import admin

# Register your models here.
from .models import *
from .models import NewsArticle


@admin.register(NewsArticle)
class NewsArticleAdmin(admin.ModelAdmin):
    list_display = ("title", "source", "industry", "published_at")
    list_filter = ("industry", "source")
    search_fields = ("title",)
    ordering = ("-published_at",)

    readonly_fields = ("created_at",)


# admin.site.register(NewsSource)


@admin.register(NewsSource)
class NewsSourceAdmin(admin.ModelAdmin):
    list_display = ("name", "industry", "is_active", "created_at")
    list_filter = ("industry", "is_active")
    search_fields = ("name", "rss_url")
    ordering = ("industry", "name")

    fieldsets = (
        ("Basic Info", {"fields": ("name", "rss_url", "industry")}),
        ("Status", {"fields": ("is_active",)}),
    )
