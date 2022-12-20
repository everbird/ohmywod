#!/usr/bin/env python3

from ohmywod.controllers.report import ReportController


class ReportPresenter:

    def __init__(self, report):
        self.report = report
        self.rc = ReportController()

    @property
    def views(self):
        return int(self.rc.get_views(self.report.id))

    def is_liked_by(self, username):
        rids = self.rc.get_likes(username)
        return str(self.report.id).encode("utf-8") in rids

    def is_favorited_by(self, username):
        return self.rc.check_favor(username, self.report.id)
