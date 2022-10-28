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
from wtforms import StringField,PasswordField,SubmitField,BooleanField
from wtforms.validators import DataRequired,Email,EqualTo

from ohmywod.controllers.report import ReportController
from ohmywod.controllers.user import UserController


frontend = Blueprint("frontend", __name__)

@frontend.route("/")
def home():
    if not current_user or current_user.is_anonymous:
        return redirect(url_for('frontend.login'))

    rc = ReportController()
    categories = rc.get_cateogories_by_user(current_user.username)
    return rt("home.html", categories=categories)


@frontend.route('/login', methods=['GET', 'POST'])
def login():
    form = LDAPLoginForm()

    if form.validate_on_submit():
        login_user(form.user)  # Tell flask-login to log them in.
        return redirect('/')  # Send them home

    return rt("login.html", form=form)


class RegistrationForm(FlaskForm):
    username = StringField('username', validators =[DataRequired()])
    email = StringField('Email', validators=[DataRequired(),Email()])
    password1 = PasswordField('Password', validators = [DataRequired()])
    password2 = PasswordField('Confirm Password', validators = [DataRequired(),EqualTo('password1')])
    submit = SubmitField('Register')


@frontend.route('/register', methods = ['POST','GET'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        uc = UserController()
        uc.save(
            username=form.username.data,
            email=form.email.data,
            passwd=form.password1.data
        )
        return redirect(url_for('frontend.login'))
    return rt('registration.html', form=form)


@frontend.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect("/")


@frontend.route("/api/user_session", methods=["POST"])
def server_session():
    sidebar_is_active = request.form.get("sidebar_is_active")
    session['sidebar_is_active'] = sidebar_is_active == 'true'
    return 'ok'
