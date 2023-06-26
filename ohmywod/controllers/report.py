#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from sqlalchemy.sql import text
from sqlalchemy.sql.expression import case

from ohmywod.extensions import db, redis
from ohmywod.models.favorite import Favorite
from ohmywod.models.report import Report, ReportCategory, ReportCategoryQuery


class ReportController:

    def get_cateogories_by_user(self, username, show_deleted=False):
        if show_deleted:
            return ReportCategory.query.filter_by(owner=username).all()

        return ReportCategory.query.filter(
            ReportCategory.owner==username,
            ReportCategory.status==None,
        ).all()

    def get_reports_by_user(self, username, show_deleted=False):
        if show_deleted:
            return Report.query.filter_by(owner=username).all()

        return Report.query.filter(
            Report.owner==username,
            Report.status==None,
        ).all()

    def create_report(self, cid, name, owner):
        report = Report(
            category_id=cid,
            owner=owner,
            name=name
        )
        db.session.add(report)
        db.session.commit()

    def delete_report(self, rid):
        report = self.get_report(rid)
        report.status = 1
        db.session.add(report)
        db.session.commit()

    def create_category(self, name, description, owner):
        category = ReportCategory(name=name, description=description, owner=owner)
        db.session.add(category)
        db.session.commit()
        return category

    def delete_category(self, cid):
        category = self.get_category(cid)
        reports = category.display_reports

        category.status = 1
        db.session.add(category)

        for r in reports:
            r.status = 1
            db.session.add(r)

        db.session.commit()

    def get_all_categories(self, show_deleted=False):
        if not show_deleted:
            return ReportCategory.query.filter(ReportCategory.status==None).all()
        return ReportCategory.query.all()

    def get_all_reports(self, show_deleted=False):
        if show_deleted:
            return Report.query.all()

        return Report.query.filter(Report.status==None).all()

    def get_category(self, cid):
        return ReportCategory.query.get(cid)

    def get_report(self, rid):
        return Report.query.get(rid)

    def get_reports(self, rids):
        if not rids:
            return []

        ordering = case(
            {_id: index for index, _id in enumerate(rids)},
            value=Report.id
        )
        rs = Report.query.filter(Report.id.in_(rids)).order_by(ordering).all()
        return rs

    def get_category_by_name_and_username(self, name, username, show_deleted=False):
        if show_deleted:
            return ReportCategory.query.filter_by(name=name, owner=username).all()

        return ReportCategory.query.filter(
            ReportCategory.name==name,
            ReportCategory.owner==username,
            ReportCategory.status==None,
        ).all()

    def incr_views(self, report_id):
        key = f"/stats/report/{report_id}/views"
        return redis.incr(key)

    def get_views(self, report_id):
        key = f"/stats/report/{report_id}/views"
        return redis.get(key)

    def incr_reader_views(self, report_id):
        key = f"/stats/report/{report_id}/reader"
        return redis.incr(key)

    def get_reader_views(self, report_id):
        key = f"/stats/report/{report_id}/reader"
        return redis.get(key)

    def incr_likes_cnt(self, report_id):
        key = f"/stats/report/{report_id}/likes"
        return redis.incr(key)

    def decr_likes_cnt(self, report_id):
        key = f"/stats/report/{report_id}/likes"
        return redis.decr(key)

    def get_likes_cnt(self, report_id):
        key = f"/stats/report/{report_id}/likes"
        return redis.get(key)

    def incr_favors(self, report_id):
        key = f"/stats/report/{report_id}/favors"
        return redis.incr(key)

    def decr_favors(self, report_id):
        key = f"/stats/report/{report_id}/favors"
        return redis.decr(key)

    def get_favors(self, report_id):
        key = f"/stats/report/{report_id}/favors"
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

    def get_favorite_reports(self, username, status=0, show_deleted=False):
        kwargs = dict(
            ftype="report",
            username=username,
        )
        if status is not None:
            kwargs["status"] = status

        favors = Favorite.query.filter_by(
            **kwargs
        ).order_by(Favorite.updated_at.desc()).all()

        rs = self.get_reports([int(x.report_id) for x in favors])
        if not show_deleted:
            rs = [x for x in rs if not x.is_deleted]
        return rs

    def search(self, q, show_deleted=False):
        sql = text('''
        SELECT id
        FROM report
        WHERE (description LIKE :q
          or name LIKE :q
          or display_name LIKE :q)
        ''')
        c = db.engine.execute(sql, q="%{}%".format(q))
        rids = [x[0] for x in c.fetchall()]
        rs = self.get_reports(rids)
        if not show_deleted:
            rs = [x for x in rs if not x.is_deleted]
        return rs
