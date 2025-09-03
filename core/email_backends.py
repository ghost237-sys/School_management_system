from __future__ import annotations

import json
import logging
from typing import Iterable

import requests
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.message import EmailMultiAlternatives, EmailMessage

logger = logging.getLogger(__name__)


class ResendEmailBackend(BaseEmailBackend):
    """
    Minimal Django email backend that sends messages via the Resend HTTP API.
    Requires RESEND_API_KEY in Django settings or environment.
    
    Docs: https://resend.com/docs/api-reference/emails/send-email
    """

    api_url = "https://api.resend.com/emails"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.api_key = getattr(settings, "RESEND_API_KEY", None)
        if not self.api_key and not getattr(settings, "DEBUG", False):
            # In production, fail early if key missing.
            raise RuntimeError(
                "RESEND_API_KEY is not configured. Set it in environment or settings."
            )

    def send_messages(self, email_messages: Iterable[EmailMessage]) -> int:
        if not email_messages:
            return 0

        sent = 0
        for message in email_messages:
            try:
                data = self._build_payload(message)
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }
                if not self.api_key:
                    # When DEBUG True but key missing, log and simulate send to avoid breaking flows.
                    logger.warning("RESEND_API_KEY not set. Email to %s not sent (DEBUG mode).", data.get("to"))
                    if self.fail_silently:
                        continue
                    raise RuntimeError("RESEND_API_KEY not set")

                resp = requests.post(self.api_url, headers=headers, data=json.dumps(data), timeout=30)
                if resp.status_code >= 200 and resp.status_code < 300:
                    sent += 1
                else:
                    detail = resp.text
                    logger.error("Resend send failed (%s): %s", resp.status_code, detail)
                    if not self.fail_silently:
                        raise RuntimeError(f"Resend error {resp.status_code}: {detail}")
            except Exception as e:
                logger.exception("Email send failed: %s", e)
                if not self.fail_silently:
                    raise
        return sent

    def _build_payload(self, message: EmailMessage) -> dict:
        from_email = message.from_email or getattr(settings, "DEFAULT_FROM_EMAIL", "onboarding@resend.dev")
        to = list(message.to or [])
        cc = list(getattr(message, "cc", []) or [])
        bcc = list(getattr(message, "bcc", []) or [])

        html_body = None
        text_body = message.body or ""
        if isinstance(message, EmailMultiAlternatives):
            # Prefer html alternative if present
            for content, mimetype in getattr(message, '_alternatives', []) or []:
                if mimetype == 'text/html':
                    html_body = content
                    break
        payload = {
            "from": from_email,
            "to": to,
            "subject": message.subject or "",
        }
        if html_body:
            payload["html"] = html_body
            if text_body:
                payload["text"] = text_body
        else:
            payload["text"] = text_body
        if cc:
            payload["cc"] = cc
        if bcc:
            payload["bcc"] = bcc
        return payload
