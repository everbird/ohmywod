#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import shutil
from pathlib import Path
from zipfile import ZipFile

from flask import Blueprint, redirect, request, abort, current_app, flash
from werkzeug.utils import secure_filename
from flask_login import current_user

from ohmywod.controllers.report import ReportController
from ohmywod.extensions import db


upload = Blueprint("upload", __name__)

ALLOWED_EXTENSIONS = {'zip'}

def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@upload.route("/process/<category_id>", methods=["POST",])
def process(category_id):
    rc = ReportController()
    category = rc.get_category(category_id)
    if not category:
        return "上传失败：找不到指定的目录", 404

    if current_user.is_anonymous or current_user.username != category.owner:
        return "上传失败：您没有权限上传到此目录", 401

    total, used, free = shutil.disk_usage("/")
    threshold = current_app.config.get('DISK_USAGE_THRESHOLD', 0.96)
    if (used / total) >= threshold:
        return f"上传失败：服务器磁盘使用率已达 {int(threshold * 100)}% 或更高，为保证稳定运行已暂停上传功能。", 400

    if 'filepond' not in request.files:
        return "上传失败：请求中缺少文件内容", 400
    
    fobj = request.files['filepond']
    # If the username does not select a file, the browser submits an
    # empty file without a filename.
    if fobj.filename == '':
        return "上传失败：未选择任何文件", 400

    if fobj and allowed_file(fobj.filename):
        filename = secure_filename(fobj.filename)
        uid = os.path.join(str(category.id), filename)
        dpath = Path(
            os.path.join(
                current_app.config['UPLOAD_DIR'],
                category.owner,
                category.name
            )
        )
        dpath.mkdir(parents=True, exist_ok=True)
        fpath = dpath / filename

        fobj.save(os.fspath(fpath))

        with ZipFile(fpath, 'r') as z:
            _filename = filename.replace(".zip", "")
            data_dir = current_app.config["DATA_DIR"]
            tpath = Path(data_dir) / category.owner / category.name / _filename
            tpath.mkdir(parents=True, exist_ok=True)
            
            # Secure extraction to prevent Zip Slip
            tpath_abs = os.path.abspath(os.fspath(tpath))
            for member in z.infolist():
                member_name = member.filename
                if '..' in member_name or member_name.startswith('/'):
                    continue
                target_path = os.path.abspath(os.path.join(tpath_abs, member_name))
                if not target_path.startswith(tpath_abs):
                    continue
                z.extract(member, os.fspath(tpath))

        exist_reports = [x for x in category.display_reports if x.name == _filename]
        if exist_reports:
            report = sorted(exist_reports, key=lambda x: x.created_at, reverse=True)[0]
            report.updated_at = db.func.now()
            db.session.commit()
        else:
            rc.create_report(category.id, _filename, category.owner)
        return uid

    return "上传失败：不支持的文件格式（仅支持 .zip 格式）", 400
