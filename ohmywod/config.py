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

    # --- Afdian (爱发电) read-only sponsor wall (AFD-002) ---
    # Credentials for the read-only query-sponsor API. Both default empty so the
    # sponsor wall stays inert until provisioned; ohmywod/afdian.py treats an
    # empty (or unrendered "<secret:...>") value as "not configured" and degrades.
    # Production values are rendered by the ohmywod-ops app role:
    # AFDIAN_USER_ID (non-secret) from group_vars vars.yml, AFDIAN_TOKEN (secret)
    # from secrets.sops.yaml. This class is only the schema reference — runtime
    # uses local_config.py, so populating it here does NOT reach any environment.
    AFDIAN_USER_ID = ""
    AFDIAN_TOKEN = ""
    # Sponsor-wall cache freshness (AFD-003), seconds. Balances display freshness
    # against source-site load; afdian.get_sponsors falls back to this default
    # (3600 = 1h) when unset. A long-lived "last good" copy is kept separately so
    # a transient Afdian failure degrades to the previous result, not an empty wall.
    AFDIAN_CACHE_TTL = 3600


# --- Afdian (爱发电) support entrance (AFD-001) ---
# Single source of truth for the sponsorship page URL. Kept as a module-level
# constant (not a DefaultConfig attribute) because local/production runs replace
# DefaultConfig wholesale via ohmywod/local_config.py, so a class attribute here
# would not reach those environments. app.py injects this into templates as
# `afdian_url` via a context processor, so the entrance stays wired in exactly
# one place across every environment. Public (non-secret); change the homepage by
# editing only this line.
AFDIAN_URL = "https://ifdian.net/a/everbird"


# --- Google Analytics (gtag.js) toggle (GAP-006) ---
# Public (non-secret) GA4 measurement id. Kept as a module-level constant for the
# same reason as AFDIAN_URL above: production replaces DefaultConfig wholesale via
# local_config.py, so a class attribute would not reach it. app.py injects this as
# `google_analytics_id` via a context processor. Set to "" to disable analytics
# entirely — base.html renders nothing when it is empty. Even when set, the tag is
# lazy-loaded after the load event so it never competes with first paint (it used
# to pend for a long time on mainland-China networks).
GOOGLE_ANALYTICS_ID = "G-TYGCT601XW"
