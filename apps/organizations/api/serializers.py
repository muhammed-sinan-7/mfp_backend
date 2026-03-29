from django.utils.text import slugify
from rest_framework import serializers

from apps.industries.models import Industry
from apps.organizations.models import Organization


class OrganizationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ["id", "name", "industry", "tagline", "logo"]

    def create(self, validated_data):
        name = validated_data["name"]

        base_slug = slugify(name)
        slug = base_slug

        counter = 1
        while Organization.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1

        validated_data["slug"] = slug

        return super().create(validated_data)

    def validate_name(self, value):
        if Organization.objects.filter(name__iexact=value).exists():
            raise serializers.ValidationError("Organization name already exists")
        return value


class OrganizationSerializer(serializers.ModelSerializer):
    logo = serializers.ImageField(required=False)
    industry_name = serializers.CharField(source="industry.name", read_only=True)

    class Meta:
        model = Organization
        fields = ["id", "name", "industry", "industry_name", "tagline", "logo"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")

        if instance.logo:
            data["logo"] = request.build_absolute_uri(instance.logo.url)

        return data
