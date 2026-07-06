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
    make_response,
    redirect,
    url_for,
    request,
    jsonify,
    flash
)
from werkzeug.utils import safe_join
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from lxml import etree, html
from lxml.html.clean import Cleaner
import re
from wtforms import StringField, SubmitField, SelectField
from wtforms.validators import DataRequired, ValidationError, Optional
from wtforms.widgets import TextArea

from ohmywod.controllers.report import ReportController
from ohmywod.extensions import db, Pagination, get_page_args
from ohmywod.utils import paginate
from ohmywod.models.report import ReportDetails
from ohmywod.presenters.report import ReportPresenter


report = Blueprint("wodreport", __name__)

wod_cleaner = Cleaner(scripts=True, javascript=True, comments=False, style=False, links=False, meta=False, page_structure=False, safe_attrs_only=False, forms=False)

def sanitize_wod_report(body):
    arg = r"('[^']*'|\"[^\"]*\"|\d+|this|true|false)"
    args = fr"{arg}(\s*,\s*{arg})*"
    safe_func = fr"^(return )?(o|dummy_jump|jump|st|cf|co|sd|ct)\(\s*({args})?\s*\);?$"
    safe_redirect = r"^(window\.)?document\.location\.href\s*=\s*('[a-zA-Z0-9_/ \.-]+'|\"[a-zA-Z0-9_/ \.-]+\");?$"
    safe_on_pattern = re.compile(safe_func)
    safe_redirect_pattern = re.compile(safe_redirect)

    for el in body.iter():
        for attr in list(el.attrib):
            if attr.lower().startswith('on'):
                val = el.attrib[attr]
                
                if attr.lower() == 'onmouseover':
                    is_valid = False
                    prefix_len = 0
                    if val.startswith("return wodToolTip(this,'"):
                        is_valid = True
                        prefix_len = 24
                    elif val.startswith("wodToolTip(this,'"):
                        is_valid = True
                        prefix_len = 17
                    
                    if is_valid and (val.endswith("');") or val.endswith("')")):
                        html_content = val[prefix_len:-3] if val.endswith("');") else val[prefix_len:-2]
                        html_content = html_content.replace("\\'", "'")
                        try:
                            frag = html.fromstring(f"<div>{html_content}</div>")
                            frag = wod_cleaner.clean_html(frag)
                            clean_content = etree.tostring(frag, encoding='unicode')[5:-6]
                            clean_content = clean_content.replace("'", "\\'").replace("\n", "\\n").replace("\r", "")
                            el.attrib['data-safe-onmouseover'] = f"return wodToolTip(this,'{clean_content}');"
                        except Exception:
                            pass
                elif attr.lower() in ('onclick', 'onchange'):
                    if safe_on_pattern.match(val) or safe_redirect_pattern.match(val):
                        el.attrib[f'data-safe-{attr.lower()}'] = val

    body = wod_cleaner.clean_html(body)

    for el in body.iter():
        for attr in list(el.attrib):
            if attr.startswith('data-safe-'):
                real_attr = attr.replace('data-safe-', '')
                el.attrib[real_attr] = el.attrib[attr]
                del el.attrib[attr]

    return body


@report.route("/")
@login_required
def home():
    rc = ReportController()
    categories = rc.get_cateogories_by_user(current_user.username)
    favor_reports, _ = rc.get_favorite_reports(current_user.username, limit=5)
    return rt("home.html", categories=categories, favor_reports=favor_reports)


# The CSP sandbox below makes the iframe an opaque origin, so the parent
# page can no longer read contentWindow.location (used by the 阅读模式
# button to map the current sub-page + scroll position to the reader URL).
# This beacon runs inside the frame and posts that state to the parent;
# postMessage is allowed across the sandbox boundary.
READER_STATE_BEACON = """
<script>
(function () {
    if (window.parent === window) return;
    function send() {
        var d = document;
        parent.postMessage({
            wodReaderState: {
                href: window.location.href,
                scrollTop: (d.body && d.body.scrollTop) ||
                    (d.documentElement && d.documentElement.scrollTop) || 0
            }
        }, '*');
    }
    window.addEventListener('scroll', send, {passive: true});
    window.addEventListener('hashchange', send);
    send();
})();
</script>
"""


