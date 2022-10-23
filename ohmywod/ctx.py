#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from flask_login import UserMixin

from ohmywod.extensions import login_manager, ldap_manager


class LDAPUser(UserMixin):
    def __init__(self, dn, username, data):
        self.dn = dn
        self.username = username
        self.data = data

    def __repr__(self):
        return self.dn

    def get_id(self):
        return self.dn


@login_manager.user_loader
def load_user(id):
    if id in users:
        return users[id]
    return None


@ldap_manager.save_user
def save_user(dn, username, data, memberships):
    user = LDAPUser(dn, username, data)
    users[dn] = user
    return user


users = {}
