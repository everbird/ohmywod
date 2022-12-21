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
    url_for,
    request,
    jsonify
)
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from lxml import etree, html
from wtforms import StringField, SubmitField, SelectField
from wtforms.validators import DataRequired, ValidationError, Optional
from wtforms.widgets import TextArea

from ohmywod.controllers.report import ReportController
from ohmywod.extensions import db, Pagination, get_page_args
from ohmywod.models.report import ReportDetails
from ohmywod.presenters.report import ReportPresenter


report = Blueprint("wodreport", __name__)


@report.route("/")
@login_required
def home():
    rc = ReportController()
    categories = rc.get_cateogories_by_user(current_user.username)
    favor_reports = rc.get_favorite_reports(current_user.username)
    return rt("home.html", categories=categories, favor_reports=favor_reports)


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

    page, per_page, offset = get_page_args(
        page_parameter='page',
        per_page_parameter='per_page'
    )
    sorted_reports = category.sorted_reports
    total = len(sorted_reports)
    reports = sorted_reports[offset:offset+per_page]
    pagination = Pagination(
        page=page,
        per_page=per_page,
        total=total,
        css_framework='bootstrap5'
    )
    return rt(
        "category.html",
        category=category,
        reports=reports,
        pagination=pagination,
        page=page,
        per_page=per_page
    )


class EditCategoryForm(FlaskForm):
    order_by = SelectField(
        "Order reports by",
        choices=[
            ("ctime", "Created At"),
            ("name", "Name"),
            ("customized", "Customized order"),
            ("reversed_ctime", "Created At(reversed)"),
            ("reversed_name", "Name(reversed)"),
            ("reversed_customized", "Customized order(reversed)"),
        ]
    )
    description = StringField("description", widget=TextArea())
    submit = SubmitField("Update")


@report.route("/category/<category_id>/edit", methods=["POST", "GET"])
@login_required
def edit_category(category_id):
    rc = ReportController()
    category = rc.get_category(category_id)
    if not category:
        abort(404)

    if current_user.username != category.owner:
        abort(403)

    form = EditCategoryForm(
        description=category.description,
        order_by=category.order_by
    )
    if form.validate_on_submit():
        category.description = form.description.data
        category.order_by = form.order_by.data
        db.session.commit()
        return redirect(url_for("wodreport.view_category", category_id=category.id))

    return rt("edit_category.html", category=category, form=form)


@report.route("/category/<category_id>/reorder", methods=["POST", "GET"])
@login_required
def reorder_category(category_id):
    rc = ReportController()
    category = rc.get_category(category_id)
    if not category:
        abort(404)

    if current_user.username != category.owner:
        abort(403)


    updates = []
    d = request.form
    for k, v in d.items():
        if not v or not v.isnumeric():
            continue

        rid = k.replace("order-", "")
        updates.append((rid, int(v)))

    for rid, order in updates:
        r = rc.get_report(rid)
        r.order = order

    db.session.commit()

    return rt("reorder_category.html", category=category)


@report.route("/report/<report_id>")
def view_report(report_id):
    rc = ReportController()
    report = rc.get_report(report_id)
    report_presenter = ReportPresenter(report)
    if not report:
        abort(404)

    rc.incr_views(report_id)
    details = report.details
    return rt(
        "report_details.html",
        report=report,
        details=details,
        report_presenter=report_presenter
    )


class EditReportForm(FlaskForm):
    display_name = StringField("display_name", validators=[Optional()])
    description = StringField("description", widget=TextArea())

    site_name = StringField("site_name", validators=[Optional()])
    server_name = StringField("server_name", validators=[Optional()])
    group_name = StringField("group_name", validators=[Optional()])
    group_size = StringField("group_size", validators=[Optional()])
    dungeon_name = StringField("dungeon_name", validators=[Optional()])
    dungeon_type = StringField("dungeon_type", validators=[Optional()])
    dungeon_date = StringField("dungeon_date", validators=[Optional()])
    challenge_name = StringField("challenge_name", validators=[Optional()])
    challenge_type = StringField("challenge_type", validators=[Optional()])
    challenge_floors = StringField("challenge_floors", validators=[Optional()])
    succeed = StringField("succeed", validators=[Optional()])
    level_min = StringField("level_min", validators=[Optional()])
    level_max = StringField("level_max", validators=[Optional()])
    classes = StringField("classes", validators=[Optional()])
    races = StringField("races", validators=[Optional()])
    classes_and_races = StringField("classes_and_races", validators=[Optional()])

    submit = SubmitField("Update")


