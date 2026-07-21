#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import click
from flask import (
    Flask, request, redirect, url_for, Response, current_app, render_template
)
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
    configure_error_handlers(app)
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
            
            # Reports are stored under JuiceFS; this is separate from local zip staging.
            jfs_path = app.config['DATA_DIR']
            try:
                if os.path.exists(jfs_path):
                    _, j_used, _ = shutil.disk_usage(jfs_path)
                    disk_info['jfs'] = {
                        'used': j_used,
                        'available': True
                    }
                else:
                    disk_info['jfs'] = {
                        'used': 0,
                        'available': False
                    }
            except Exception:
                disk_info['jfs'] = {
                    'used': 0,
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

    def _make_model_view(model_class, *args,
                         column_exclude_list=None,
                         form_excluded_columns=None,
                         **kwargs):

        class AuthModelView(sqla.ModelView):

            def is_accessible(self):
                auth = request.authorization
                return auth and check_auth(auth.username, auth.password)

            def inaccessible_callback(self, name, **kwargs):
                return Response(
                    'Could not verify your access level for that URL.\n'
                    'You have to login with proper credentials', 401,
                    {'WWW-Authenticate': 'Basic realm="Login Required"'})

        # Set as class attrs before instantiation: Flask-Admin scaffolds its
        # column/form caches in __init__, so post-hoc assignment wouldn't apply.
        if column_exclude_list is not None:
            AuthModelView.column_exclude_list = column_exclude_list
        if form_excluded_columns is not None:
            AuthModelView.form_excluded_columns = form_excluded_columns

        return AuthModelView(model_class, db, *args, **kwargs)

    admin.add_view(_make_model_view(Report, endpoint='report',
        category='Online'))
    admin.add_view(_make_model_view(ReportCategory, endpoint='category',
        category='Online'))
    admin.add_view(_make_model_view(ReportDetails, endpoint='report_details',
        category='Online'))
    admin.add_view(_make_model_view(User,
        endpoint='user', category='User',
        # HA-008: password is a hash, never edit/expose it through admin.
        column_exclude_list=['password'],
        form_excluded_columns=['password', 'password_updated_at']))
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


def configure_error_handlers(app):

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        # errors/500.html is standalone (no base.html) so a broken
        # extension/DB can't take the error page down with it.
        return render_template("errors/500.html"), 500


def configure_cli(app):

    @app.cli.command("init_db")
    def init_db():
        db.create_all()

    @app.cli.command("drop_db")
    def drop_db():
        db.drop_all()

    @app.cli.command("import-ldap-users")
    @click.option("--ldif", "ldif_path", required=True,
                  type=click.Path(exists=True, dir_okay=False),
                  help="Path to an LDIF dump (slapcat -o ldif-wrap=no).")
    @click.option("--force/--no-force", default=False,
                  help="Overwrite existing non-null passwords.")
    @click.option("--dry-run/--no-dry-run", default=False,
                  help="Report what would change without writing.")
    def import_ldap_users(ldif_path, force, dry_run):
        """HA-008: import LDAP account password truth into the user table."""
        from ohmywod.ldif_import import run_import
        stats = run_import(ldif_path, force=force, dry_run=dry_run)
        mode = "DRY-RUN (no writes)" if dry_run else "committed"
        click.echo(f"import-ldap-users [{mode}]:")
        for key in ("total", "created", "password_filled", "password_overwritten",
                    "skipped_has_password", "skipped_no_ldif_password"):
            click.echo(f"  {key}: {stats[key]}")


@login_manager.user_loader
def load_user(dn):
    uc = UserController()
    try:
        return uc.get_ldap_user(dn)
    except Exception:
        current_app.logger.exception(f"load_user failed for dn={dn}")


@ldap_manager.save_user
def save_user(dn, username, data, memberships):
    return LDAPUser.from_ldap_entry(data)


@login_manager.unauthorized_handler
def unauthorized_callback():
    return redirect(url_for('frontend.login') +'?next=' + request.path)
