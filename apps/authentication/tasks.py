from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail


@shared_task
def send_otp_email_task(email, otp, purpose="email_verification"):
    is_password_reset = purpose == "password_reset"

    subject = (
        "Reset your password - MFP"
        if is_password_reset
        else "Verify your email - MFP"
    )
    intro = (
        "Use this OTP to reset your password."
        if is_password_reset
        else "Use this OTP to verify your email."
    )
    message = (
        f"Hello,\n\n{intro}\nOTP: {otp}\n\n"
        "This expires in 5 minutes.\n"
        "If you did not request this, please ignore this email.\n\n- MFP Team"
    )

    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
    )
