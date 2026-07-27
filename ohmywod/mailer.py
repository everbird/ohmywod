# -*- coding: utf-8 -*-
"""Outbound mail helpers (PWR-002).

Thin wrapper over Flask-Mail so views don't build ``Message`` objects by hand.
Sending is best-effort: a mail failure is logged but never raised, so the
forgot-password view can return its uniform "if the address exists, we sent a
link" response without leaking outcome (and without 500-ing on an SMTP blip).
"""

from flask import current_app, render_template
from flask_mail import Message

from ohmywod.extensions import mail


def send_reset_email(user, reset_url):
    """Send the password-reset link to ``user``. Returns True on success.

    Never raises: on any failure it logs and returns False so the caller keeps
    its enumeration-safe behaviour.
    """
    try:
        msg = Message(
            subject="重置你的战报网密码",
            recipients=[user.email],
            body=render_template(
                "emails/reset_password.txt",
                user=user,
                reset_url=reset_url,
            ),
        )
        mail.send(msg)
        return True
    except Exception:
        current_app.logger.exception("failed to send password reset email")
        return False
