#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import os
from pathlib import Path

from flask import (
    Blueprint,
    render_template as rt,
    render_template_string as rt_string,
    abort,
    current_app,
    redirect,
    url_for
)
from flask_login import current_user
from flask_wtf import FlaskForm
from lxml import etree, html
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired

from ohmywod.controllers.report import ReportController


report = Blueprint("wodreport", __name__)

@report.route("/original/<username>/<category>/<name>/")
@report.route("/original/<username>/<category>/<name>/<path:subpath>")
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




# Used in iframe, username+cateogry+name should be uniqe
@report.route("/raw/<username>/<category>/<name>/")
@report.route("/raw/<username>/<category>/<name>/<path:subpath>")
def report_raw(username, category, name, subpath="index.html"):
    data_dir = current_app.config["DATA_DIR"]
    rpath = os.path.join(data_dir, username, category, name)
    fpath = os.path.join(rpath, subpath)

    if not subpath.endswith(".html"):
        abort(404)

    with open(fpath) as f:
        raw = f.read()

        return rt_string(raw)


@report.route("/category/<category_id>")
def view_category(category_id):
    rc = ReportController()
    category = rc.get_category(category_id)
    return rt("category.html", category=category)


@report.route("/report/<report_id>")
def view_report(report_id):
    rc = ReportController()
    report = rc.get_report(report_id)
    return rt("report_details.html", report=report)


@report.route("/report/<report_id>/reader/")
@report.route("/report/<report_id>/reader/<path:subpath>")
def report_reader(report_id, subpath="index.html"):
    if not subpath.endswith(".html"):
        abort(404)

    rc = ReportController()
    report = rc.get_report(report_id)

    data_dir = current_app.config["DATA_DIR"]
    rpath = os.path.join(data_dir, report.owner, report.category.name, report.name)
    fpath = os.path.join(rpath, subpath)

    with open(fpath) as f:
        raw = f.read()
        tree = html.fromstring(raw)
        body = tree.xpath("body")[0]
        report_html = etree.tostring(body, pretty_print=False, encoding='unicode')
        report_html = report_html.replace('<body>', '<div id="auto_extracted" style="width: 100vw;">')
        report_html = report_html.replace('</body>', '</div>')
        report_html = report_html.replace('#', '#/')

        return rt(
            "report_reader.html",
            report_html=report_html,
            report=report,
            subpath=subpath
        )
    return rt("report_details.html", report=report)


@report.route("/")
def report_page():
    rc = ReportController()
    categories = rc.get_all_categories()
    return rt("root.html", categories=categories)


class NewCategoryForm(FlaskForm):
    name = StringField('name', validators =[DataRequired()])
    description = StringField("description")
    submit = SubmitField("Create")


@report.route("/new_category", methods=['GET', 'POST'])
def new_category():
    form = NewCategoryForm()
    if form.validate_on_submit():
        rc = ReportController()
        name = form.name.data
        description = form.description.data
        rc.create_category(name, description, current_user.username)
        return redirect(
            url_for(
                "wodreport.report_category",
                username=current_user.username,
                category=name
            )
        )
    return rt("new_category.html", form=form)
