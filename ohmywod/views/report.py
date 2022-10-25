#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import os
from pathlib import Path

from flask import (
    Blueprint,
    render_template as rt,
    abort,
    current_app
)
from flask_login import current_user
from lxml import etree, html


report = Blueprint("wodreport", __name__)

def listdir_only(path):
    for x in os.listdir(path):
        dpath = os.path.join(path, x)
        if os.path.isdir(dpath):
            yield x


@report.route("/<username>/<category>/<name>/")
@report.route("/<username>/<category>/<name>/<path:subpath>")
def report_details(username, category, name, subpath="index.html"):
    data_dir = current_app.config["DATA_DIR"]
    rpath = os.path.join(data_dir, username, category, name)
    fpath = os.path.join(rpath, subpath)

    if not subpath.endswith(".html"):
        abort(404)

    with open(fpath) as f:
        raw = f.read()
        tree = html.fromstring(raw)
        body = tree.xpath("body")[0]
        report_html = etree.tostring(body, pretty_print=False, encoding='unicode')
        report_html = report_html.replace('<body>', '<div id="auto_extracted">')
        report_html = report_html.replace('</body>', '</div>')

        return rt(
            "layout.html",
            report_html=report_html,
            username=username,
            category=category,
            name=name,
            subpath=subpath
        )


@report.route("/<username>/<category>/")
def report_category(username, category):
    data_dir = current_app.config["DATA_DIR"]
    cpath = os.path.join(data_dir, username, category)
    dirs = listdir_only(cpath)
    return rt("category.html", category=category, username=username, dirs=dirs)


@report.route("/")
def report_page():
    data_dir = current_app.config["DATA_DIR"]
    rpath = Path(data_dir)
    dirs = []
    for upath in rpath.iterdir():
        if not upath.is_dir():
            continue

        username = upath.stem
        for cpath in upath.iterdir():
            if not cpath.is_dir():
                continue

            category = cpath.stem
            dirs.append((category, username))

    return rt("root.html", dirs=dirs)