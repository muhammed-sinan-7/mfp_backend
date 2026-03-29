from rest_framework.permissions import BasePermission


class HasOrganization(BasePermission):
    message = "Organization onboarding required."

    def has_permission(self, request, view):
        return hasattr(request, "organization") and request.organization is not None


class RolePermission(BasePermission):
    allowed_roles = []

    def has_permission(self, request, view):
        membership = getattr(request, "membership", None)

        if not membership:
            return False

        return membership.role in self.allowed_roles


class IsOwner(RolePermission):
    allowed_roles = ["OWNER"]


class IsAdminOrOwner(RolePermission):
    allowed_roles = ["OWNER", "ADMIN"]


class IsEditorOrAbove(RolePermission):
    allowed_roles = ["OWNER", "ADMIN", "EDITOR"]


class IsViewerOrAbove(RolePermission):
    allowed_roles = ["OWNER", "ADMIN", "EDITOR", "VIEWER"]
