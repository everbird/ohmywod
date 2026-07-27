# -*- coding: utf-8 -*-
"""Stateless password-reset tokens (PWR-001).

A reset link carries a signed, time-limited token instead of a database row, so
finding-your-password needs no new table, column, or migration (keeps SQLite the
single source of truth and out of the litestream / DR concern).

The token signs ``{uid, pw}`` where ``pw`` is a short fingerprint of the user's
current password hash. ``itsdangerous`` enforces expiry (``max_age``); the
fingerprint enforces one-time use: any successful password change re-hashes the
password (``UserController.set_password``), the fingerprint no longer matches,
and every previously issued link is silently invalidated.
"""

from flask import current_app
from itsdangerous import URLSafeTimedSerializer, BadData

from ohmywod.extensions import db
from ohmywod.models.user import User

# Namespaces the signature so a reset token can't be replayed as some other
# SECRET_KEY-signed value (or vice versa).
_SALT = "ohmywod-password-reset"

# How much of the password hash to bind into the token. The Argon2 tail changes
# whenever the password does, so a dozen chars is plenty to detect a reset.
_FINGERPRINT_LEN = 12

# Fallback lifetime if the app doesn't configure one (seconds).
_DEFAULT_MAX_AGE = 1800


def _serializer():
    # Built per call so it always uses the live SECRET_KEY (tests swap it).
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=_SALT)


def _fingerprint(user):
    return (user.password or "")[-_FINGERPRINT_LEN:]


def generate_reset_token(user):
    """Return a signed reset token for ``user``."""
    return _serializer().dumps({"uid": user.id, "pw": _fingerprint(user)})


def verify_reset_token(token, max_age=None):
    """Return the ``User`` for a valid, unexpired, unused token, else ``None``.

    Returns ``None`` for a tampered/garbage token, an expired one, a vanished
    user, or a token whose password fingerprint no longer matches (i.e. the
    password was changed after the link was issued).
    """
    if not token:
        return None
    if max_age is None:
        max_age = current_app.config.get(
            "PASSWORD_RESET_TOKEN_MAX_AGE", _DEFAULT_MAX_AGE
        )
    try:
        data = _serializer().loads(token, max_age=max_age)
    except BadData:
        # Covers SignatureExpired and BadSignature alike -> just "invalid".
        return None
    if not isinstance(data, dict):
        return None
    user = db.session.get(User, data.get("uid"))
    if user is None:
        return None
    if _fingerprint(user) != data.get("pw"):
        return None
    return user
