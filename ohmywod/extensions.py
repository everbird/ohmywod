# -*- coding: utf-8 -*-

from flask_admin import Admin, AdminIndexView, expose
from flask_admin.theme import Bootstrap4Theme
from flask_caching import Cache
from flask_login import LoginManager
from flask_paginate import Pagination, get_page_args
from flask_redis import FlaskRedis
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect

from ohmywod.decorators import requires_auth


__all__ = ['db', 'admin']

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
