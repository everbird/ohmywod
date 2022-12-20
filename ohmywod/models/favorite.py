#!/usr/bin/env python3

from datetime import datetime

from ohmywod.extensions import db


class Favorite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ftype = db.Column(db.String(255))
    username = db.Column(db.String(255))
    report_id = db.Column(db.Integer)
    status = db.Column(db.Integer)
    created_at = db.Column(db.DateTime(), default = datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())
