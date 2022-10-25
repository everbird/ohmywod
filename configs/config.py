#!/usr/bin/env python
# -*- coding: utf-8 -*-

PORT = '8013'
APP_NAME = "ohmywod"
VAR_PATH = "/var"


try:
    from .local_config import *
except ImportError as e:
    if e.args[0].startswith('No module named'):
        pass
    else:
        # the ImportError is raised inside local_config
        raise
