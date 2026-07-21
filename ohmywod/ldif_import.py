# -*- coding: utf-8 -*-
"""Import LDAP account password truth into the SQLite ``user`` table.

HA-008 slice 1 tooling. Consumes an LDIF dump (produced on the box with
``slapcat -o ldif-wrap=no``, which is also the encrypted rollback artifact) and
upserts each ``inetOrgPerson`` into SQLite:

  * missing username        -> create the row (username/display_name/email/
                               password, joined_at from createTimestamp);
  * existing row, no hash    -> fill ``password`` from LDAP;
  * existing row, has a hash  -> leave it (use ``--force`` to overwrite).

It only ever writes the ``password``/``password_updated_at``/identity of *new*
rows -- it never clobbers a display_name or email a user already edited in
SQLite. Passwords are stored verbatim as their self-describing ``{SSHA}`` value;
a later slice rehashes them to Argon2id on successful login. Purely additive and
idempotent: re-running with the same LDIF is a no-op.
"""

import base64
import re
from collections import namedtuple
from datetime import datetime

from ohmywod.models.user import User


LdifUser = namedtuple("LdifUser", "username display_name email password created_at")


def parse_ldif(text):
    """Parse LDIF text into a list of entries (attr -> list of str values).

    Handles RFC 2849 line folding (continuation lines start with a space) and
    base64 values (``attr:: <b64>``). Comment lines and the ``version:`` header
    are ignored.
    """
    entries = []
    current = {}
    # Unfold continuation lines first so a wrapped value is a single logical line.
    logical = []
    for raw in text.splitlines():
        if raw.startswith(" ") and logical:
            logical[-1] += raw[1:]
        else:
            logical.append(raw)

    for line in logical:
        if line == "":
            if current:
                entries.append(current)
                current = {}
            continue
        if line.startswith("#"):
            continue
        m = re.match(r"^([^:]+)::?\s?(.*)$", line)
        if not m:
            continue
        attr = m.group(1)
        # Distinguish "attr:: b64" from "attr: value" by re-checking the colon run.
        is_b64 = line[len(attr):].startswith("::")
        value = m.group(2)
        if is_b64:
            try:
                value = base64.b64decode(value).decode("utf-8", "replace")
            except Exception:
                value = ""
        if attr.lower() == "version" and not current:
            # LDIF stream header, not an attribute of an entry.
            continue
        current.setdefault(attr, []).append(value)
    if current:
        entries.append(current)
    return entries


def _first(entry, attr, default=""):
    for key, vals in entry.items():
        if key.lower() == attr.lower() and vals:
            return vals[0]
    return default


def _has_object_class(entry, name):
    for key, vals in entry.items():
        if key.lower() == "objectclass":
            return any(v.lower() == name.lower() for v in vals)
    return False


def _parse_generalized_time(value):
    """LDAP generalizedTime (``YYYYMMDDHHMMSSZ``) -> naive UTC datetime or None."""
    if not value:
        return None
    m = re.match(r"^(\d{14})Z?", value)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y%m%d%H%M%S")
    except ValueError:
        return None


def extract_users(entries):
    """Pull the ``inetOrgPerson`` accounts out of parsed LDIF entries."""
    users = []
    for entry in entries:
        if not _has_object_class(entry, "inetOrgPerson"):
            continue
        # Preserve the cn verbatim -- do NOT strip. A few production accounts
        # carry a trailing space in the username in BOTH LDAP and SQLite (the
        # LDIF DN shows it escaped as `\20`, and the cn value is base64). The app
        # created the SQLite row from the raw cn, so the upsert must match on the
        # raw value too: stripping would miss the existing row, create a
        # duplicate, and then collide on the unique email column at commit.
        username = _first(entry, "cn")
        if not username.strip():
            continue
        display_name = _first(entry, "displayName").strip() or username.strip()
        email = _first(entry, "mail").strip()
        password = _first(entry, "userPassword")
        created_at = _parse_generalized_time(_first(entry, "createTimestamp"))
        users.append(LdifUser(username, display_name, email, password, created_at))
    return users


def import_users(session, users, force=False, dry_run=False):
    """Upsert LDIF users into SQLite. Returns a stats dict.

    ``force`` overwrites an existing non-null password. ``dry_run`` computes the
    stats and leaves the session uncommitted / unflushed of new rows.
    """
    stats = {
        "total": len(users),
        "created": 0,
        "password_filled": 0,
        "password_overwritten": 0,
        "skipped_has_password": 0,
        "skipped_no_ldif_password": 0,
    }

    for u in users:
        existing = User.query.filter_by(username=u.username).first()
        if existing is None:
            if not u.password:
                stats["skipped_no_ldif_password"] += 1
                # Still create the identity row so the account is not lost.
            new_user = User(
                username=u.username,
                display_name=u.display_name,
                email=u.email or None,
                password=u.password or None,
                password_updated_at=None,
                joined_at=u.created_at or datetime.utcnow(),
            )
            if not dry_run:
                session.add(new_user)
            stats["created"] += 1
            continue

        if not u.password:
            stats["skipped_no_ldif_password"] += 1
            continue

        if existing.password and not force:
            stats["skipped_has_password"] += 1
            continue

        if existing.password and force:
            stats["password_overwritten"] += 1
        else:
            stats["password_filled"] += 1
        if not dry_run:
            existing.password = u.password

    if dry_run:
        session.rollback()
    else:
        session.commit()
    return stats


def run_import(ldif_path, force=False, dry_run=False):
    """Read an LDIF file and import its users using the app's db session."""
    from ohmywod.extensions import db

    with open(ldif_path, "r", encoding="utf-8") as f:
        text = f.read()
    users = extract_users(parse_ldif(text))
    return import_users(db.session, users, force=force, dry_run=dry_run)
