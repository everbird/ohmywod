#!/usr/bin/env python3
from datetime import datetime

import bbcode
from flask_sqlalchemy import BaseQuery
from sqlalchemy.orm import backref, relationship

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
    owner = db.Column(db.String(255))
    # Can not be modified since file path is fixed
    name = db.Column(db.String(255))
    display_name = db.Column(db.String(255))
    description = db.Column(db.Text)
    order = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime(), default = datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

    @property
    def title(self):
        if not self.display_name or len(self.display_name) == 0:
            return self.name

        return self.display_name

    @property
    def description_rendered(self):
        return bbcode.render_html(self.description)

    @property
    def presenter(self):
        return self.get_presenter()

    def get_presenter(self):
        from ohmywod.presenters.report import ReportPresenter
        return ReportPresenter(self)

    def get_favor(self, username, status=0):
        from ohmywod.controllers.report import ReportController
        rc = ReportController()
        return rc.get_favor(username, self.id, status=status)


class ReportCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # Can not be modified since file path is fixed
    name = db.Column(db.String(255), nullable=False)
    owner = db.Column(db.String(255), nullable=False)
    reports = db.relationship("Report", backref="category", lazy=True)
    display_name = db.Column(db.String(255))
    description = db.Column(db.Text)
    # Order by: name, created_time, customized
    order_by = db.Column(db.String(32))
    created_at = db.Column(db.DateTime(), default = datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

    @property
    def title(self):
        if not self.display_name or len(self.display_name) == 0:
            return self.name

        return self.display_name


    @property
    def sorted_reports(self):
        rs = self.reports
        d = {
            "customized": "sorted_reports_by_customized_order",
            "ctime": "sorted_reports_by_ctime",
            "name": "sorted_reports_by_name",
        }

        order_by = self.order_by.replace("reversed_", "") if self.order_by else "ctime"
        attr = d.get(order_by)
        if attr:
            rs = getattr(self, attr)

        reversed = False
        if self.order_by and self.order_by.startswith("reversed_"):
            reversed = True

        return rs[::-1] if reversed else rs


    @property
    def sorted_reports_by_customized_order(self):
        def _fkey(r):
            o1 = -r.order if r.order else -float("inf")
            o2 = r.created_at
            o3 = r.name
            o4 = r.id
            return (o1, o2, o3, o4)

        return sorted(self.reports, key=_fkey, reverse=True)

    @property
    def sorted_reports_by_ctime(self):
        return sorted(self.reports, key=lambda x: x.created_at)

    @property
    def sorted_reports_by_name(self):
        return sorted(self.reports, key=lambda x: x.name)

    @property
    def description_rendered(self):
        return bbcode.render_html(self.description)



class ReportDetails(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(
        db.Integer,
        db.ForeignKey("report.id")
    )
    report = relationship("Report", backref=backref("details", uselist=False))

    # .net | .org | .de
    site_name = db.Column(db.String(255))

    # Delta, Canto etc.
    server_name = db.Column(db.String(255))

    group_name = db.Column(db.String(255))
    group_size = db.Column(db.String(255))
    dungeon_name = db.Column(db.String(255))

    # Normal | Time-limited | others
    dungeon_type = db.Column(db.String(255))
    dungeon_date = db.Column(db.String(255))

    challenge_name = db.Column(db.String(255))
    challenge_type = db.Column(db.String(255))

    # F5,F6,F7
    challenge_floors = db.Column(db.String(255))

    succeed = db.Column(db.String(255))

    level_min = db.Column(db.String(255))
    level_max = db.Column(db.String(255))

    classes = db.Column(db.String(255))
    races = db.Column(db.String(255))

    classes_and_races = db.Column(db.String(255))

    created_at = db.Column(db.DateTime(), default = datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())
