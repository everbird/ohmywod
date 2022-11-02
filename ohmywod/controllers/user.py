#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json

from ldap3 import HASHED_SALTED_SHA, SUBTREE
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
        if self.save_ldap_user(username, display_name, email, passwd):
            self.save_db_user(username, display_name, email, passwd)

            return True
        return False

    def get_db_user(self, username):
        return User.get(username)

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
