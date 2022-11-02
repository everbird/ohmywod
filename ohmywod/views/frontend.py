#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#

import os
from pathlib import Path

from flask import (
    Blueprint,
    render_template as rt,
    render_template_string as rt_string,
    redirect,
    url_for, current_app, g, session, request
)
from flask_ldap3_login.forms import LDAPLoginForm
from flask_login import login_user, current_user, login_required, logout_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField
from wtforms.validators import DataRequired, Email, EqualTo, ValidationError

from ohmywod.controllers.report import ReportController
from ohmywod.controllers.user import UserController


frontend = Blueprint("frontend", __name__)

@frontend.route("/")
def landing_page():
    return rt("landing.html")


@frontend.route('/login', methods=['GET', 'POST'])
def login():
    form = LDAPLoginForm()

    if form.validate_on_submit():
        login_user(form.user)  # Tell flask-login to log them in.
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
    return rt("help.html")


@frontend.route("/feedback")
def feedback_page():
    return rt("feedback.html")
