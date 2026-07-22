# -*- coding: utf-8 -*-

from flask import request
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
