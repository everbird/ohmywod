#!/usr/bin/env python3
# -*- coding: utf-8 -*-


from ohmywod.extensions import db
from ohmywod.models.report import Report, ReportCategory, ReportCategoryQuery


class ReportController:

    def get_cateogories_by_user(self, username):
        return ReportCategory.query.filter_by(owner=username).all()

    def get_reports_by_user(self, username):
        return Report.query.filter_by(owner=username).all()

    def create_report(self, category, name, owner):
        report = Report(
            category_id=category.id,
            owner=owner,
            name=name
        )
        db.session.add(report)
        db.session.commit()

    def create_category(self, name, description, owner):
        category = ReportCategory(name=name, description=description, owner=owner)
        db.session.add(category)
        db.session.commit()
        return category

    def get_all_categories(self):
        return ReportCategory.query.all()

    def get_all_reports(self):
        return Report.query.all()

    def get_category(sefl, cid):
        return ReportCategory.query.get(cid)

    def get_report(self, rid):
        return Report.query.get(rid)

    def get_category_by_name_and_username(self, name, username):
        return ReportCategory.query.filter_by(name=name, owner=username).all()
