# -*- coding: utf-8 -*-

from flask_admin import Admin, AdminIndexView, expose
from flask_ldap3_login import LDAP3LoginManager
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy

from ohmywod.decorators import requires_auth


__all__ = ['db', 'admin']

class AuthAdminHome(AdminIndexView):
    @expose('/')
    @requires_auth
    def index(self):
        return self.render('admin_index.html')

db = SQLAlchemy()
admin = Admin(name='Admin of Seer', index_view=AuthAdminHome())
login_manager = LoginManager()
ldap_manager = LDAP3LoginManager()