@report.route("/report/<report_id>/edit", methods=["GET", "POST"])
@login_required
def edit_report(report_id):
    rc = ReportController()
    report = rc.get_report(report_id)
    if not report:
        abort(404)

    if current_user.username != report.owner:
        abort(403)

    details = report.details or ReportDetails()
    form = EditReportForm(
        description=report.description,
        display_name=report.display_name,
        site_name=details.site_name,
        server_name=details.server_name,
        group_name=details.group_name,
        group_size=details.group_size,
        dungeon_name=details.dungeon_name,
        dungeon_type=details.dungeon_type,
        dungeon_date=details.dungeon_date,
        challenge_name=details.challenge_name,
        challenge_type=details.challenge_type,
        challenge_floors=details.challenge_floors,
        succeed=details.succeed,
        level_min=details.level_min,
        level_max=details.level_max,
        classes=details.classes,
        races=details.races,
        classes_and_races=details.classes_and_races,
    )
    if form.validate_on_submit():
        report.description = form.description.data
        report.display_name = form.display_name.data
        details.site_name = form.site_name.data
        details.server_name = form.server_name.data
        details.group_name = form.group_name.data
        details.group_size = form.group_size.data
        details.dungeon_name = form.dungeon_name.data
        details.dungeon_type = form.dungeon_type.data
        details.dungeon_date = form.dungeon_date.data
        details.challenge_name = form.challenge_name.data
        details.challenge_type = form.challenge_type.data
        details.challenge_floors = form.challenge_floors.data
        details.succeed = form.succeed.data
        details.level_min = form.level_min.data
        details.level_max = form.level_max.data
        details.classes = form.classes.data
        details.races = form.races.data
        details.classes_and_races = form.classes_and_races.data
        report.details = details
        db.session.commit()
        return redirect(url_for("wodreport.view_report", report_id=report.id))

    return rt("edit_report.html", report=report, form=form)


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

    rc.incr_reader_views(report.id)
    rc.incr_views(report.id)
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
    page, per_page, offset = get_page_args(
        page_parameter='page',
        per_page_parameter='per_page'
    )
    all_categories = rc.get_all_categories()
    total = len(all_categories)
    categories = all_categories[offset:offset+per_page]
    pagination = Pagination(
        page=page,
        per_page=per_page,
        total=total,
        css_framework='bootstrap5'
    )
    return rt(
        "root.html",
        categories=categories,
        pagination=pagination,
        page=page,
        per_page=per_page
    )

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


@report.route("/report/<report_id>/like", methods=['POST'])
@login_required
def ajax_like(report_id):
    username = current_user.username
    rc = ReportController()
    report = rc.get_report(report_id)
    if report:
        rc.like(username, report_id)
        r = {"status": 0, "message": "Liked successfully."}
        rc.incr_likes_cnt(report_id)
    else:
        r = {"status": 1, "message": f"Report {report_id} doesn't exist."}
    return jsonify(r)


@report.route("/report/<report_id>/unlike", methods=['POST'])
@login_required
def ajax_unlike(report_id):
    username = current_user.username
    rc = ReportController()
    report = rc.get_report(report_id)
    if report:
        rc.unlike(username, report_id)
        r = {"status": 0, "message": "Uniked successfully."}
        rc.decr_likes_cnt(report_id)
    else:
        r = {"status": 1, "message": f"Report {report_id} doesn't exist."}
    return jsonify(r)


@report.route("/report/<report_id>/add_favorite", methods=['POST'])
@login_required
def ajax_add_favorite(report_id):
    username = current_user.username
    rc = ReportController()
    report = rc.get_report(report_id)
    if report:
        rc.add_favor(username, report_id)
        r = {"status": 0, "message": "Favorite added successfully."}
        rc.incr_favors(report_id)
    else:
        r = {"status": 1, "message": f"Report {report_id} doesn't exist."}
    return jsonify(r)


@report.route("/report/<report_id>/cancel_favorite", methods=['POST'])
@login_required
def ajax_cancel_favorite(report_id):
    username = current_user.username
    rc = ReportController()
    report = rc.get_report(report_id)
    if report:
        rc.cancel_favor(username, report_id)
        r = {"status": 0, "message": "Favorite cancelled successfully."}
        rc.decr_favors(report_id)
    else:
        r = {"status": 1, "message": f"Report {report_id} doesn't exist."}
    return jsonify(r)


@report.route("favor")
@login_required
def favorite_reports():
    username = current_user.username
    rc = ReportController()
    favor_reports = rc.get_favorite_reports(current_user.username)
    page, per_page, offset = get_page_args(
        page_parameter='page',
        per_page_parameter='per_page'
    )
    total = len(favor_reports)
    reports = favor_reports[offset:offset+per_page]
    pagination = Pagination(
        page=page,
        per_page=per_page,
        total=total,
        css_framework='bootstrap5'
    )
    return rt(
        "favor.html",
        reports=reports,
        pagination=pagination,
        page=page,
        per_page=per_page
    )


@report.route("/user/<username>/categories")
def user_categories(username):
    rc = ReportController()
    categories = rc.get_cateogories_by_user(username)
    return rt("user_categories.html", categories=categories, username=username)


@report.route("search")
def search():
    args = request.args
    q = args.get("q") or ""
    reports = []
    rc = ReportController()
    reports = rc.search(q)

    page, per_page, offset = get_page_args(
        page_parameter='page',
        per_page_parameter='per_page'
    )
    total = len(reports)
    reports = reports[offset:offset+per_page]
    pagination = Pagination(
        page=page,
        per_page=per_page,
        total=total,
        css_framework='bootstrap5'
    )
    return rt(
        "search.html",
        q=q,
        reports=reports,
        pagination=pagination,
        page=page,
        per_page=per_page,
        total=total
    )
