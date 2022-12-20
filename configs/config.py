#!/usr/bin/env python
# -*- coding: utf-8 -*-

PORT = '8013'
APP_NAME = "ohmywod"
VAR_PATH = "/var"
DATA_PATH = "/data"
REDIS_STORE_HOST = "localhost"
REDIS_STORE_PORT = 6379
REDIS_CACHE_HOST = "localhost"
REDIS_CACHE_PORT = 7379
REDIS_BIN_PATH = "/usr/sbin/redis-server"


try:
    from .local_config import *
except ImportError as e:
    if e.args[0].startswith('No module named'):
        pass
    else:
        # the ImportError is raised inside local_config
        raise
