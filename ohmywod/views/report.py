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
from wtforms.validators import DataRequired, ValidationError
from wtforms.widgets import TextArea

from ohmywod.controllers.report import ReportController


report = Blueprint("wodreport", __name__)


@report.route("/")
def home():
    if not current_user or current_user.is_anonymous:
        return redirect(url_for('frontend.login'))

    rc = ReportController()
    categories = rc.get_cateogories_by_user(current_user.username)
    return rt("home.html", categories=categories)


# Used in iframe, username+cateogry+name should be uniqe
@report.route("/raw/<username>/<category>/<name>/")
@report.route("/raw/<username>/<category>/<name>/<path:subpath>")
def report_raw(username, category, name, subpath="index.html"):
    if not subpath.endswith(".html"):
        abort(404)

    data_dir = Path(current_app.config["DATA_DIR"])
    rpath = data_dir / username / category / name
    fpath = rpath / subpath

    if not fpath.exists():
        abort(404)

    with open(fpath) as f:
        raw = f.read()
        return rt_string(raw)


@report.route("/category/<category_id>")
def view_category(category_id):
    rc = ReportController()
    category = rc.get_category(category_id)
    if not category:
        abort(404)

    return rt("category.html", category=category)


@report.route("/report/<report_id>")
def view_report(report_id):
    rc = ReportController()
    report = rc.get_report(report_id)
    if not report:
        abort(404)

    return rt("report_details.html", report=report)


@report.route("/report/<report_id>/reader/")
@report.route("/report/<report_id>/reader/<path:subpath>")
def report_reader(report_id, subpath="index.html"):
    if not subpath.endswith(".html"):
        abort(404)

    rc = ReportController()
    report = rc.get_report(report_id)

    data_dir = Path(current_app.config["DATA_DIR"])
    rpath = data_dir / report.owner / report.category.name / report.name
    fpath = rpath / subpath

    if not fpath.exists():
        abort(404)

    with fpath.open() as f:
        raw = f.read()
        tree = html.fromstring(raw)
        body = tree.xpath("body")[0]
        report_html = etree.tostring(body, pretty_print=False, encoding='unicode')
        report_html = report_html.replace('<body>', '<div id="auto_extracted" style="width: 100vw;">')
        report_html = report_html.replace('</body>', '</div>')
        report_html = report_html.replace('#"', '#/"')
        report_html = report_html.replace('jump(', 'dummy_jump(')

        return rt(
            "report_reader.html",
            report_html=report_html,
            report=report,
            subpath=subpath
        )
    return rt("report_details.html", report=report)


@report.route("/all")
def report_page():
    rc = ReportController()
    categories = rc.get_all_categories()
    return rt("root.html", categories=categories)


class NewCategoryForm(FlaskForm):
    name = StringField('name', validators =[DataRequired()])
    description = StringField("description", widget=TextArea())
    submit = SubmitField("Create")

    def validate_name(form, field):
        name = field.data
        rc = ReportController()
        if rc.get_category_by_name_and_username(name, current_user.username):
            raise ValidationError(
                "Category {} exists for username:{}"
                .format(name, current_user.username)
            )



@report.route("/new_category", methods=['GET', 'POST'])
def new_category():
    form = NewCategoryForm()
    if form.validate_on_submit():
        rc = ReportController()
        name = form.name.data
        description = form.description.data
        category = rc.create_category(name, description, current_user.username)
        return redirect(
            url_for(
                "wodreport.view_category",
                category_id=category.id
            )
        )
    return rt("new_category.html", form=form)
