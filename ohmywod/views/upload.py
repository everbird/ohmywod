#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import shutil
import unicodedata
from pathlib import Path
from zipfile import ZipFile

from flask import Blueprint, redirect, request, abort, current_app, flash
from flask_login import current_user

from ohmywod.controllers.report import ReportController, invalidate_sitemap_cache
from ohmywod.extensions import db


upload = Blueprint("upload", __name__)

ALLOWED_EXTENSIONS = {'zip'}
UNSAFE_FILENAME_CHARS = re.compile(r'[\x00-\x1f\x7f<>:"|?*]+')
FILENAME_WHITESPACE = re.compile(r'\s+')


def secure_upload_filename(filename):
    filename = unicodedata.normalize("NFKC", filename or "")
    filename = filename.replace("\\", "/").rsplit("/", 1)[-1]
    filename = UNSAFE_FILENAME_CHARS.sub("_", filename)
    filename = FILENAME_WHITESPACE.sub("_", filename).strip("._ ")
    filename = re.sub(r'_+', '_', filename)
    return filename


def report_name_from_filename(filename):
    return filename.rsplit(".", 1)[0]

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

    try:
        total, used, free = shutil.disk_usage(current_app.config['UPLOAD_DIR'])
        threshold = current_app.config.get('UPLOAD_DISK_USAGE_THRESHOLD', 0.96)
        if (used / total) >= threshold:
            return f"上传失败：本地临时上传空间使用率已达 {int(threshold * 100)}% 或更高，为保证稳定运行已暂停上传功能。", 400
    except OSError as e:
        current_app.logger.error(f"Failed to check local upload staging space: {e}")
        return "上传失败：本地临时上传空间不可用，请联系管理员", 503

    if 'filepond' not in request.files:
        return "上传失败：请求中缺少文件内容", 400
    
    fobj = request.files['filepond']
    # If the username does not select a file, the browser submits an
    # empty file without a filename.
    if fobj.filename == '':
        return "上传失败：未选择任何文件", 400

    if fobj and allowed_file(fobj.filename):
        filename = secure_upload_filename(fobj.filename)
        if not filename or not allowed_file(filename):
            return "上传失败：文件名无效", 400
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

        try:
            fobj.save(os.fspath(fpath))

            with ZipFile(fpath, 'r') as z:
                _filename = report_name_from_filename(filename)
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
        except OSError as e:
            if 'tpath' in locals() and tpath.exists():
                try:
                    shutil.rmtree(tpath)
                except Exception:
                    pass
            if fpath.exists():
                try:
                    fpath.unlink()
                except Exception:
                    pass
            current_app.logger.error(f"File upload/extraction failed: {e}")
            if e.errno == 28:
                return "上传失败：服务器磁盘空间不足", 507
            return f"上传失败：写入文件时发生错误 ({e.strerror or str(e)})", 500

        exist_reports = [x for x in category.display_reports if x.name == _filename]
        if exist_reports:
            report = sorted(exist_reports, key=lambda x: x.created_at, reverse=True)[0]
            report.updated_at = db.func.now()
            db.session.commit()
            invalidate_sitemap_cache()
        else:
            rc.create_report(category.id, _filename, category.owner)
        return uid

    return "上传失败：不支持的文件格式（仅支持 .zip 格式）", 400
