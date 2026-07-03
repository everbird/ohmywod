#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import click
from flask import Flask, request, redirect, url_for, Response
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
    db, admin, login_manager, ldap_manager, redis, cache, csrf
)
from ohmywod.decorators import check_auth
from ohmywod.models.favorite import Favorite
from ohmywod.models.feedback import Feedback
from ohmywod.models.report import Report, ReportCategory, ReportDetails
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

    @app.context_processor
    def inject_disk_usage():
        from ohmywod.extensions import cache
        import shutil
        import os
        disk_info = cache.get("disk_info")
        if disk_info is None:
            total, used, free = shutil.disk_usage("/")
            disk_info = {
                'total': total,
                'used': used,
                'free': free,
                'percent': round((used / total) * 100, 2)
            }
            
            # Extra disk usage check for /mnt/test001
            extra_path = "/mnt/test001"
            if os.path.exists(extra_path):
                try:
                    e_total, e_used, e_free = shutil.disk_usage(extra_path)
                    disk_info['extra'] = {
                        'total': e_total,
                        'used': e_used,
                        'free': e_free,
                        'percent': round((e_used / e_total) * 100, 2),
                        'available': True
                    }
                except Exception:
                    disk_info['extra'] = {
                        'total': 0,
                        'used': 0,
                        'free': 0,
                        'percent': 0.0,
                        'available': False
                    }
            else:
                disk_info['extra'] = {
                    'total': 0,
                    'used': 0,
                    'free': 0,
                    'percent': 0.0,
                    'available': False
                }

            # JuiceFS disk usage check for /mnt/jfs
            jfs_path = "/mnt/jfs"
            try:
                if os.path.exists(jfs_path):
                    _, j_used, _ = shutil.disk_usage(jfs_path)
                    disk_info['jfs'] = {
                        'used': j_used,
                        'est_s3': j_used * 2,
                        'available': True
                    }
                else:
                    disk_info['jfs'] = {
                        'used': 0,
                        'est_s3': 0,
                        'available': False
                    }
            except Exception:
                disk_info['jfs'] = {
                    'used': 0,
                    'est_s3': 0,
                    'available': False
                }

            cache.set("disk_info", disk_info, timeout=300)
        return dict(disk_info=disk_info)


def configure_extensions(app):
    db.init_app(app)
    login_manager.init_app(app)
    ldap_manager.init_app(app)
    csrf.init_app(app)

    if app.config.get('LDAP_MOCK', False):
        from ohmywod.ldap_mock import init_mock_ldap
        init_mock_ldap(ldap_manager, app)

    redis.init_app(app)

    if app.config.get('REDIS_MOCK', False):
        from ohmywod.ldap_mock import init_mock_redis
        init_mock_redis(redis)

    cache.init_app(app)

    def _make_model_view(model_class, *args, **kwargs):

        class AuthModelView(sqla.ModelView):

            def is_accessible(self):
                auth = request.authorization
                return auth and check_auth(auth.username, auth.password)

            def inaccessible_callback(self, name, **kwargs):
                return Response(
                    'Could not verify your access level for that URL.\n'
                    'You have to login with proper credentials', 401,
                    {'WWW-Authenticate': 'Basic realm="Login Required"'})

        return AuthModelView(model_class, db.session, *args, **kwargs)

    admin.add_view(_make_model_view(Report, endpoint='report',
        category='Online'))
    admin.add_view(_make_model_view(ReportCategory, endpoint='category',
        category='Online'))
    admin.add_view(_make_model_view(ReportDetails, endpoint='report_details',
        category='Online'))
    admin.add_view(_make_model_view(User,
        endpoint='user', category='User'))
    admin.add_view(_make_model_view(Favorite,
        endpoint='favorite', category='Misc'))
    admin.add_view(_make_model_view(Feedback,
        endpoint='feedback', category='Misc'))

    admin.init_app(app)

    # Flask-Admin ships its own auth gate (HTTP Basic, see AuthModelView
    # above) and its templates/JS were never wired up to send CSRF tokens.
    # Exempt it so the global CSRFProtect below doesn't 400 every admin
    # form submit/delete action.
    for bp in app.blueprints.values():
        if bp.url_prefix and bp.url_prefix.startswith('/admin'):
            csrf.exempt(bp)


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
