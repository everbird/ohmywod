#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#

import os
import shutil
from pathlib import Path

from sqlalchemy import text

from flask import (
    Blueprint,
    flash,
    render_template as rt,
    render_template_string as rt_string,
    redirect,
    url_for, current_app, g, session, request, jsonify
)
from flask_login import login_user, current_user, login_required, logout_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField, SelectField
from wtforms.validators import DataRequired, Email, EqualTo, ValidationError
from wtforms.widgets import TextArea

from ohmywod import security
from ohmywod.controllers.feedback import FeedbackController
from ohmywod.controllers.report import ReportController
from ohmywod.controllers.user import UserController
from ohmywod.extensions import cache, db, redis, limiter, client_ip_key
from ohmywod.models.report import Report, ReportCategory


frontend = Blueprint("frontend", __name__)

@frontend.route("/")
def landing_page():
    return rt("landing.html")


class LoginForm(FlaskForm):
    username = StringField('用户名', validators=[DataRequired()])
    password = PasswordField('密码', validators=[DataRequired()])
    submit = SubmitField('登录')


def _login_username_key():
    # Per-account dimension: throttles a targeted (possibly distributed) brute
    # force on one username. Empty -> fall back to the IP bucket so blank
    # submissions don't share one global bucket.
    username = (request.form.get("username") or "").strip().lower()
    return f"login-user:{username}" if username else client_ip_key()


@frontend.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute; 60 per hour", methods=["POST"])
@limiter.limit("6 per minute", methods=["POST"], key_func=_login_username_key)
def login():
    form = LoginForm()

    if form.validate_on_submit():
        uc = UserController()
        user = uc.authenticate(form.username.data, form.password.data)
        if user is not None:
            login_user(user)  # Tell flask-login to log them in.
            next_url = request.args.get("next")
            if next_url:
                return redirect(next_url)
            return redirect(url_for("wodreport.home"))  # Send them home
        # Generic message avoids leaking whether the username exists.
        flash("用户名或密码错误。")

    return rt("login.html", form=form)


class RegistrationForm(FlaskForm):
    username = StringField('用户名', validators =[DataRequired()])
    display_name = StringField('显示名称')
    email = StringField('邮箱', validators=[DataRequired(),Email()])
    password1 = PasswordField('密码', validators = [DataRequired()])
    password2 = PasswordField('确认密码', validators = [DataRequired(),EqualTo('password1')])
    # Honeypot: hidden from humans (see registration.html); bots that autofill
    # it are silently dropped. No validators so it never bothers real users.
    website = StringField('请勿填写')
    submit = SubmitField('注册')

    def validate_email(form, field):
        email = field.data
        if email:
            uc = UserController()
            if uc.get_db_user_by_email(email):
                raise ValidationError("邮箱已被其他用户使用。")

    def validate_display_name(form, field):
        display_name = field.data
        if display_name:
            uc = UserController()
            db_user = uc.get_db_user_by_display_name(display_name)
            if db_user:
                raise ValidationError("显示名称已被其他用户使用。")

    def validate_username(form, field):
        username = field.data
        if username:
            uc = UserController()
            db_user = uc.get_db_user(username)
            if db_user:
                raise ValidationError("用户名已被其他用户使用。")




@frontend.route('/register', methods = ['POST','GET'])
@limiter.limit("5 per minute; 30 per hour", methods=["POST"])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        # Honeypot tripped -> pretend success without creating anything.
        if form.website.data:
            current_app.logger.info("register honeypot tripped from %s", client_ip_key())
            return redirect(url_for('frontend.login'))
        uc = UserController()
        uc.save(
            username=form.username.data,
            display_name=form.display_name.data,
            email=form.email.data,
            passwd=form.password1.data
        )
        return redirect(url_for('frontend.login'))
    return rt('registration.html', form=form)


@frontend.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for('frontend.login'))


@frontend.route("/api/session/<key>", methods=["POST"])
def server_session(key):
    allowed_keys = {'sidebar_is_active'}
    if key not in allowed_keys:
        return 'forbidden', 403

    v = request.form.get(key)
    if key in allowed_keys:
        #FIXME: TIL: json boolean -> python string rather than boolean in Flask
        v = (v == 'true')

    session[key] = v
    return 'ok'


@frontend.route("/help")
def help_page():
    return redirect(url_for("frontend.landing_page"))
    # return rt("help.html")


