# -*- coding: utf-8 -*-

import os
import shutil
import tempfile
import json
import pytest

from ohmywod import create_app
from ohmywod.extensions import db as _db


@pytest.fixture(scope='session')
def app():
    # Create temp directories for testing session
    temp_data_dir = tempfile.mkdtemp()
    temp_upload_dir = tempfile.mkdtemp()

    class TestConfig(object):
        TESTING = True
        WTF_CSRF_ENABLED = False
        SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
        SQLALCHEMY_ECHO = False

        # Auth is SQLite-only now (HA-008); only Redis is still mocked.
        REDIS_MOCK = True
        CACHE_TYPE = 'simple'

        DATA_DIR = temp_data_dir
        UPLOAD_DIR = temp_upload_dir
        UPLOAD_DISK_USAGE_THRESHOLD = 0.99
        HEALTHZ_STORAGE_PATHS = (temp_data_dir,)
        SECRET_KEY = 'test_secret_key'

        FLASK_ADMIN_USERNAME = "admin"
        FLASK_ADMIN_PASSWD = "password"

    app = create_app(config=TestConfig)

    # Push application context
    ctx = app.app_context()
    ctx.push()

    yield app

    ctx.pop()

    # Clean up directories
    shutil.rmtree(temp_data_dir, ignore_errors=True)
    shutil.rmtree(temp_upload_dir, ignore_errors=True)


@pytest.fixture(autouse=True)
def _reset_login_state(app):
    # The session-scoped app context above is reused by every test-client
    # request (Flask only pushes a new app ctx if none is active for the
    # app), so flask-login's cached g._login_user leaks across tests.
    # Drop it so each test starts unauthenticated unless it logs in itself.
    yield
    from flask import g
    if '_login_user' in g:
        g.pop('_login_user')


@pytest.fixture(scope='function')
def db(app):
    _db.create_all()
    yield _db
    _db.session.remove()
    _db.drop_all()


@pytest.fixture(scope='function')
def client(app, db):
    return app.test_client()


@pytest.fixture(scope='function')
def runner(app):
    return app.test_cli_runner()


@pytest.fixture(scope='function')
def register_user(app, db):
    def _register(username, display_name, email, password):
        from ohmywod.controllers.user import UserController
        uc = UserController()
        uc.save(username, display_name, email, password)
        return uc.get_db_user(username)
    return _register


@pytest.fixture(scope='function')
def authenticated_client(client, register_user):
    username = "testuser"
    password = "password123"
    register_user(username, "Test User", "test@example.com", password)
    
    # Login via mock LDAP & session
    client.post('/login', data={
        'username': username,
        'password': password
    }, follow_redirects=True)
    
    return client
