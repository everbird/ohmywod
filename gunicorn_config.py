#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from configs.config import PORT

bind = "0.0.0.0:{}".format(PORT)
workers = 4
worker_class = "sync"
debug = True
daemon = False