@frontend.route("/usage")
def usage_page():
    rc = ReportController()
    stats = rc.get_system_stats()
    latest_reports = rc.get_latest_reports(limit=5)
    return rt("usage.html", stats=stats, latest_reports=latest_reports)


class FeedbackForm(FlaskForm):
    username = StringField('你的名称')
    feedback = StringField("反馈内容", widget=TextArea())
    submit = SubmitField("提交")


@frontend.route("/feedback", methods=["POST", "GET"])
# IMP-006: feedback is an open (unauthenticated) text POST -> spam vector.
# Conservative per-IP cap; GET (viewing the form) is unaffected.
@limiter.limit("5 per minute; 20 per hour", methods=["POST"])
def feedback_page():
    form = FeedbackForm()
    if form.validate_on_submit():
        fc = FeedbackController()
        fc.create_feedback(
            form.username.data,
            form.feedback.data
        )
        return rt("feedback_submitted.html")

    return rt("feedback.html", form=form)


class ProfileForm(FlaskForm):
    display_name = StringField('显示名称')
    email = StringField('邮箱', validators=[Email()])
    old_password = PasswordField('旧密码')
    new_password1 = PasswordField('新密码')
    new_password2 = PasswordField('确认新密码', validators = [EqualTo('new_password1')])
    submit = SubmitField('更新')

    def validate_email(form, field):
        email = field.data
        if email and current_user.email != email:
            uc = UserController()
            if uc.get_db_user_by_email(email):
                raise ValidationError("邮箱已被其他用户使用。")

    def validate_old_password(form, field):
        old_password = field.data
        if old_password:
            # Re-auth against the stored hash directly (no lazy upgrade here;
            # the actual password change re-hashes anyway).
            if not security.verify_password(current_user.password, old_password):
                raise ValidationError("旧密码不匹配。")
        elif form.new_password1.data or form.new_password2.data:
            raise ValidationError("修改密码时需要填写旧密码。")



@frontend.route("/profile", methods=["POST", "GET"])
@login_required
def profile_page():
    form = ProfileForm(
        display_name=current_user.display_name,
        email=current_user.email,
    )
    if form.validate_on_submit():
        uc = UserController()
        uc.update_user(
            current_user.username,
            form.display_name.data,
            form.email.data,
            form.new_password1.data,
        )

        flash("更新成功。")
        return redirect(url_for('frontend.profile_page'))
    return rt("profile.html", form=form)


@frontend.route("healthz")
def healthz():
    checks = {}
    http_status = 200

    try:
        db.session.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception:
        current_app.logger.exception("healthz database check failed")
        checks["db"] = "error"
        http_status = 503

    try:
        redis.ping()
        checks["redis"] = "ok"
    except Exception:
        current_app.logger.exception("healthz redis check failed")
        checks["redis"] = "error"
        http_status = 503

    storage_checks = {}
    storage_paths = current_app.config.get("HEALTHZ_STORAGE_PATHS") or (
        current_app.config["DATA_DIR"],
    )
    for raw_path in storage_paths:
        path = Path(raw_path)
        try:
            if path.is_dir() and os.access(path, os.R_OK):
                storage_checks[str(path)] = "ok"
            else:
                storage_checks[str(path)] = "error"
                http_status = 503
        except OSError:
            current_app.logger.exception("healthz storage check failed for %s", path)
            storage_checks[str(path)] = "error"
            http_status = 503
    checks["storage"] = storage_checks

    status = "ok" if http_status == 200 else "error"
    return jsonify(status=status, checks=checks), http_status


@frontend.route("ads.txt")
def ads_txt():
    return rt("ads.txt")


@frontend.route("robots.txt")
def robots_txt():
    return rt("robots.txt")


@frontend.route("sitemap.xml")
def sitemap_xml():
    # Cached because it walks the whole report table and crawlers hit it
    # repeatedly; 1h staleness is fine for a sitemap.
    xml = cache.get("sitemap_xml")
    if xml is None:
        reports = (
            Report.query
            .filter(Report.status == None)
            .order_by(Report.updated_at.desc())
            .all()
        )
        categories = (
            ReportCategory.query
            .filter(ReportCategory.status == None)
            .all()
        )
        xml = rt("sitemap.xml", reports=reports, categories=categories)
        cache.set("sitemap_xml", xml, timeout=3600)
    return current_app.response_class(xml, mimetype="application/xml")
