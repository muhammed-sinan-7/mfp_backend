from django.urls import path

from .views import GeneratePostView

urlpatterns = [
    # path('test/',AITestView.as_view()),
    path("generate-post/", GeneratePostView.as_view()),
]
