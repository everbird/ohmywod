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
    url_for, current_app, g
)
from flask_ldap3_login.forms import LDAPLoginForm
from flask_login import login_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField,PasswordField,SubmitField,BooleanField
from wtforms.validators import DataRequired,Email,EqualTo

from ohmywod.controllers.user import UserController


frontend = Blueprint("frontend", __name__)

@frontend.route("/")
def home():
    print(current_user)
    print(g._login_user)
    if not current_user or current_user.is_anonymous:
        return redirect(url_for('frontend.login'))

    return rt("home.html")




@frontend.route('/login', methods=['GET', 'POST'])
def login():
    template = """
    {{ get_flashed_messages() }}
    {{ form.errors }}
    <form method="POST">
        <label>Username{{ form.username() }}</label>
        <label>Password{{ form.password() }}</label>
        {{ form.submit() }}
        {{ form.hidden_tag() }}
    </form>
    """

    # Instantiate a LDAPLoginForm which has a validator to check if the user
    # exists in LDAP.
    form = LDAPLoginForm()

    if form.validate_on_submit():
        # Successfully logged in, We can now access the saved user object
        # via form.user.
        login_user(form.user)  # Tell flask-login to log them in.
        print("g:", g._login_user)
        print("g:", form.user.is_anonymous)
        return redirect('/')  # Send them home

    return rt_string(template, form=form)


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
