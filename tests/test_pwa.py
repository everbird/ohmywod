"""PWA stays a small, online-only addition to the existing Flask pages."""

import struct
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from lxml import html

from ohmywod.controllers.report import ReportController
from ohmywod.models.report import Report


@pytest.fixture
def pwa_report(app, db):
    rc = ReportController()
    category = rc.create_category("pwa-fixture", "", "testuser")
    rc.create_report(category.id, "wide-report", "testuser")
    report = Report.query.filter_by(category_id=category.id).one()
    directory = Path(app.config["DATA_DIR"]) / report.owner / category.name / report.name
    directory.mkdir(parents=True, exist_ok=True)
    body = """<html><body>
        <p><a href="level1.html">下一层</a></p>
        <table style="width:1600px"><tr><td>宽表阅读样例</td></tr></table>
        </body></html>"""
    (directory / "index.html").write_text(body, encoding="utf-8")
    (directory / "level1.html").write_text(body, encoding="utf-8")
    return report


def assert_pwa_head(response):
    assert response.status_code == 200
    page = html.fromstring(response.get_data(as_text=True))
    assert page.xpath('//head/link[@rel="manifest"]/@href') == [
        "/static/manifest.webmanifest"
    ]
    assert page.xpath('//head/meta[@name="theme-color"]/@content') == ["#222222"]
    assert page.xpath('//head/meta[@name="apple-mobile-web-app-capable"]/@content') == ["yes"]
    assert page.xpath('//head/link[@rel="apple-touch-icon"]/@href') == [
        "/static/img/apple-touch-icon.png"
    ]
    return page


def test_manifest_has_one_stable_online_app_identity(client):
    response = client.get("/static/manifest.webmanifest")
    assert response.status_code == 200
    assert response.mimetype == "application/manifest+json"
    manifest = response.get_json()
    assert manifest["id"] == "/"
    assert manifest["name"] == "OhMyWoD 战报网"
    assert manifest["short_name"] == "战报网"
    assert manifest["lang"] == "zh-CN"
    assert manifest["display"] == "standalone"
    assert manifest["scope"] == "/"
    assert manifest["start_url"] == "/r/all"
    assert "orientation" not in manifest  # Wide tables can still use landscape.
    assert client.get(manifest["start_url"]).status_code == 200
    assert [(icon["sizes"], icon["purpose"]) for icon in manifest["icons"]] == [
        ("192x192", "any"), ("512x512", "any"), ("512x512", "maskable")
    ]
    for icon in manifest["icons"]:
        assert icon["src"].startswith("/static/img/")
        assert icon["type"] == "image/png"


@pytest.mark.parametrize("path", [
    "/", "/r/all", "/r/search", "/help", "/login", "/register", "/forgot-password"
])
def test_public_pages_share_install_metadata(client, path):
    assert_pwa_head(client.get(path))


@pytest.mark.parametrize("filename,size", [
    ("pwa-192.png", 192),
    ("pwa-512.png", 512),
    ("pwa-maskable-512.png", 512),
    ("apple-touch-icon.png", 180),
])
def test_install_icons_are_anonymous_pngs_of_declared_size(client, filename, size):
    response = client.get("/static/img/" + filename)
    assert response.status_code == 200
    assert response.mimetype == "image/png"
    assert response.data[:8] == b"\x89PNG\r\n\x1a\n"
    assert struct.unpack(">II", response.data[16:24]) == (size, size)


def test_reader_and_subpages_share_manifest_and_native_return(client, pwa_report):
    for subpath in ("", "level1.html"):
        response = client.get(f"/r/report/{pwa_report.id}/reader/{subpath}")
        page = assert_pwa_head(response)
        content = page.xpath('//div[contains(@class, "reader-report-content")]')
        assert len(content) == 1
        assert "宽表阅读样例" in content[0].text_content()
        assert content[0].xpath('.//a[@href="level1.html"]')
        back = page.xpath('//nav[@aria-label="阅读导航"]/a')
        assert len(back) == 1
        assert back[0].get("href") == f"/r/report/{pwa_report.id}"
        assert back[0].get("target") is None
        assert not back[0].xpath('ancestor::div[contains(@class, "reader-report-content")]')
        # Scope the old event interception to report content, not app controls.
        assert '$(".reader-report-content").find("a, span")' in response.get_data(as_text=True)


@pytest.mark.parametrize("path", ["/", "/help"])
def test_site_tutorial_links_stay_in_the_app_window(client, path):
    page = html.fromstring(client.get(path).get_data(as_text=True))
    links = page.xpath('//main//a[starts-with(@href, "/r/")]')
    assert links
    assert all(link.get("target") != "_blank" for link in links)
    # Export userscript and WoD/GitHub links may still open outside the app.


def test_login_profile_and_logout_remain_inside_manifest_scope(authenticated_client):
    assert_pwa_head(authenticated_client.get("/r/"))
    assert_pwa_head(authenticated_client.get("/r/favor"))
    assert_pwa_head(authenticated_client.get("/profile"))
    logout = authenticated_client.get("/logout")
    assert logout.status_code == 302
    destination = urlsplit(logout.headers["Location"])
    assert not destination.netloc
    assert destination.path == "/login"
    assert_pwa_head(authenticated_client.get(destination.path))
