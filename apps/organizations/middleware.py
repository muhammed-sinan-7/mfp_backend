# from apps.organizations.models import OrganizationMember


# class OrganizationContextMiddleware:

#     def __init__(self, get_response):
#         self.get_response = get_response

#     def __call__(self, request):

#         request.organization = None
#         request.membership = None

#         user = getattr(request, "user", None)

#         if user and user.is_authenticated:
#             membership = OrganizationMember.objects.filter(
#                 user=user,
#                 is_deleted=False
#             ).select_related("organization").first()

#             if membership:
#                 request.organization = membership.organization
#                 request.membership = membership

#         response = self.get_response(request)
#         return response
