# -*- coding: utf-8 -*-

from flask import current_app, has_app_context, request
from flask_admin import Admin, AdminIndexView, expose
from flask_admin.theme import Bootstrap4Theme
from flask_caching import Cache
from flask_limiter import Limiter
from flask_login import LoginManager
from flask_paginate import Pagination, get_page_args
from flask_redis import FlaskRedis
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect

from ohmywod.decorators import requires_auth


__all__ = ['db', 'admin']


def client_ip_key():
    """Rate-limit key = the real client IP.

    The Cloud Firewall restricts the origin's 80/443 to Cloudflare's ranges, so
    ``CF-Connecting-IP`` (set by Cloudflare, not forgeable by clients that can't
    bypass the firewall) is the trustworthy client IP. Fall back to the socket
    peer when the header is absent (direct/test access).
    """
    cf = request.headers.get("CF-Connecting-IP")
    if cf:
        return cf.strip()
    return request.remote_addr or "127.0.0.1"

class AuthAdminHome(AdminIndexView):
    @expose('/')
    @requires_auth
    def index(self):
        return self.render('admin_index.html')

db = SQLAlchemy()
admin = Admin(name='Admin of Ohmywod', index_view=AuthAdminHome(), theme=Bootstrap4Theme(swatch='darkly'))
login_manager = LoginManager()
redis = FlaskRedis()
cache = Cache()
csrf = CSRFProtect()
# No default/global limits: only login & register are decorated (IMP-006 gate),
# so every other endpoint is unaffected. Storage/enabled/fail-open are wired in
# app.configure_extensions.
limiter = Limiter(key_func=client_ip_key)


def _cache_warning(operation, key, error):
    if has_app_context():
        current_app.logger.warning(
            "application cache %s failed for %s: %s",
            operation,
            key,
            error.__class__.__name__,
        )


def cache_get(key):
    """Read the optional application cache without making it a hard dependency."""
    try:
        return cache.get(key)
    except Exception as error:
        _cache_warning("get", key, error)
        return None


def cache_set(key, value, timeout=None):
    """Write the optional application cache; requests still work if Redis is down."""
    try:
        return cache.set(key, value, timeout=timeout)
    except Exception as error:
        _cache_warning("set", key, error)
        return False


def cache_delete(key):
    """Invalidate a cache entry without failing a completed database write."""
    try:
        return cache.delete(key)
    except Exception as error:
        _cache_warning("delete", key, error)
        return False
