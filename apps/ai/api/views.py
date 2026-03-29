from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.ai.services.post_service import PostService

from .serializers import GeneratePostSerializer


class GeneratePostView(APIView):

    def post(self, request):

        serializer = GeneratePostSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        service = PostService()

        result = service.generate_post(
            history=data["history"],
            platform=data["platform"],
            tone=data["tone"],
            audience=data["audience"],
        )

        return Response(result, status=status.HTTP_200_OK)
