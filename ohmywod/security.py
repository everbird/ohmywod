# -*- coding: utf-8 -*-
"""Password hashing / verification for SQLite-backed auth (HA-008).

The ``user.password`` column stores a self-describing hash:

  * ``$argon2id$...`` for anything this app sets (registration, password change,
    operator reset) or lazily upgrades.
  * ``{SSHA}...`` imported verbatim from the retired OpenLDAP directory. These
    verify here and are re-hashed to Argon2id on the user's next successful
    login, so the SSHA values age out without forcing a password reset.
"""

import base64
import hashlib
import hmac

from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error

# Library defaults (Argon2id, m=64MiB, t=3, p=4). Tune here if needed later.
_hasher = PasswordHasher()


def hash_password(password):
    """Return a fresh Argon2id hash string for ``password``."""
    return _hasher.hash(password)


def verify_password(stored, password):
    """True iff ``password`` matches ``stored`` (Argon2id or LDAP {SSHA})."""
    if not stored:
        return False
    if stored.startswith("$argon2"):
        try:
            return _hasher.verify(stored, password)
        except Argon2Error:
            return False
    if stored[:6].upper() == "{SSHA}":
        return _verify_ssha(stored, password)
    # Unknown / legacy plaintext scheme -> never accept.
    return False


def needs_rehash(stored):
    """True if ``stored`` should be replaced by a fresh Argon2id hash.

    LDAP {SSHA} (and anything non-Argon2) always upgrades; an existing Argon2
    hash upgrades only when its parameters fall behind the current policy.
    """
    if not stored:
        return False
    if stored.startswith("$argon2"):
        try:
            return _hasher.check_needs_rehash(stored)
        except Argon2Error:
            return True
    return True


def _verify_ssha(stored, password):
    """Verify an LDAP ``{SSHA}`` value: base64(sha1(password + salt) + salt)."""
    try:
        decoded = base64.b64decode(stored[6:])
    except Exception:
        return False
    if len(decoded) < 20:
        return False
    digest, salt = decoded[:20], decoded[20:]
    calc = hashlib.sha1(password.encode("utf-8") + salt).digest()
    return hmac.compare_digest(calc, digest)
