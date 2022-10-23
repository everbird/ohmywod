#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#

import os
from pathlib import Path
from zipfile import ZipFile

from flask import (
    Blueprint,
    render_template as rt,
    render_template_string as rt_string,
    redirect,
    abort,
    url_for,
    current_app
)
from flask_ldap3_login.forms import LDAPLoginForm
from flask_login import login_user, current_user
from flask_wtf import FlaskForm
from ldap3 import HASHED_SALTED_SHA, MODIFY_ADD
from ldap3.utils.hashed import hashed
from lxml import etree, html
from wtforms import StringField,PasswordField,SubmitField,BooleanField
from wtforms.validators import DataRequired,Email,EqualTo


frontend = Blueprint("frontend", __name__)

ALLOWED_EXTENSIONS = {'zip'}

def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def listdir_only(path):
    for x in os.listdir(path):
        dpath = os.path.join(path, x)
        if os.path.isdir(dpath):
            yield x


@frontend.route("/r/<username>/<category>/<name>/")
@frontend.route("/r/<username>/<category>/<name>/<path:subpath>")
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


@frontend.route("/r/<username>/<category>/")
def report_category(username, category):
    data_dir = current_app.config["DATA_DIR"]
    cpath = os.path.join(data_dir, username, category)
    dirs = listdir_only(cpath)
    return rt("category.html", category=category, username=username, dirs=dirs)


@frontend.route("/r/")
def report():
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


@frontend.route("/")
def home():
    if not current_user or current_user.is_anonymous:
        return redirect(url_for('frontend.login'))

    return rt("home.html")


@frontend.route("/upload/process/<username>/<category>", methods=["POST",])
def process(username, category):
    if current_user.is_anonymous or current_user.username != username:
        abort(401)

    if 'filepond' not in request.files:
        flash('No file part')
        return redirect(request.url)
    fobj = request.files['filepond']
    # If the username does not select a file, the browser submits an
    # empty file without a filename.
    if fobj.filename == '':
        flash('No selected file')
        return redirect(request.url)

    if fobj and allowed_file(fobj.filename):
        #filename = secure_filename(fobj.filename)
        filename = fobj.filename
        uid = os.path.join(category, filename)
        dpath = Path(os.path.join(app.config['UPLOAD_DIR'], username, category))
        dpath.mkdir(parents=True, exist_ok=True)
        fpath = dpath / filename

        fobj.save(os.fspath(fpath))

        with ZipFile(fpath, 'r') as z:
            _filename = filename.replace(".zip", "")
            data_dir = current_app.config["DATA_DIR"]
            tpath = Path(data_dir) / username / category / _filename
            tpath.mkdir(parents=True, exist_ok=True)
            z.extractall(os.fspath(tpath))

        return uid

    abort(400)


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
        return redirect('/')  # Send them home

    return rt_string(template, form=form)


class RegistrationForm(FlaskForm):
    username = StringField('username', validators =[DataRequired()])
    email = StringField('Email', validators=[DataRequired(),Email()])
    password1 = PasswordField('Password', validators = [DataRequired()])
    password2 = PasswordField('Confirm Password', validators = [DataRequired(),EqualTo('password1')])
    submit = SubmitField('Register')


def save_ldap_user(username, email, passwd):
    conn = ldap_manager.connection
    dn = f'cn={username},ou=users,dc=everbird,dc=me'
    hashed_passwd = hashed(HASHED_SALTED_SHA, passwd)
    r = conn.add(
        dn,
        'inetOrgPerson',
        {
            "displayName": username,
            "mail": email,
            "sn": username,
            "userPassword": hashed_passwd,
        }
    )
    return r


@frontend.route('/register', methods = ['POST','GET'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        save_ldap_user(
            username=form.username.data,
            email=form.email.data,
            passwd=form.password1.data
        )
        return redirect(url_for('frontend.login'))
    return rt('registration.html', form=form)
