from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.news.api.serializers import NewsArticleSerializer
from apps.news.selectors import get_industry_news
from apps.organizations.mixins import OrganizationContextMixin


@method_decorator(cache_page(60 * 5), name="dispatch")
class IndustryNewsAPIView(OrganizationContextMixin, APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):
        org = request.organization

        if not org or not org.industry:
            return Response({"results": [], "page": 1, "has_next": False})

        try:
            page = max(1, int(request.query_params.get("page", 1)))
        except ValueError:
            page = 1

        limit = 10

        articles = get_industry_news(
            industry_id=org.industry_id, page=page, limit=limit
        )

        serializer = NewsArticleSerializer(articles, many=True)

        return Response(
            {
                "results": serializer.data,
                "page": page,
                "has_next": len(articles) == limit,
            }
        )
