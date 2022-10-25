#!/usr/bin/env python3
# -*- coding: utf-8 -*-


from ohmywod.extensions import db
from ohmywod.models.report import Report, ReportCategory, ReportCategoryQuery


class ReportController:

    def get_cateogories_by_user(self, username):
        return ReportCategory.query.filter_by(owner=username).all()

    def get_reports_by_user(self, username):
        return Report.query.filer_by(owner=username).all()

    def create_report(self, category, name, owner):
        c = ReportCategoryQuery.get_by_name(category)
        if not c:
            raise Error("category should exist")

        report = Report(
            category_id=c.id,
            owner=owner,
            name=name
        )
        db.session.add(report)
        db.session.commit()

    def create_category(self, name, description, owner):
        category = ReportCategory(name=name, description=description, owner=owner)
        db.session.add(category)
        db.session.commit()
