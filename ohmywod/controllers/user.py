#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from ldap3 import HASHED_SALTED_SHA
from ldap3.utils.hashed import hashed

from ohmywod.extensions import db, ldap_manager
from ohmywod.models.user import User, LDAPUser


class UserController:

    def save_ldap_user(self, username, email, passwd):
        dn = f'cn={username},ou=users,dc=everbird,dc=me'
        hashed_passwd = hashed(HASHED_SALTED_SHA, passwd)
        conn = ldap_manager.connection
        r = conn.add(
            dn,
            'inetOrgPerson',
            {
                "displayName": username,
                "mail": email,
                "sn": username,
                "userPassword": hashed_passwd,
            }
        )
        return r

    def save_db_user(self, username, email, passwd):
        user = User(username=username, email=email)
        db.session.add(user)
        db.session.commit()
        return user

    def save(self, username, email, passwd):
        if self.save_ldap_user(username, email, passwd):
            self.save_db_user(username, email, passwd)

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