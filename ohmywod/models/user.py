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
    # HA-008: SQLite becomes the password truth. Holds a self-describing hash
    # ({SSHA} imported from LDAP, or $argon2id$ once a later slice rehashes on
    # login). Nullable and unused for auth in this slice -- login still goes
    # through LDAP. Kept out of the Flask-Admin User view (see app.py).
    password = db.Column(db.String(255))
    password_updated_at = db.Column(db.DateTime())


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
        user = User.query.filter_by(username=self.username).first()
        if not user:
            email = self.data.get('mail')
            if isinstance(email, list):
                email = email[0] if email else ''
            elif not email:
                email = ''
            
            display_name = self.data.get('displayName')
            if isinstance(display_name, list):
                display_name = display_name[0] if display_name else self.username
            elif not display_name:
                display_name = self.username
            
            user = User(username=self.username, display_name=display_name, email=email)
            db.session.add(user)
            db.session.commit()
        return user

    @property
    def display_name(self):
        return self.data.get('displayName')

    @property
    def reader_theme(self):
        # Default reader theme
        return 4

    @property
    def app_theme(self):
        # No custom app theme
        return None

    @property
    def theme_css(self):
        # Default bootstrap style sheet
        return "css/bootstrap.min.css"

    @classmethod
    def from_ldap_entry(cls, d):
        if isinstance(d, (tuple, list)):
            d = d[0]
        dn = d.get("dn")
        if isinstance(dn, (tuple, list)):
            dn = dn[0]
        username = d.get("cn")
        if isinstance(username, list):
            username = username[0]
        elif isinstance(username, (tuple, list)):
            username = username[0]
        return LDAPUser(
            dn=dn,
            username=username,
            data=d,
        )
