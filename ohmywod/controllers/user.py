#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json

from ldap3 import HASHED_SALTED_SHA, SUBTREE, MODIFY_REPLACE
from ldap3.utils.hashed import hashed

from ohmywod.extensions import db, ldap_manager
from ohmywod.models.user import User, LDAPUser


class UserController:

    def save_ldap_user(self, username, display_name, email, passwd):
        dn = f'cn={username},ou=users,dc=everbird,dc=me'
        hashed_passwd = hashed(HASHED_SALTED_SHA, passwd)
        conn = ldap_manager.connection
        r = conn.add(
            dn,
            'inetOrgPerson',
            {
                "displayName": display_name,
                "mail": email,
                "sn": username,
                "userPassword": hashed_passwd,
            }
        )
        return r

    def save_db_user(self, username, display_name, email, passwd):
        user = User(username=username, display_name=display_name, email=email)
        db.session.add(user)
        db.session.commit()
        return user

    def save(self, username, display_name, email, passwd):
        display_name = display_name or username
        if self.save_ldap_user(username, display_name, email, passwd):
            self.save_db_user(username, display_name, email, passwd)

            return True
        return False

    def get_db_user(self, username):
        return User.query.filter_by(username=username).first()

    def get_ldap_user(self, dn):
        d = ldap_manager.get_user_info(dn)
        if d:
            return LDAPUser.from_ldap_entry(d)

    def get_ldap_user_by_username(self, username):
        d = ldap_manager.get_user_info_for_username(username)
        if d:
            return LDAPUser.from_ldap_entry(d)

    def get_db_user_by_email(self, email):
        return User.query.filter_by(email=email).first()

    def get_ldap_user_by_email(self, email):
        conn = ldap_manager.connection
        result = conn.search(
            "dc=everbird,dc=me",
            "(&(objectClass=inetOrgPerson)(mail={}))".format(email),
            SUBTREE,
            attributes=['*']
        )
        if result:
            entry = conn.entries[0]
            data = json.loads(entry.entry_to_json())
            _entry = dict(
                dn=data['dn'],
                **data['attributes']
            )
            return LDAPUser.from_ldap_entry(_entry)

    def get_db_user_by_display_name(self, display_name):
        return User.query.filter_by(display_name=display_name).first()

    def update_user(self, username,
                    display_name=None,
                    email=None,
                    password=None,
                    reader_theme=None
                    ):
        ldap_user = self.get_ldap_user_by_username(username)
        if display_name or email or password or reader_theme:
            conn = ldap_manager.connection
            d = {}
            if display_name:
                d['displayName'] = [(MODIFY_REPLACE, [display_name])]

            if email:
                d['mail'] = [(MODIFY_REPLACE, [email])]

            if password:
                hashed_passwd = hashed(HASHED_SALTED_SHA, password)
                d['userPassword'] = [(MODIFY_REPLACE, [hashed_passwd])]

            if reader_theme:
                d['departmentNumber'] = [(MODIFY_REPLACE, [str(reader_theme)])]

            conn.modify(ldap_user.dn, d)
