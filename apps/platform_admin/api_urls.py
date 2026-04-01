from django.urls import path

from .views import (
    AdminAuditLogListView,
    AdminOrganizationDetailView,
    AdminOrganizationListCreateView,
    AdminOrganizationRestoreView,
    AdminOverviewView,
    AdminPostDetailView,
    AdminPostListView,
    AdminPostRestoreView,
    AdminSocialAccountDetailView,
    AdminSocialAccountListView,
    AdminUserDetailView,
    AdminUserListCreateView,
)

urlpatterns = [
    path("overview/", AdminOverviewView.as_view()),
    path("users/", AdminUserListCreateView.as_view()),
    path("users/<uuid:user_id>/", AdminUserDetailView.as_view()),
    path("organizations/", AdminOrganizationListCreateView.as_view()),
    path("organizations/<uuid:organization_id>/", AdminOrganizationDetailView.as_view()),
    path("organizations/<uuid:organization_id>/restore/", AdminOrganizationRestoreView.as_view()),
    path("social-accounts/", AdminSocialAccountListView.as_view()),
    path("social-accounts/<uuid:account_id>/", AdminSocialAccountDetailView.as_view()),
    path("posts/", AdminPostListView.as_view()),
    path("posts/<uuid:post_id>/", AdminPostDetailView.as_view()),
    path("posts/<uuid:post_id>/restore/", AdminPostRestoreView.as_view()),
    path("audit-logs/", AdminAuditLogListView.as_view()),
]

