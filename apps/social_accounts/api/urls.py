from django.urls import path

from .views import (
    LinkedInCallbackView,
    LinkedInConnectView,
    MetaCallbackView,
    MetaConnectView,
    PublishingTargetListAPIView,
    SocialAccountDisconnectView,
    SocialAccountListView,
    SocialAccountRefreshView,
    YouTubeCallbackView,
    YouTubeConnectView,
)

urlpatterns = [
    path("", SocialAccountListView.as_view()),
    path("meta/connect/", MetaConnectView.as_view()),
    path("meta/callback/", MetaCallbackView.as_view()),
    path("linkedin/connect/", LinkedInConnectView.as_view()),
    path("linkedin/callback/", LinkedInCallbackView.as_view()),
    path("youtube/connect/", YouTubeConnectView.as_view()),
    path("youtube/callback/", YouTubeCallbackView.as_view()),
    path("publishing-targets/", PublishingTargetListAPIView.as_view()),
    path("accounts/<uuid:account_id>/refresh/", SocialAccountRefreshView.as_view()),
    path(
        "accounts/<uuid:account_id>/disconnect/", SocialAccountDisconnectView.as_view()
    ),
]
