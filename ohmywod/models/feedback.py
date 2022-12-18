from datetime import datetime

from ohmywod.extensions import db


class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text)
    username = db.Column(db.String(255))
    created_at = db.Column(db.DateTime(), default = datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())
