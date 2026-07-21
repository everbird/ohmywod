# -*- coding: utf-8 -*-
"""In-process test doubles. Only Redis is mocked now that auth is SQLite-only
(HA-008 retired the LDAP mock along with the LDAP auth path)."""


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

    def ping(self):
        return True

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
        # Match real Redis: 1 only when the member was actually added
        if str(member) in self._data[key]:
            return 0
        self._data[key].add(str(member))
        return 1

    def srem(self, key, member):
        if key in self._data and isinstance(self._data[key], set):
            if str(member) in self._data[key]:
                self._data[key].remove(str(member))
                return 1
        return 0

    def smembers(self, key):
        val = self._data.get(key, set())
        if isinstance(val, set):
            return {m.encode('utf-8') for m in val}
        return set()

    def pipeline(self):
        return MockRedisPipeline(self)


def init_mock_redis(redis_instance):
    redis_instance._redis_client = MockRedis()
