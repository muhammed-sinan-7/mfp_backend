"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions

from .views import health_check, readiness_check

schema_view = get_schema_view(
    openapi.Info(
        title="MFP API",
        default_version="v1",
        description="Modular SaaS Backend API for MFP",
        contact=openapi.Contact(email="support@mfp.com"),
        license=openapi.License(name="MIT License"),
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
)

urlpatterns = [
    path("", include("django_prometheus.urls")),
    path("admin/", admin.site.urls),
    path("health/", health_check),
    path("ready/", readiness_check),
    path("api/v1/auth/", include("apps.authentication.urls")),
    path("api/v1/organizations/", include("apps.organizations.api.urls")),
    path("api/v1/industries/", include("apps.industries.api.urls")),
    path("api/v1/audit/", include("apps.audit.api.urls")),
    path("api/v1/analytics/", include("apps.analytics.api.urls")),
    path("api/v1/social/", include("apps.social_accounts.api.urls")),
    path("api/v1/posts/", include("apps.posts.api.urls")),
    path("api/v1/news/", include("apps.news.api.urls")),
    path("api/v1/ai/", include("apps.ai.api.urls")),
    path(
        "swagger/", schema_view.with_ui("swagger", cache_timeout=0), name="swagger-ui"
    ),
    path("redoc/", schema_view.with_ui("redoc", cache_timeout=0), name="redoc-ui"),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
