from django.urls import path

from .views import (
    EmptyRecycleBinView,
    PermanentDeletePostView,
    PostCreateAPIView,
    PostDeleteView,
    PostDetailView,
    PostListView,
    PostRestoreView,
    PostUpdateView,
    RecycleBinListView,
)

urlpatterns = [
    path("", PostListView.as_view()),
    path("create/", PostCreateAPIView.as_view()),
    path("<uuid:pk>/", PostDetailView.as_view()),
    path("<uuid:pk>/edit/", PostUpdateView.as_view()),
    path("<uuid:pk>/delete/", PostDeleteView.as_view()),
    path("<uuid:pk>/restore/", PostRestoreView.as_view()),
    path("<uuid:pk>/permanent-delete/", PermanentDeletePostView.as_view()),
    path("recycle-bin/", RecycleBinListView.as_view()),
    path("recycle-bin/empty/", EmptyRecycleBinView.as_view()),
]
