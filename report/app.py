#!/usr/bin/env python3

from datetime import datetime
import os
from pathlib import Path
from zipfile import ZipFile

from flask import (
    Flask, abort, redirect, render_template, request, url_for, render_template_string,
    redirect
)
from flask_ldap3_login import LDAP3LoginManager
from flask_login import LoginManager, login_user, UserMixin, current_user
from flask_ldap3_login.forms import LDAPLoginForm
from flask_wtf import FlaskForm


from ldap3 import (
    HASHED_SALTED_SHA, MODIFY_ADD
)
from ldap3.utils.hashed import hashed
from lxml import etree, html

from wtforms import StringField,PasswordField,SubmitField,BooleanField
from wtforms.validators import DataRequired,Email,EqualTo

from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename


app = Flask(__name__)


DATA_DIR = "/Users/everbird/playground/wod/ohmywod/.data/report"
UPLOAD_DIR = "/Users/everbird/playground/wod/ohmywod/.data/upload"
ALLOWED_EXTENSIONS = {'zip'}

app.config["UPLOAD_DIR"] = UPLOAD_DIR
app.config["SECRET_KEY"] = "6e848025ab466c03faa992f11cfb132be8b6935dbb0bb358898163ca2bc9e3f8"

# Hostname of your LDAP Server
app.config['LDAP_HOST'] = 'everbird.me'

# Base DN of your directory
app.config['LDAP_BASE_DN'] = 'dc=everbird,dc=me'

# Users DN to be prepended to the Base DN
app.config['LDAP_USER_DN'] = 'ou=users'

# Groups DN to be prepended to the Base DN
app.config['LDAP_GROUP_DN'] = 'ou=groups'

# The RDN attribute for your user schema on LDAP
app.config['LDAP_USER_RDN_ATTR'] = 'cn'

# The Attribute you want users to authenticate to LDAP with.
app.config['LDAP_USER_LOGIN_ATTR'] = 'cn'

# The Username to bind to LDAP with
app.config['LDAP_BIND_USER_DN'] = "cn=admin,dc=everbird,dc=me"

# The Password to bind to LDAP with
app.config['LDAP_BIND_USER_PASSWORD'] = "2Bornot2Bldap"

app.config['LDAP_GROUP_OBJECT_FILTER'] = "(objectclass=groupOfNames)"
app.config['LDAP_USER_OBJECT_FILTER'] = "(objectclass=inetOrgPerson)"
app.config['LDAP_READONLY'] = False


login_manager = LoginManager(app)
ldap_manager = LDAP3LoginManager(app)

users = {}


class User(UserMixin):
    def __init__(self, dn, username, data):
        self.dn = dn
        self.username = username
        self.data = data

    def __repr__(self):
        return self.dn

    def get_id(self):
        return self.dn



@login_manager.user_loader
def load_user(id):
    if id in users:
        return users[id]
    return None

@ldap_manager.save_user
def save_user(dn, username, data, memberships):
    user = User(dn, username, data)
    users[dn] = user
    return user


def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def listdir_only(path):
    for x in os.listdir(path):
        dpath = os.path.join(path, x)
        if os.path.isdir(dpath):
            yield x


@app.route("/r/<username>/<category>/<name>/")
@app.route("/r/<username>/<category>/<name>/<path:subpath>")
def report_details(username, category, name, subpath="index.html"):
    rpath = os.path.join(DATA_DIR, username, category, name)
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

        return render_template(
            "layout.html",
            report_html=report_html,
            username=username,
            category=category,
            name=name,
            subpath=subpath
        )


@app.route("/r/<username>/<category>/")
def report_category(username, category):
    cpath = os.path.join(DATA_DIR, username, category)
    dirs = listdir_only(cpath)
    return render_template("category.html", category=category, username=username, dirs=dirs)


@app.route("/r/")
def report():
    rpath = Path(DATA_DIR)
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

    return render_template("root.html", dirs=dirs)


@app.route("/")
def home():
    if not current_user or current_user.is_anonymous:
        return redirect(url_for('login'))

    return render_template("home.html")


@app.route("/upload/process/<username>/<category>", methods=["POST",])
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
            tpath = Path(DATA_DIR) / username / category / _filename
            tpath.mkdir(parents=True, exist_ok=True)
            z.extractall(os.fspath(tpath))

        return uid

    abort(400)


@app.route('/login', methods=['GET', 'POST'])
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

    return render_template_string(template, form=form)


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


@app.route('/register', methods = ['POST','GET'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        save_ldap_user(
            username=form.username.data,
            email=form.email.data,
            passwd=form.password1.data
        )
        return redirect(url_for('login'))
    return render_template('registration.html', form=form)
