#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#

import os
from pathlib import Path

from flask import (
    Blueprint,
    flash,
    render_template as rt,
    render_template_string as rt_string,
    redirect,
    url_for, current_app, g, session, request
)
from flask_ldap3_login import AuthenticationResponseStatus
from flask_ldap3_login.forms import LDAPLoginForm
from flask_login import login_user, current_user, login_required, logout_user
from flask_wtf import FlaskForm
from ldap3 import HASHED_SALTED_SHA
from ldap3.utils.hashed import hashed
from wtforms import StringField, PasswordField, SubmitField, BooleanField, SelectField
from wtforms.validators import DataRequired, Email, EqualTo, ValidationError
from wtforms.widgets import TextArea

from ohmywod.controllers.feedback import FeedbackController
from ohmywod.controllers.report import ReportController
from ohmywod.controllers.user import UserController
from ohmywod.extensions import ldap_manager


frontend = Blueprint("frontend", __name__)

@frontend.route("/")
def landing_page():
    return rt("landing.html")


@frontend.route('/login', methods=['GET', 'POST'])
def login():
    form = LDAPLoginForm()

    if form.validate_on_submit():
        login_user(form.user)  # Tell flask-login to log them in.
        args = request.args
        next_url = args.get("next")
        if next_url:
            return redirect(next_url)

        return redirect(url_for("wodreport.home"))  # Send them home

    return rt("login.html", form=form)


class RegistrationForm(FlaskForm):
    username = StringField('username', validators =[DataRequired()])
    display_name = StringField('display_name')
    email = StringField('Email', validators=[DataRequired(),Email()])
    password1 = PasswordField('Password', validators = [DataRequired()])
    password2 = PasswordField('Confirm Password', validators = [DataRequired(),EqualTo('password1')])
    submit = SubmitField('Register')

    def validate_email(form, field):
        email = field.data
        if email:
            uc = UserController()
            ldap_user = uc.get_ldap_user_by_email(email)
            db_user = uc.get_db_user_by_email(email)
            if ldap_user or db_user:
                raise ValidationError("Email is already used by other users.")

    def validate_display_name(form, field):
        display_name = field.data
        if display_name:
            uc = UserController()
            db_user = uc.get_db_user_by_display_name(display_name)
            if db_user:
                raise ValidationError("Display name is already used by other users.")

    def validate_username(form, field):
        username = field.data
        if username:
            uc = UserController()
            db_user = uc.get_db_user(username)
            if db_user:
                raise ValidationError("Username is already used by other users.")




@frontend.route('/register', methods = ['POST','GET'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
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
    boolean_keys = {'sidebar_is_active'}
    v = request.form.get(key)
    if key in boolean_keys:
        #FIXME: TIL: json boolean -> python string rather than boolean in Flask
        v = (v == 'true')

    session[key] = v
    return 'ok'


@frontend.route("/help")
def help_page():
    return redirect(url_for("frontend.landing_page"))
    # return rt("help.html")


class FeedbackForm(FlaskForm):
    username = StringField('Your Name')
    feedback = StringField("Content", widget=TextArea())
    submit = SubmitField("Submit")


@frontend.route("/feedback", methods=["POST", "GET"])
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
    display_name = StringField('display_name')
    reader_theme = SelectField(
        'Report reader theme',
        choices=[
            (1, 'Office'),
            (2, 'WoD Stone'),
            (3, 'WoD Classic'),
            (4, 'WoD Alternative'),
            (5, 'Starmarines'),
            (6, 'Old Ages Classic'),
            (7, 'Old Ages Default'),
            (9, 'Zeitgeist'),
            (10, 'Red Dragon'),
        ]
    )
    app_theme = SelectField(
        'App theme',
        choices=[
            ('darkly', 'Darkly'),
            ('cyborg', 'Cyborg'),
            ('vapor', 'Vapor'),
        ]
    )
    email = StringField('Email', validators=[Email()])
    old_password = PasswordField('Password')
    new_password1 = PasswordField('Password')
    new_password2 = PasswordField('Confirm Password', validators = [EqualTo('new_password1')])
    submit = SubmitField('Update')

    def validate_email(form, field):
        email = field.data
        if email and current_user.db_user.email != email:
            uc = UserController()
            ldap_user = uc.get_ldap_user_by_email(email)
            db_user = uc.get_db_user_by_email(email)
            if ldap_user or db_user:
                raise ValidationError("Email is already used by other users.")

    def validate_old_password(form, field):
        old_password = field.data
        if old_password:
            result = ldap_manager.authenticate(current_user.username, old_password)
            print(result.status)
            if result.status != AuthenticationResponseStatus.success:
                raise ValidationError("Password doesn't match with existing one")
        elif form.new_password1.data or form.new_password2.data:
            raise ValidationError("Old password is require when change to a new password.")



@frontend.route("/profile", methods=["POST", "GET"])
@login_required
def profile_page():
    form = ProfileForm(
        display_name=current_user.display_name,
        email=current_user.db_user.email,
        reader_theme=current_user.reader_theme or 4,
        app_theme=current_user.app_theme,
    )
    if form.validate_on_submit():
        uc = UserController()
        uc.update_user(
            current_user.username,
            form.display_name.data,
            form.email.data,
            form.new_password1.data,
            form.reader_theme.data,
            form.app_theme.data
        )

        flash("Updated successfully.")
        return redirect(url_for('frontend.profile_page'))
    return rt("profile.html", form=form)
