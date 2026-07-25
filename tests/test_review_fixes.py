# -*- coding: utf-8 -*-
"""Regression tests for the 2026-07-25 code-review Action Items (A1–A6)."""

import io
import zipfile

import pytest

from ohmywod.utils import is_safe_path_segment, is_safe_next_url, clamped_page_args, MAX_PER_PAGE
from ohmywod.controllers.report import ReportController
from ohmywod.controllers.user import UserController
from ohmywod.models.report import Report


# ---------------------------------------------------------------- A1: paths ---
@pytest.mark.parametrize("bad", [
    "", ".", "..", "/tmp/x", "../x", "a/b", "a\\b", ".hidden", "   ", "a\x00b", "tab\tx",
])
def test_path_segment_rejects_unsafe(bad):
    assert is_safe_path_segment(bad) is False


@pytest.mark.parametrize("good", ["cat1", "含中文的分类", "my report", "a-b_c", "R2D2"])
def test_path_segment_accepts_normal(good):
    assert is_safe_path_segment(good) is True


def test_register_rejects_unsafe_username(client, db):
    res = client.post("/register", data={
        "username": "../evil", "display_name": "E", "email": "e@example.com",
        "password1": "pw", "password2": "pw",
    })
    assert UserController().get_db_user("../evil") is None
    assert "路径分隔符" in res.data.decode("utf-8")


def test_new_category_rejects_unsafe_name(authenticated_client, db):
    authenticated_client.post("/r/new_category", data={"name": "../../etc", "description": "x"})
    assert ReportController().get_category_by_name_and_username("../../etc", "testuser") == []


# ------------------------------------------------------- A5: username casing ---
def test_register_rejects_case_insensitive_duplicate(client, register_user, db):
    register_user("Bob", "Bob", "bob@example.com", "pw")
    res = client.post("/register", data={
        "username": "bob", "display_name": "Bob2", "email": "bob2@example.com",
        "password1": "pw", "password2": "pw",
    })
    assert UserController().get_db_user("bob") is None
    assert "已被其他用户使用" in res.data.decode("utf-8")


# ------------------------------------------------------- A4: open redirect ----
@pytest.mark.parametrize("bad", ["https://evil.example", "//evil.example", "/\\evil.example", "http://x", "", None, "evil"])
def test_is_safe_next_url_rejects(bad):
    assert is_safe_next_url(bad) is False


@pytest.mark.parametrize("good", ["/", "/r/", "/r/all?page=2"])
def test_is_safe_next_url_accepts(good):
    assert is_safe_next_url(good) is True


@pytest.mark.parametrize("nxt", ["https://evil.example", "//evil.example", "/\\evil.example"])
def test_login_ignores_offsite_next(client, register_user, db, nxt):
    register_user("redir", "R", "r@example.com", "pw")
    res = client.post(f"/login?next={nxt}", data={"username": "redir", "password": "pw"})
    assert res.status_code == 302
    assert "evil.example" not in res.headers["Location"]


def test_login_follows_local_next(client, register_user, db):
    register_user("redir2", "R", "r2@example.com", "pw")
    res = client.post("/login?next=/r/all", data={"username": "redir2", "password": "pw"})
    assert res.status_code == 302
    assert res.headers["Location"].endswith("/r/all")


# ----------------------------------------------------------- A6: pagination ---
def test_clamped_page_args_bounds_and_offset(app):
    with app.test_request_context("/?page=2&per_page=100000"):
        page, per_page, offset = clamped_page_args()
        assert per_page == MAX_PER_PAGE
        assert offset == (2 - 1) * MAX_PER_PAGE  # offset recomputed after clamp
    with app.test_request_context("/?page=1&per_page=-5"):
        page, per_page, offset = clamped_page_args()
        assert per_page == 1  # lower bound: no negative LIMIT
        assert offset == 0


# ------------------------------------------------------- A2/A3: upload+delete --
def _upload_report(client, cat_id, filename="rep.zip", body="<html><body>hi</body></html>"):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("index.html", body)
    buf.seek(0)
    return client.post(
        f"/upload/process/{cat_id}",
        data={"filepond": (buf, filename)},
        content_type="multipart/form-data",
    )


def test_bad_zip_returns_400(authenticated_client, db):
    cat = ReportController().create_category("catbad", "d", "testuser")
    buf = io.BytesIO(b"this is not a zip")
    res = authenticated_client.post(
        f"/upload/process/{cat.id}",
        data={"filepond": (buf, "broken.zip")},
        content_type="multipart/form-data",
    )
    assert res.status_code == 400
    assert "zip" in res.data.decode("utf-8")


def test_soft_deleted_report_not_publicly_readable(authenticated_client, db):
    cat = ReportController().create_category("cat_del", "d", "testuser")
    assert _upload_report(authenticated_client, cat.id).status_code == 200
    report = Report.query.filter_by(category_id=cat.id).first()
    rid = report.id

    # Readable before delete.
    assert authenticated_client.get(f"/r/report/{rid}").status_code == 200
    assert authenticated_client.get("/r/raw/testuser/cat_del/rep/").status_code == 200

    authenticated_client.post(f"/r/report/{rid}/delete")

    # A2: every public read path 404s after soft delete.
    assert authenticated_client.get(f"/r/report/{rid}").status_code == 404
    assert authenticated_client.get(f"/r/report/{rid}/reader/").status_code == 404
    assert authenticated_client.get("/r/raw/testuser/cat_del/rep/").status_code == 404


def test_soft_deleted_category_not_publicly_readable(authenticated_client, db):
    cat = ReportController().create_category("cat_gone", "d", "testuser")
    cid = cat.id
    assert authenticated_client.get(f"/r/category/{cid}").status_code == 200
    authenticated_client.post(f"/r/category/{cid}/delete")
    assert authenticated_client.get(f"/r/category/{cid}").status_code == 404
