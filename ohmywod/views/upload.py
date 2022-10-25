#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from pathlib import Path
from zipfile import ZipFile

from flask import Blueprint, redirect, request, abort, current_app
from flask_login import current_user

from ohmywod.controllers.report import ReportController


upload = Blueprint("upload", __name__)

ALLOWED_EXTENSIONS = {'zip'}

def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@upload.route("/process/<username>/<category>", methods=["POST",])
def process(username, category):
    if current_user.is_anonymous or current_user.username != username:
        print("before 401", current_user, username, current_user.username)
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
        dpath = Path(
            os.path.join(
                current_app.config['UPLOAD_DIR'],
                username,
                category
            )
        )
        dpath.mkdir(parents=True, exist_ok=True)
        fpath = dpath / filename

        fobj.save(os.fspath(fpath))

        with ZipFile(fpath, 'r') as z:
            _filename = filename.replace(".zip", "")
            data_dir = current_app.config["DATA_DIR"]
            tpath = Path(data_dir) / username / category / _filename
            tpath.mkdir(parents=True, exist_ok=True)
            z.extractall(os.fspath(tpath))

        rc = ReportController()
        rc.create_report(category, _filename, username)
        return uid

    abort(400)