# Used in iframe, username+cateogry+name should be uniqe
@report.route("/raw/<username>/<category>/<name>/")
@report.route("/raw/<username>/<category>/<name>/<path:subpath>")
def report_raw(username, category, name, subpath="index.html"):
    if not subpath.endswith(".html"):
        abort(404)

    data_dir = current_app.config["DATA_DIR"]
    fpath_str = safe_join(data_dir, username, category, name, subpath)
    if not fpath_str:
        abort(404)

    fpath = Path(fpath_str)

    try:
        if not fpath.exists():
            abort(404)
    except OSError as e:
        current_app.logger.error(f"Failed to access path {fpath_str}: {e}")
        abort(503, description="Storage service is temporarily unavailable.")

    try:
        with open(fpath) as f:
            raw = f.read()
    except OSError as e:
        current_app.logger.error(f"Failed to read path {fpath_str}: {e}")
        abort(503, description="Storage service is temporarily unavailable.")

    raw = raw.replace('http:', 'https:')
    resp = make_response(raw + READER_STATE_BEACON)
    resp.mimetype = 'text/html'
    # User-uploaded HTML is served verbatim; CSP sandbox makes the browser
    # treat it as an opaque origin so its scripts can't touch main-site
    # cookies or issue same-origin requests. iframe embedding still works.
    resp.headers['Content-Security-Policy'] = "sandbox allow-scripts allow-popups"
    return resp


@report.route("/category/<category_id>")
def view_category(category_id):
    rc = ReportController()
    category = rc.get_category(category_id)
    if not category:
        abort(404)

    reports, pagination, page, per_page, total = paginate(
        rc.get_category_reports,
        category
    )
    return rt(
        "category.html",
        category=category,
        reports=reports,
        pagination=pagination,
        page=page,
        per_page=per_page
    )


CATEGORY_ORDER_BY_CHOICES = [
    ("ctime", "创建时间"),
    ("reversed_ctime", "创建时间（倒序）"),
    ("name", "名称"),
    ("reversed_name", "名称（倒序）"),
    ("customized", "手动排序"),
    ("reversed_customized", "手动排序（倒序）"),
]
CATEGORY_ORDER_BY_LABELS = dict(CATEGORY_ORDER_BY_CHOICES)


def category_order_by_label(order_by):
    return CATEGORY_ORDER_BY_LABELS.get(order_by or "ctime", CATEGORY_ORDER_BY_LABELS["ctime"])


def is_manual_category_order(order_by):
    return (order_by or "").replace("reversed_", "") == "customized"


class EditCategoryForm(FlaskForm):
    order_by = SelectField(
        "默认显示顺序",
        choices=CATEGORY_ORDER_BY_CHOICES
    )
    display_name = StringField("display_name", validators=[Optional()])
    description = StringField("description", widget=TextArea())
    submit = SubmitField("更新")


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
        display_name=category.display_name,
        description=category.description,
        order_by=category.order_by
    )
    if form.validate_on_submit():
        category.display_name = form.display_name.data
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
        if not k.startswith("order-") or not v or not v.isnumeric():
            continue

        rid = k.replace("order-", "")
        updates.append((rid, int(v)))

    for rid, order in updates:
        r = rc.get_report(rid)
        if r and r.category_id == category.id:
            r.order = order

    if request.method == "POST" and updates and not is_manual_category_order(category.order_by):
        category.order_by = "customized"
        db.session.add(category)

    db.session.commit()

    reports, _ = rc.get_category_reports(category)
    return rt(
        "reorder_category.html",
        category=category,
        reports=reports,
        current_order_label=category_order_by_label(category.order_by),
        manual_order_active=is_manual_category_order(category.order_by)
    )


@report.route("/category/<category_id>/delete", methods=["POST"])
@login_required
def delete_category(category_id):
    rc = ReportController()
    category = rc.get_category(category_id)
    if not category:
        abort(404)

    if current_user.username != category.owner:
        abort(403)

    rc.delete_category(category.id)

    return redirect(url_for("wodreport.report_page"))


