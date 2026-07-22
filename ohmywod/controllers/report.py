#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from sqlalchemy.sql import text
from sqlalchemy.sql.expression import case

from ohmywod.extensions import cache_delete, cache_get, cache_set, db, redis
from ohmywod.models.favorite import Favorite
from ohmywod.models.report import Report, ReportCategory


SITEMAP_CACHE_KEY = "sitemap_xml"


def invalidate_sitemap_cache():
    """Drop the shared sitemap after a public report/category mutation."""
    cache_delete(SITEMAP_CACHE_KEY)


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
        invalidate_sitemap_cache()

    def delete_report(self, rid):
        report = self.get_report(rid)
        report.status = 1
        db.session.add(report)
        db.session.commit()
        invalidate_sitemap_cache()

    def create_category(self, name, description, owner):
        category = ReportCategory(name=name, description=description, owner=owner)
        db.session.add(category)
        db.session.commit()
        invalidate_sitemap_cache()
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
        invalidate_sitemap_cache()

    def bulk_load_report_stats(self, reports):
        if not reports:
            return
        
        pipe = redis.pipeline()
        for r in reports:
            pipe.get(f"/stats/report/{r.id}/views")
            pipe.get(f"/stats/report/{r.id}/likes")
            pipe.get(f"/stats/report/{r.id}/favors")
        
        results = pipe.execute()
        
        for idx, r in enumerate(reports):
            r._prefetched_views = int(results[idx * 3]) if results[idx * 3] else 0
            r._prefetched_likes = int(results[idx * 3 + 1]) if results[idx * 3 + 1] else 0
            r._prefetched_favors = int(results[idx * 3 + 2]) if results[idx * 3 + 2] else 0

    def get_all_categories(self, offset=None, limit=None, show_deleted=False):
        query = ReportCategory.query
        if not show_deleted:
            query = query.filter(ReportCategory.status==None)
        
        total = query.count()
        if offset is not None:
            query = query.offset(offset)
        if limit is not None:
            query = query.limit(limit)
            
        return query.all(), total

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

        # SQLite has a limit of 999 SQL variables per query.
        # We chunk the rids to avoid the "too many SQL variables" error.
        chunk_size = 900
        rs = []
        for i in range(0, len(rids), chunk_size):
            chunk = rids[i:i + chunk_size]
            ordering = case(
                {_id: index for index, _id in enumerate(chunk)},
                value=Report.id
            )
            chunk_rs = Report.query.filter(Report.id.in_(chunk)).order_by(ordering).all()
            rs.extend(chunk_rs)
        self.bulk_load_report_stats(rs)
        return rs

    def get_category_reports(self, category, order_by=None, offset=None, limit=None, show_deleted=False):
        query = Report.query.filter(Report.category_id == category.id)
        if not show_deleted:
            query = query.filter(Report.status == None)

        # Determine order
        if not order_by:
            order_by = category.order_by or "ctime"

        is_reversed = order_by.startswith("reversed_")
        base_order = order_by.replace("reversed_", "")

        if base_order == "customized":
            if not is_reversed:
                query = query.order_by(
                    Report.order.is_(None),  # Nulls last (False is 0, True is 1)
                    Report.order.asc(),
                    Report.created_at.desc(),
                    Report.name.desc(),
                    Report.id.desc()
                )
            else:
                query = query.order_by(
                    Report.order.isnot(None),  # Nulls first (True is 1, False is 0)
                    Report.order.desc(),
                    Report.created_at.asc(),
                    Report.name.asc(),
                    Report.id.asc()
                )
        elif base_order == "name":
            if not is_reversed:
                query = query.order_by(Report.name.asc())
            else:
                query = query.order_by(Report.name.desc())
        else: # ctime or fallback
            if not is_reversed:
                query = query.order_by(Report.created_at.asc())
            else:
                query = query.order_by(Report.created_at.desc())

        # Get total count before pagination
        total = query.count()

        if offset is not None:
            query = query.offset(offset)
        if limit is not None:
            query = query.limit(limit)

        results = query.all()
        self.bulk_load_report_stats(results)
        return results, total

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

    def get_favorite_reports(self, username, status=0, offset=None, limit=None, show_deleted=False):
        kwargs = dict(
            ftype="report",
            username=username,
        )
        if status is not None:
            kwargs["status"] = status

        query = db.session.query(Favorite).filter_by(**kwargs)
        if not show_deleted:
            query = query.join(Report, Favorite.report_id == Report.id).filter(Report.status == None)

        query = query.order_by(Favorite.updated_at.desc())
        total = query.count()

        if offset is not None:
            query = query.offset(offset)
        if limit is not None:
            query = query.limit(limit)

        favors = query.all()
        # Fetch the actual Report objects for the paginated favorites
        rs = self.get_reports([int(x.report_id) for x in favors])
        
        # Pre-populate _prefetched_favor on each report object to avoid N+1 in the templates
        favor_map = {int(x.report_id): x for x in favors}
        for r in rs:
            r._prefetched_favor = favor_map.get(r.id)
            
        return rs, total

    def search(self, q, offset=None, limit=None, show_deleted=False):
        query = Report.query.filter(
            db.or_(
                Report.description.like(f"%{q}%"),
                Report.name.like(f"%{q}%"),
                Report.display_name.like(f"%{q}%")
            )
        )
        if not show_deleted:
            query = query.filter(Report.status == None)

        total = query.count()
        if offset is not None:
            query = query.offset(offset)
        if limit is not None:
            query = query.limit(limit)

        return query.all(), total

    def get_system_stats(self):
        from ohmywod.models.user import User
        
        stats = cache_get("system_stats")
        if stats is not None:
            return stats

        reports_count = Report.query.filter(Report.status == None).count()
        categories_count = ReportCategory.query.filter(ReportCategory.status == None).count()
        users_count = User.query.count()
        
        favors_count = Favorite.query.filter(
            Favorite.ftype == "report",
            Favorite.status == 0
        ).join(Report, Favorite.report_id == Report.id).filter(Report.status == None).count()
        
        active_report_ids = [r[0] for r in db.session.query(Report.id).filter(Report.status == None).all()]
        
        total_likes = 0
        total_views = 0
        if active_report_ids:
            pipe = redis.pipeline()
            for r_id in active_report_ids:
                pipe.get(f"/stats/report/{r_id}/likes")
                pipe.get(f"/stats/report/{r_id}/views")
            results = pipe.execute()
            
            for idx, r_id in enumerate(active_report_ids):
                likes_val = results[idx * 2]
                views_val = results[idx * 2 + 1]
                total_likes += int(likes_val) if likes_val else 0
                total_views += int(views_val) if views_val else 0
                
        stats = {
            'reports': reports_count,
            'categories': categories_count,
            'users': users_count,
            'favors': favors_count,
            'likes': total_likes,
            'views': total_views
        }
        cache_set("system_stats", stats, timeout=300)
        return stats

    def get_latest_reports(self, limit=5):
        reports = Report.query.filter(Report.status == None).order_by(Report.created_at.desc()).limit(limit).all()
        self.bulk_load_report_stats(reports)
        return reports
