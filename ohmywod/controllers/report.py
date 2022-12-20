#!/usr/bin/env python3
# -*- coding: utf-8 -*-


from ohmywod.extensions import db, redis
from ohmywod.models.favorite import Favorite
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

    def get_all_categories(self, page=None, per_page=None):
        if not page or not per_page:
            return ReportCategory.query.all()
        else:
            return ReportCategory.query.paginate(page=page, per_page=per_page)

    def get_all_reports(self):
        return Report.query.all()

    def get_category(self, cid):
        return ReportCategory.query.get(cid)

    def get_report(self, rid):
        return Report.query.get(rid)

    def get_category_by_name_and_username(self, name, username):
        return ReportCategory.query.filter_by(name=name, owner=username).all()

    def incr_views(self, report_id):
        key = f"/stats/report/{report_id}/views"
        return redis.incr(key)

    def get_views(self, report_id):
        key = f"/stats/report/{report_id}/views"
        return redis.get(key)

    def like(self, username, report_id):
        key = f"/data/report/{username}/like"
        return redis.sadd(key, report_id)

    def unlike(self, username, report_id):
        key = f"/data/report/{username}/like"
        return redis.srem(key, report_id)

    def get_likes(self, username):
        key = f"/data/report/{username}/like"
        return redis.smembers(key)

    def get_favor(self, username, report_id, status=0):
        favors = Favorite.query.filter_by(
            ftype="report",
            username=username,
            report_id=report_id,
            status=status,
        ).all()
        if favors:
            return favors[0]

    def add_favor(self, username, report_id):
        favor = self.get_favor(username, report_id)
        if favor:
            return favor

        favor = Favorite(
            ftype="report",
            username=username,
            report_id=report_id,
            status=0,
        )
        db.session.add(favor)
        db.session.commit()
        return favor

    def cancel_favor(self, username, report_id):
        favor = self.get_favor(username, report_id)
        if favor:
            favor.status = 1
            db.session.add(favor)
            db.session.commit()
            return True
        return False

    def check_favor(self, username, report_id):
        favor = self.get_favor(username, report_id)
        return favor is not None
