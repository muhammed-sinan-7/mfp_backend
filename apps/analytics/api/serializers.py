from rest_framework import serializers

from ..models import PostPlatformAnalytics


class PostAnalyticsSerializer(serializers.ModelSerializer):

    class Meta:
        model = PostPlatformAnalytics
        fields = "__all__"
