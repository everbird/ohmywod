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
    temp_ldap_db_dir = tempfile.mkdtemp()
    mock_ldap_db_path = os.path.join(temp_ldap_db_dir, 'mock_ldap.json')

    # Setup initial empty mock LDAP database
    with open(mock_ldap_db_path, 'w', encoding='utf-8') as f:
        json.dump({}, f)

    class TestConfig(object):
        TESTING = True
        WTF_CSRF_ENABLED = False
        SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
        SQLALCHEMY_ECHO = False
        
        LDAP_MOCK = True
        REDIS_MOCK = True
        CACHE_TYPE = 'simple'
        
        MOCK_LDAP_DB = mock_ldap_db_path
        DATA_DIR = temp_data_dir
        UPLOAD_DIR = temp_upload_dir
        DISK_USAGE_THRESHOLD = 0.99
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
    shutil.rmtree(temp_ldap_db_dir, ignore_errors=True)


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
