# -*- coding: utf-8 -*-

class DefaultConfig(object):
    DEBUG = False
    SECRET_KEY = "<secret:secret_key>"

    # Site is HTTPS-only (behind nginx); harden the session cookie.
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # --- SQLAlchemy ---
    SQLALCHEMY_DATABASE_URI = "sqlite:////data/ohmywod/ohmywod_d.sqlite"
    SQLALCHEMY_ECHO = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "connect_args": {
            "timeout": 5,
        },
    }

    # --- Upload ---
    # Reports are persisted in JuiceFS; UPLOAD_DIR is only local staging for zips.
    DATA_DIR = "/mnt/jfs/reports"
    UPLOAD_DIR = "/data/ohmywod/upload"
    UPLOAD_DISK_USAGE_THRESHOLD = 0.96
    HEALTHZ_STORAGE_PATHS = (DATA_DIR,)


    FLASK_ADMIN_SWATCH = "darkly"
    FLASK_ADMIN_USERNAME = "<secret:flask_admin_username>"
    FLASK_ADMIN_PASSWD = "<secret:flask_admin_passwd>"
