#!/usr/bin/env python3
from datetime import datetime

from ohmywod.extensions import db


class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    path = db.Column(db.String(150))
    created_at = db.Column(db.DateTime(), default = datetime.utcnow)
    # owner
    # description
