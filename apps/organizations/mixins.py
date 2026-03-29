from apps.organizations.models import OrganizationMember


class OrganizationContextMixin:

    def initial(self, request, *args, **kwargs):

        request.organization = None
        request.membership = None

        user = request.user

        if user and user.is_authenticated:
            membership = (
                OrganizationMember.objects.filter(user=user, is_deleted=False)
                .select_related("organization")
                .first()
            )

            if membership:
                request.organization = membership.organization
                request.membership = membership

        super().initial(request, *args, **kwargs)
