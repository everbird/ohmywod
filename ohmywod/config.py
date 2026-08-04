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

    # Shared, explicitly configured application cache. Production and local
    # development already run redis-cache on 7379; a shared backend keeps
    # sitemap invalidation coherent across Gunicorn workers.
    CACHE_TYPE = "RedisCache"
    CACHE_REDIS_URL = "redis://localhost:7379/0"
    CACHE_KEY_PREFIX = "flask_cache_"

    # --- Upload ---
    # Reports are persisted in JuiceFS; UPLOAD_DIR is only local staging for zips.
    DATA_DIR = "/mnt/jfs/reports"
    UPLOAD_DIR = "/data/ohmywod/upload"
    UPLOAD_DISK_USAGE_THRESHOLD = 0.96
    HEALTHZ_STORAGE_PATHS = (DATA_DIR,)


    FLASK_ADMIN_SWATCH = "darkly"
    FLASK_ADMIN_USERNAME = "<secret:flask_admin_username>"
    FLASK_ADMIN_PASSWD = "<secret:flask_admin_passwd>"

    # --- Mail (PWR-002, Resend SMTP) ---
    # Only MAIL_PASSWORD (the Resend API key) is secret; everything else is
    # public. From must be on a Resend-verified domain (wod.everbird.me).
    MAIL_SERVER = "smtp.resend.com"
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = "resend"
    MAIL_PASSWORD = "<secret:smtp_password>"
    MAIL_DEFAULT_SENDER = ("Ohmywod", "noreply@wod.everbird.me")

    # Reset links must be absolute HTTPS (site is HTTPS-only behind nginx);
    # url_for(..., _external=True) uses this scheme.
    PREFERRED_URL_SCHEME = "https"
    # Reset-token lifetime in seconds (30 min).
    PASSWORD_RESET_TOKEN_MAX_AGE = 1800


# --- Afdian (爱发电) support entrance (AFD-001) ---
# Single source of truth for the sponsorship page URL. Kept as a module-level
# constant (not a DefaultConfig attribute) because local/production runs replace
# DefaultConfig wholesale via ohmywod/local_config.py, so a class attribute here
# would not reach those environments. app.py injects this into templates as
# `afdian_url` via a context processor, so the entrance stays wired in exactly
# one place across every environment. Public (non-secret); change the homepage by
# editing only this line.
AFDIAN_URL = "https://ifdian.net/a/everbird"
