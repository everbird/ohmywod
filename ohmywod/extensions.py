# -*- coding: utf-8 -*-

from flask_admin import Admin, AdminIndexView, expose
from flask_caching import Cache
from flask_ldap3_login import LDAP3LoginManager
from flask_login import LoginManager
from flask_paginate import Pagination, get_page_args
from flask_redis import FlaskRedis
from flask_sqlalchemy import SQLAlchemy

from ohmywod.decorators import requires_auth


__all__ = ['db', 'admin']

class AuthAdminHome(AdminIndexView):
    @expose('/')
    @requires_auth
    def index(self):
        return self.render('admin_index.html')

db = SQLAlchemy()
admin = Admin(name='Admin of Ohmywod', index_view=AuthAdminHome(), template_mode='bootstrap3')
login_manager = LoginManager()
ldap_manager = LDAP3LoginManager()
redis = FlaskRedis()
cache = Cache()
