# -*- coding: utf-8 -*-

from datetime import datetime

from flask_login import UserMixin

from ohmywod.extensions import db, login_manager, ldap_manager


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), index=True, unique=True)
    email = db.Column(db.String(150), unique = True, index = True)
    joined_at = db.Column(db.DateTime(), default = datetime.utcnow, index = True)


class LDAPUser(UserMixin):
    def __init__(self, dn, username, data):
        self.dn = dn
        self.username = username
        self.data = data

    def __repr__(self):
        return "<LDAPUser: dn={}, username={}>".format(self.dn, self.username)

    # Flask-Login will use this as parameter for the load_user()
    def get_id(self):
        return self.dn

    @property
    def db_user(self):
        return User.get(self.username)

    @classmethod
    def from_ldap_entry(cls, d):
        return LDAPUser(
            dn=d["dn"],
            username=d["cn"],
            data=d,
        )
