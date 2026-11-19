"""Plain-text transactional email helper."""

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def absolute_url(path):
    return f"{settings.BASE_URL}{path}"


def send_templated_email(template_name, context, recipients):
    """
    Render ``emails/<template_name>.txt`` (first line is the subject) and send it.

    Delivery failures are logged instead of breaking the user's request; email is a
    notification channel, never part of a business transaction.
    """
    recipients = [r for r in recipients if r]
    if not recipients:
        return 0
    context = {"site_name": "CoreCart", "base_url": settings.BASE_URL, **context}
    rendered = render_to_string(f"emails/{template_name}.txt", context).strip()
    subject, _, body = rendered.partition("\n")
    try:
        return send_mail(subject.strip(), body.strip(), settings.DEFAULT_FROM_EMAIL, recipients)
    except Exception:  # pragma: no cover - depends on the mail transport
        logger.exception("Failed to send '%s' email to %s", template_name, recipients)
        return 0
