from django.contrib import admin

# Register your models here.
from .models import PostPlatformAnalytics, PostPlatformAnalyticsSnapshot

admin.site.register(PostPlatformAnalytics)
admin.site.register(PostPlatformAnalyticsSnapshot)
