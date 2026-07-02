# -*- coding: utf-8 -*-

import base64
import hashlib
import json
import os
import re
from ldap3 import SUBTREE
from flask_ldap3_login import AuthenticationResponse, AuthenticationResponseStatus

def verify_password(stored_hash, password):
    if not stored_hash:
        return False
    if isinstance(stored_hash, list):
        stored_hash = stored_hash[0]
    
    if stored_hash.upper().startswith('{SSHA}'):
        try:
            encoded = stored_hash[6:]
            decoded = base64.b64decode(encoded)
            sha_hash = decoded[:20]
            salt = decoded[20:]
            h = hashlib.sha1()
            h.update(password.encode('utf-8'))
            h.update(salt)
            return h.digest() == sha_hash
        except Exception:
            return False
    else:
        return stored_hash == password

class MockLDAPEntry:
    def __init__(self, dn, attributes):
        self.dn = dn
        self.attributes = attributes
        
    def entry_to_json(self):
        return json.dumps({
            'dn': self.dn,
            'attributes': self.attributes
        })

class MockLDAPConnection:
    def __init__(self, db_path):
        self.db_path = db_path
        self.entries = []
    
    def _load_db(self):
        if not os.path.exists(self.db_path):
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            with open(self.db_path, 'w', encoding='utf-8') as f:
                json.dump({}, f, indent=4)
            return {}
        try:
            with open(self.db_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_db(self, db_data):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with open(self.db_path, 'w', encoding='utf-8') as f:
            json.dump(db_data, f, indent=4)

    def add(self, dn, object_class, attributes):
        db_data = self._load_db()
        match = re.search(r'cn=([^,]+)', dn)
        username = match.group(1) if match else dn
        
        stored_attrs = {}
        for k, v in attributes.items():
            if isinstance(v, list):
                stored_attrs[k] = v
            else:
                stored_attrs[k] = [v]
        
        stored_attrs['dn'] = dn
        stored_attrs['cn'] = [username]
        
        db_data[username.lower()] = {
            'dn': dn,
            'attributes': stored_attrs
        }
        self._save_db(db_data)
        return True

    def search(self, search_base, search_filter, search_scope=SUBTREE, attributes=None):
        db_data = self._load_db()
        self.entries = []
        
        mail_match = re.search(r'mail=([^)]+)', search_filter)
        if mail_match:
            email_val = mail_match.group(1).strip().lower()
            for username, user_data in db_data.items():
                mails = user_data['attributes'].get('mail', [])
                if any(m.lower() == email_val for m in mails):
                    self.entries.append(MockLDAPEntry(user_data['dn'], user_data['attributes']))
                    return True
            return False
            
        cn_match = re.search(r'cn=([^)]+)', search_filter)
        if cn_match:
            cn_val = cn_match.group(1).strip().lower()
            if cn_val in db_data:
                user_data = db_data[cn_val]
                self.entries.append(MockLDAPEntry(user_data['dn'], user_data['attributes']))
                return True
        
        return False

    def modify(self, dn, changes):
        db_data = self._load_db()
        match = re.search(r'cn=([^,]+)', dn)
        username = match.group(1) if match else dn
        user_key = username.lower()
        
        if user_key in db_data:
            user_data = db_data[user_key]
            for attr_name, ops in changes.items():
                for op, vals in ops:
                    user_data['attributes'][attr_name] = vals
            self._save_db(db_data)
            return True
        return False

class MockRedisPipeline:
    def __init__(self, client):
        self.client = client
        self.ops = []
        
    def incr(self, key):
        self.ops.append(lambda: self.client.incr(key))
        return self
        
    def get(self, key):
        self.ops.append(lambda: self.client.get(key))
        return self
        
    def execute(self):
        results = [op() for op in self.ops]
        self.ops = []
        return results

class MockRedis:
    def __init__(self):
        self._data = {}
        
    def get(self, key):
        val = self._data.get(key)
        if val is None:
            return None
        return str(val).encode('utf-8')
        
    def set(self, key, val):
        self._data[key] = val
        return True
        
    def incr(self, key):
        val = int(self._data.get(key, 0)) + 1
        self._data[key] = val
        return val
        
    def decr(self, key):
        val = int(self._data.get(key, 0)) - 1
        self._data[key] = val
        return val
        
    def sadd(self, key, member):
        if key not in self._data:
            self._data[key] = set()
        if not isinstance(self._data[key], set):
            self._data[key] = set([self._data[key]])
        self._data[key].add(str(member))
        return 1
        
    def srem(self, key, member):
        if key in self._data and isinstance(self._data[key], set):
            self._data[key].discard(str(member))
            return 1
        return 0
        
    def smembers(self, key):
        val = self._data.get(key, set())
        if isinstance(val, set):
            return {m.encode('utf-8') for m in val}
        return set()
        
    def pipeline(self):
        return MockRedisPipeline(self)

def init_mock_ldap(ldap_manager, app):
    class MockLDAP3LoginManager(ldap_manager.__class__):
        @property
        def connection(self):
            if not hasattr(self, '_mock_connection'):
                db_path = app.config.get('MOCK_LDAP_DB', '.data/mock_ldap.json')
                if not os.path.isabs(db_path):
                    db_path = os.path.join(app.root_path, '..', db_path)
                self._mock_connection = MockLDAPConnection(db_path)
            return self._mock_connection
            
        def authenticate(self, username, password):
            db_path = app.config.get('MOCK_LDAP_DB', '.data/mock_ldap.json')
            if not os.path.isabs(db_path):
                db_path = os.path.join(app.root_path, '..', db_path)
            
            if os.path.exists(db_path):
                try:
                    with open(db_path, 'r', encoding='utf-8') as f:
                        db_data = json.load(f)
                except Exception:
                    db_data = {}
            else:
                db_data = {}
                
            user_key = username.lower()
            if user_key in db_data:
                user_data = db_data[user_key]
                stored_hash = user_data['attributes'].get('userPassword')
                if verify_password(stored_hash, password):
                    response = AuthenticationResponse()
                    response.status = AuthenticationResponseStatus.success
                    response.user_info = user_data['attributes']
                    response.user_id = username
                    response.user_dn = user_data['dn']
                    response.user_groups = []
                    return response
            
            response = AuthenticationResponse()
            response.status = AuthenticationResponseStatus.fail
            response.user_info = None
            response.user_id = None
            response.user_dn = None
            response.user_groups = []
            return response
            
        def get_user_info(self, dn):
            db_path = app.config.get('MOCK_LDAP_DB', '.data/mock_ldap.json')
            if not os.path.isabs(db_path):
                db_path = os.path.join(app.root_path, '..', db_path)
            if not os.path.exists(db_path):
                return None
            try:
                with open(db_path, 'r', encoding='utf-8') as f:
                    db_data = json.load(f)
            except Exception:
                return None
            for user_data in db_data.values():
                if user_data['dn'].lower() == dn.lower():
                    return user_data['attributes']
            return None
            
        def get_user_info_for_username(self, username):
            db_path = app.config.get('MOCK_LDAP_DB', '.data/mock_ldap.json')
            if not os.path.isabs(db_path):
                db_path = os.path.join(app.root_path, '..', db_path)
            if not os.path.exists(db_path):
                return None
            try:
                with open(db_path, 'r', encoding='utf-8') as f:
                    db_data = json.load(f)
            except Exception:
                return None
            user_key = username.lower()
            if user_key in db_data:
                return db_data[user_key]['attributes']
            return None

    ldap_manager.__class__ = MockLDAP3LoginManager

def init_mock_redis(redis_instance):
    redis_instance._redis_client = MockRedis()
