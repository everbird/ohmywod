# -*- coding: utf-8 -*-

from datetime import datetime

from flask_login import UserMixin

from ohmywod.extensions import db


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), index=True, unique=True)
    display_name = db.Column(db.String(255))
    email = db.Column(db.String(150), unique = True, index = True)
    joined_at = db.Column(db.DateTime(), default = datetime.utcnow, index = True)
    # HA-008: SQLite is the password truth. Holds a self-describing hash
    # ({SSHA} imported from LDAP, upgraded to $argon2id$ on next login). Kept out
    # of the Flask-Admin User view (see app.py). Flask-Login's get_id() returns
    # the primary key, so sessions minted before the LDAP->SQLite cutover (which
    # stored an LDAP DN) no longer resolve and are transparently logged out.
    password = db.Column(db.String(255))
    password_updated_at = db.Column(db.DateTime())
