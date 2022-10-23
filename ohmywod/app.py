#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import click
from flask import Flask, request
from flask_admin.contrib import sqla
from flask_ldap3_login import LDAP3LoginManager
from flask_login import LoginManager

from ohmywod import views
from ohmywod.config import DefaultConfig

try:
    from ohmywod.local_config import DefaultConfig
except ImportError as e:
    if e.args[0].startswith('No module named'):
        pass
    else:
        # the ImportError is raised inside local_config
        raise

from ohmywod.ctx import users, LDAPUser
from ohmywod.extensions import db, admin, login_manager, ldap_manager
from ohmywod.models.report import Report
from ohmywod.models.user import User


__all__ = ['create_app']

DEFAULT_APP_NAME = "ohmywod"

DEFAULT_MODULES = (
    (views.frontend, ""),
)


def create_app(config=None, app_name=None, modules=None):
    if app_name is None:
        app_name = DEFAULT_APP_NAME
    if modules is None:
        modules = DEFAULT_MODULES
    app = Flask(app_name)

    configure_app(app, config)

    configure_extensions(app)
    configure_modules(app, modules)
    configure_cli(app)

    return app


def configure_app(app, config):
    app.config.from_object(DefaultConfig())
    if config is not None:
        app.config.from_object(config)
    app.config.from_envvar('APP_CONFIG', silent=True)


def configure_extensions(app):
    db.init_app(app)
    login_manager.init_app(app)
    ldap_manager.init_app(app)

    def check_auth(username, password):
        return username == 'admin' and password == 'secret'

    def _make_model_view(model_class, *args, **kwargs):

        class AuthModelView(sqla.ModelView):

            def is_accessible(self):
                auth = request.authorization
                return auth and check_auth(auth.username, auth.password)

        return AuthModelView(model_class, db.session, *args, **kwargs)

    admin.add_view(_make_model_view(Report, endpoint='report',
        category='Online'))
    admin.add_view(_make_model_view(User,
        endpoint='user', category='User'))

    admin.init_app(app)


def configure_modules(app, modules):
    for module, url_prefix in modules:
        app.register_blueprint(module, url_prefix=url_prefix)


def configure_cli(app):

    @app.cli.command("init_db")
    def init_db():
        db.create_all()

    @app.cli.command("drop_db")
    def drop_db():
        db.drop_all()