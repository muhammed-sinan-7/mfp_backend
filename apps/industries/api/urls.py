from django.urls import path

from .views import GetIndustries

urlpatterns = [
    path("", GetIndustries.as_view()),
]