@report.route("/report/<report_id>")
def view_report(report_id):
    rc = ReportController()
    report = rc.get_report(report_id)
    if not report:
        abort(404)

    report_presenter = ReportPresenter(report)

    rc.incr_views(report_id)
    details = report.details
    return rt(
        "report_details.html",
        report=report,
        details=details,
        subpath="index.html",
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

    submit = SubmitField("更新")


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


@report.route("/report/<report_id>/delete", methods=["POST"])
@login_required
def delete_report(report_id):
    rc = ReportController()
    report = rc.get_report(report_id)
    if not report:
        abort(404)

    if current_user.username != report.owner:
        abort(403)

    category = report.category
    rc.delete_report(report.id)
    return redirect(url_for("wodreport.view_category", category_id=category.id))


@report.route("/report/<report_id>/reader/")
@report.route("/report/<report_id>/reader/<path:subpath>")
def report_reader(report_id, subpath="index.html"):
    if not subpath.endswith(".html"):
        abort(404)

    rc = ReportController()
    report = rc.get_report(report_id)
    if not report:
        abort(404)

    data_dir = current_app.config["DATA_DIR"]
    fpath_str = safe_join(data_dir, report.owner, report.category.name, report.name, subpath)
    if not fpath_str:
        abort(404)

    fpath = Path(fpath_str)

    try:
        if not fpath.exists():
            abort(404)
    except OSError as e:
        current_app.logger.error(f"Failed to access path {fpath_str}: {e}")
        abort(503, description="Storage service is temporarily unavailable.")

    rc.incr_reader_views(report.id)
    rc.incr_views(report.id)
    with fpath.open() as f:
        raw = f.read()
        tree = html.fromstring(raw)
        body = tree.xpath("body")[0]
        
        body = sanitize_wod_report(body)
        
        report_html = etree.tostring(body, pretty_print=False, encoding='unicode')
        report_html = report_html.replace('<body>', '<div id="auto_extracted" style="width: 100vw;">')
        report_html = report_html.replace('</body>', '</div>')
        report_html = report_html.replace('#"', '#/"')
        report_html = report_html.replace('jump(', 'dummy_jump(')
        report_html = report_html.replace('http:', 'https:')

        return rt(
            "report_reader.html",
            report_html=report_html,
            report=report,
            subpath=subpath
        )
    return rt("report_details.html", report=report, subpath="index.html")


@report.route("/all")
def report_page():
    rc = ReportController()
    categories, pagination, page, per_page, total = paginate(rc.get_all_categories)
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
    submit = SubmitField("创建")

    def validate_name(form, field):
        name = field.data
        rc = ReportController()
        if rc.get_category_by_name_and_username(name, current_user.username):
            raise ValidationError(
                "分类 {} 已存在，用户：{}"
                .format(name, current_user.username)
            )



@report.route("/new_category", methods=['GET', 'POST'])
@login_required
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
        # sadd returns 1 only when the member is new; skip the counter
        # otherwise so double-clicks/replays can't inflate it.
        if rc.like(username, report_id):
            rc.incr_likes_cnt(report_id)
        r = {"status": 0, "message": "点赞成功。"}
    else:
        r = {"status": 1, "message": f"战报 {report_id} 不存在。"}
    return jsonify(r)


@report.route("/report/<report_id>/unlike", methods=['POST'])
@login_required
def ajax_unlike(report_id):
    username = current_user.username
    rc = ReportController()
    report = rc.get_report(report_id)
    if report:
        if rc.unlike(username, report_id):
            rc.decr_likes_cnt(report_id)
        r = {"status": 0, "message": "取消点赞成功。"}
    else:
        r = {"status": 1, "message": f"战报 {report_id} 不存在。"}
    return jsonify(r)


@report.route("/report/<report_id>/add_favorite", methods=['POST'])
@login_required
def ajax_add_favorite(report_id):
    username = current_user.username
    rc = ReportController()
    report = rc.get_report(report_id)
    if report:
        if not rc.check_favor(username, report_id):
            rc.add_favor(username, report_id)
            rc.incr_favors(report_id)
        r = {"status": 0, "message": "收藏成功。"}
    else:
        r = {"status": 1, "message": f"战报 {report_id} 不存在。"}
    return jsonify(r)


@report.route("/report/<report_id>/cancel_favorite", methods=['POST'])
@login_required
def ajax_cancel_favorite(report_id):
    username = current_user.username
    rc = ReportController()
    report = rc.get_report(report_id)
    if report:
        if rc.cancel_favor(username, report_id):
            rc.decr_favors(report_id)
        r = {"status": 0, "message": "取消收藏成功。"}
    else:
        r = {"status": 1, "message": f"战报 {report_id} 不存在。"}
    return jsonify(r)


@report.route("favor")
@login_required
def favorite_reports():
    username = current_user.username
    rc = ReportController()
    reports, pagination, page, per_page, total = paginate(
        rc.get_favorite_reports,
        username
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
    # Detect if 'q' parameter is present in the query string
    q = request.args.get("q")
    reports = []
    total = 0
    page, per_page, offset = get_page_args(
        page_parameter='page',
        per_page_parameter='per_page'
    )

    if q is not None:
        q_stripped = q.strip()
        if len(q_stripped) < 2:
            flash("搜索关键字过短，请至少输入 2 个字符。", "warning")
            pagination = Pagination(
                page=page,
                per_page=per_page,
                total=0,
                css_framework='bootstrap5'
            )
        else:
            rc = ReportController()
            reports, pagination, page, per_page, total = paginate(rc.search, q_stripped)
    else:
        pagination = Pagination(
            page=page,
            per_page=per_page,
            total=0,
            css_framework='bootstrap5'
        )

    return rt(
        "search.html",
        q=q or "",
        reports=reports,
        pagination=pagination,
        page=page,
        per_page=per_page,
        total=total
    )
