#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import click
from flask import Flask, request, redirect, url_for
from flask_admin.contrib import sqla
from flask_ldap3_login import LDAP3LoginManager
from flask_login import LoginManager

from ohmywod import views
from ohmywod.config import DefaultConfig
from ohmywod.controllers.user import UserController

try:
    from ohmywod.local_config import DefaultConfig
except ImportError as e:
    if e.args[0].startswith('No module named'):
        pass
    else:
        # the ImportError is raised inside local_config
        raise

from ohmywod.extensions import (
    db, admin, login_manager, ldap_manager, redis, cache
)
from ohmywod.decorators import check_auth
from ohmywod.models.favorite import Favorite
from ohmywod.models.feedback import Feedback
from ohmywod.models.report import Report, ReportCategory
from ohmywod.models.user import User, LDAPUser


__all__ = ['create_app']

DEFAULT_APP_NAME = "ohmywod"

DEFAULT_MODULES = (
    (views.frontend, ""),
    (views.report, "/r"),
    (views.upload, "/upload"),
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
    redis.init_app(app)
    cache.init_app(app)

    def _make_model_view(model_class, *args, **kwargs):

        class AuthModelView(sqla.ModelView):

            def is_accessible(self):
                auth = request.authorization
                return auth and check_auth(auth.username, auth.password)

        return AuthModelView(model_class, db.session, *args, **kwargs)

    admin.add_view(_make_model_view(Report, endpoint='report',
        category='Online'))
    admin.add_view(_make_model_view(ReportCategory, endpoint='category',
        category='Online'))
    admin.add_view(_make_model_view(User,
        endpoint='user', category='User'))
    admin.add_view(_make_model_view(Favorite,
        endpoint='favorite', category='Misc'))
    admin.add_view(_make_model_view(Feedback,
        endpoint='feedback', category='Misc'))

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


@login_manager.user_loader
def load_user(dn):
    uc = UserController()
    try:
        return uc.get_ldap_user(dn)
    except Exception as ex:
        print(str(ex))


@ldap_manager.save_user
def save_user(dn, username, data, memberships):
    return LDAPUser.from_ldap_entry(data)


@login_manager.unauthorized_handler
def unauthorized_callback():
    return redirect(url_for('frontend.login') +'?next=' + request.path)
