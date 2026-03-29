from django.urls import include, path

urlpatterns = [path("", include("apps.authentication.api.urls"))]
