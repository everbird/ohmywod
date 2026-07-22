#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from datetime import datetime

from sqlalchemy import func

from ohmywod.extensions import db
from ohmywod.models.user import User
from ohmywod import security


class UserController:
    """SQLite-backed user identity (HA-008: LDAP retired from the auth path)."""

    def get_db_user(self, username):
        return User.query.filter_by(username=username).first()

    def get_db_user_by_email(self, email):
        return User.query.filter_by(email=email).first()

    def get_db_user_by_display_name(self, display_name):
        return User.query.filter_by(display_name=display_name).first()

    def get_by_login(self, username):
        # Case-insensitive match, mirroring LDAP cn (caseIgnoreMatch) so existing
        # users keep logging in with any casing.
        return User.query.filter(
            func.lower(User.username) == (username or "").lower()
        ).first()

    def authenticate(self, username, password):
        """Return the User on success, else None. Lazily upgrades the hash."""
        user = self.get_by_login(username)
        if user is None:
            return None
        if not security.verify_password(user.password, password):
            return None
        # Re-hash imported LDAP {SSHA} (or a stale Argon2 hash) to current policy
        # now that we have the plaintext. Best-effort: a failure here must not
        # block a valid login.
        if security.needs_rehash(user.password):
            try:
                user.password = security.hash_password(password)
                user.password_updated_at = datetime.utcnow()
                db.session.add(user)
                db.session.commit()
            except Exception:
                db.session.rollback()
        return user

    def save(self, username, display_name, email, passwd):
        """Create a new user with an Argon2id password. Returns the User."""
        display_name = display_name or username
        user = User(
            username=username,
            display_name=display_name,
            email=email,
            password=security.hash_password(passwd),
            password_updated_at=datetime.utcnow(),
        )
        db.session.add(user)
        db.session.commit()
        return user

    def set_password(self, username, password):
        """Operator / self-service password reset. Returns the User or None."""
        user = self.get_db_user(username)
        if user is None:
            return None
        user.password = security.hash_password(password)
        user.password_updated_at = datetime.utcnow()
        db.session.add(user)
        db.session.commit()
        return user

    def update_user(self, username, display_name=None, email=None, password=None):
        user = self.get_db_user(username)
        if user is None:
            return None
        if display_name:
            user.display_name = display_name
        if email:
            user.email = email
        if password:
            user.password = security.hash_password(password)
            user.password_updated_at = datetime.utcnow()
        db.session.add(user)
        db.session.commit()
        return user
