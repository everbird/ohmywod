# -*- coding: utf-8 -*-

class DefaultConfig(object):
    DEBUG = False
    SECRET_KEY = "<secret:secret_key>"

    # --- SQLAlchemy ---
    SQLALCHEMY_DATABASE_URI = "sqlite:////data/ohmywod/ohmywod_d.sqlite"
    SQLALCHEMY_ECHO = False

    # --- FLASK-LDAP3-LOGIN ---
    LDAP_HOST = 'everbird.me'
    LDAP_BASE_DN = 'dc=everbird,dc=me'
    LDAP_USER_DN = 'ou=users'
    LDAP_GROUP_DN = 'ou=groups'
    LDAP_USER_RDN_ATTR = 'cn'
    # The Attribute you want users to authenticate to LDAP with.
    LDAP_USER_LOGIN_ATTR = 'cn'
    # The Username to bind to LDAP with
    LDAP_BIND_USER_DN = "cn=admin,dc=everbird,dc=me"
    # The Password to bind to LDAP with
    LDAP_BIND_USER_PASSWORD = "<secret:ldap_passwd>"

    # Override the group => groupOfNames and person => inetOrgPerson
    LDAP_GROUP_OBJECT_FILTER = "(objectclass=groupOfNames)"
    LDAP_USER_OBJECT_FILTER = "(objectclass=inetOrgPerson)"
    # Need to support sign-up
    LDAP_READONLY = False

    # --- Upload ---
    DATA_DIR = "/data/ohmywod/report"
    UPLOAD_DIR = "/data/ohmywod/upload"


    FLASK_ADMIN_SWATCH = "darkly"
    FLASK_ADMIN_USERNAME = "<secret:flask_admin_username>"
    FLASK_ADMIN_PASSWD = "<secret:flask_admin_passwd>"
