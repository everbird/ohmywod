# -*- coding: utf-8 -*-

from datetime import datetime

from flask_login import UserMixin

from ohmywod.extensions import db, login_manager, ldap_manager


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), index=True, unique=True)
    display_name = db.Column(db.String(255))
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
        return User.query.filter_by(username=self.username).first()

    @property
    def display_name(self):
        return self.data.get('displayName')

    @property
    def reader_theme(self):
        # Even this looks weird, but just save the theme to
        # "departmentNumber" to avoid creating a new table in DB
        r = self.data.get('departmentNumber')
        if r:
            return int(r[0])

    @classmethod
    def from_ldap_entry(cls, d):
        return LDAPUser(
            dn=d["dn"],
            username=d["cn"][0],
            data=d,
        )

    @property
    def app_theme(self):
        r = self.data.get('employeeNumber')
        if r:
            return r

    @property
    def theme_css(self):
        # similar to reader_theme
        if self.app_theme:
            return "css/themes/{}/bootstrap.min.css".format(self.app_theme)

        return "css/bootstrap.min.css"
