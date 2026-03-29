from rest_framework import serializers

from apps.industries.models import Industry


class IndustrySerializer(serializers.ModelSerializer):

    class Meta:
        model = Industry
        fields = ["id", "name"]
