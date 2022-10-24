# -*- coding: utf-8 -*-

class DefaultConfig(object):
    DEBUG = False
    SECRET_KEY = "6e848025ab466c03faa992f11cfb132be8b6935dbb0bb358898163ca2bc9e3f8"

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
    LDAP_BIND_USER_PASSWORD = "2Bornot2Bldap"

    # Override the group => groupOfNames and person => inetOrgPerson
    LDAP_GROUP_OBJECT_FILTER = "(objectclass=groupOfNames)"
    LDAP_USER_OBJECT_FILTER = "(objectclass=inetOrgPerson)"
    # Need to support sign-up
    LDAP_READONLY = False

    # --- Upload ---
    DATA_DIR = "/data/ohmywod/report"
    UPLOAD_DIR = "/data/ohmywod/upload"


    FLASK_ADMIN_SWATCH = "cerulean"
