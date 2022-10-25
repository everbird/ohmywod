#!/usr/bin/env python3
from datetime import datetime

from flask_sqlalchemy import BaseQuery

from ohmywod.extensions import db


class ReportQuery(BaseQuery):

    def search(self, keywords):
        criteria = []

        for keyword in keywords.split():
            keyword = '%' + keyword + '%'
            criteria.append(db.or_(Report.name.ilike(keyword),
                ))
        q = reduce(db.and_, criteria)
        return self.filter(q).distinct()

    def get_by_username(self, username):
        exp = db.session.query(Report) \
            .filter(Report.owner==username) \

        return exp.all()


class ReportCategoryQuery(BaseQuery):

    def get_by_username(self, username):
        exp = db.session.query(ReportCategory) \
            .filter(ReportCategory.owner==username) \

        return exp.all()

    @classmethod
    def get_by_name(cls, name):
        return ReportCategory.query.filter_by(name=name).first()


class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(
        db.Integer,
        db.ForeignKey("report_category.id"),
        nullable=False
    )
    created_at = db.Column(db.DateTime(), default = datetime.utcnow)
    owner = db.Column(db.String(255))
    name = db.Column(db.Unicode(255))
    description = db.Column(db.Text)


class ReportCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Unicode(255), nullable=False)
    owner = db.Column(db.String(255), nullable=False)
    reports = db.relationship("Report", backref="category", lazy=True)
    description = db.Column(db.Text)
