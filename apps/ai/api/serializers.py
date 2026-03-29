from rest_framework import serializers


class GeneratePostSerializer(serializers.Serializer):
    history = serializers.ListField()

    platform = serializers.CharField()
    tone = serializers.CharField()
    audience = serializers.CharField(required=False, allow_blank=True)


class HashtagGenerateSerializer(serializers.Serializer):

    content = serializers.CharField(max_length=2000)
    industry = serializers.CharField(max_length=200)

    platform = serializers.ChoiceField(choices=["instagram", "linkedin", "youtube"])


class CaptionRewriteSerializer(serializers.Serializer):

    caption = serializers.CharField(max_length=2000)

    platform = serializers.ChoiceField(choices=["instagram", "linkedin", "youtube"])

    mode = serializers.ChoiceField(choices=["improve", "professional", "engaging"])


class ContentIdeasSerializer(serializers.Serializer):
    industry = serializers.CharField(max_length=100)
    platform = serializers.ChoiceField(
        choices=["instagram", "linkedin", "twitter", "youtube"]
    )
    audience = serializers.CharField(max_length=200)
