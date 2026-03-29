from .models import AuditLog


def get_client_ip(request):
    x_forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded:
        return x_forwarded.split(",")[0]
    return request.META.get("REMOTE_ADDR")


def log_event(
    *,
    actor=None,
    organization=None,
    action,
    request=None,
    target_model=None,
    target_id=None,
    metadata=None,
):
    ip = None
    agent = None

    if request:
        ip = get_client_ip(request)
        agent = request.META.get("HTTP_USER_AGENT")

    AuditLog.objects.create(
        actor=actor,
        organization=organization,
        action=action,
        target_model=target_model,
        target_id=target_id,
        ip_address=ip,
        user_agent=agent,
        metadata=metadata or {},
    )
