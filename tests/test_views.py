# -*- coding: utf-8 -*-

import io
import os
import zipfile
from flask import url_for
from lxml import html
import pytest

from ohmywod.controllers.report import ReportController
from ohmywod.models.report import Report, ReportCategory
from ohmywod.views.report import sanitize_wod_report


def test_landing_page(client):
    res = client.get('/')
    assert res.status_code == 200
    assert "OhMyWoD" in res.data.decode('utf-8')


def test_registration_flow(client):
    # GET register form
    res = client.get('/register')
    assert res.status_code == 200

    # POST registration
    res = client.post('/register', data={
        'username': 'jane',
        'display_name': 'Jane Doe',
        'email': 'jane@example.com',
        'password1': 'secpass123',
        'password2': 'secpass123'
    }, follow_redirects=True)
    assert res.status_code == 200
    # Success redirects to login page
    assert "login" in res.request.path.lower()

    # Try registering with duplicate username
    res = client.post('/register', data={
        'username': 'jane',
        'display_name': 'Jane Two',
        'email': 'jane2@example.com',
        'password1': 'secpass123',
        'password2': 'secpass123'
    })
    assert res.status_code == 200
    assert "用户名已被其他用户使用。" in res.data.decode('utf-8')


def test_login_logout(client, register_user):
    register_user("bob", "Bob D", "bob@example.com", "bobpassword")

    # Failed login
    res = client.post('/login', data={
        'username': 'bob',
        'password': 'wrongpassword'
    })
    assert res.status_code == 200
    # Should stay on login page
    assert "login" in res.request.path.lower()
    assert "invalid-feedback" in res.data.decode('utf-8')

    # Successful login
    res = client.post('/login', data={
        'username': 'bob',
        'password': 'bobpassword'
    }, follow_redirects=True)
    assert res.status_code == 200
    # Should redirect to report home page (which in frontend redirects or loads home)
    assert "/r/" in res.request.path

    # Logout
    res = client.get('/logout', follow_redirects=True)
    assert res.status_code == 200
    assert "login" in res.request.path.lower()


def test_profile_page_requires_login(client):
    res = client.get('/profile')
    assert res.status_code == 302
    assert "login" in res.headers['Location']


def test_profile_page_update(authenticated_client):
    res = authenticated_client.get('/profile')
    assert res.status_code == 200

    # Submit profile update
    res = authenticated_client.post('/profile', data={
        'display_name': 'New Test User Name',
        'email': 'newtest@example.com',
        'old_password': '',
        'new_password1': '',
        'new_password2': ''
    }, follow_redirects=True)
    assert res.status_code == 200
    assert "更新成功。" in res.data.decode('utf-8')


def test_feedback_page(client):
    res = client.get('/feedback')
    assert res.status_code == 200

    res = client.post('/feedback', data={
        'username': 'Guest User',
        'feedback': 'Excellent application interface!'
    }, follow_redirects=True)
    assert res.status_code == 200
    assert "feedback_submitted" in res.data.decode('utf-8') or "feedback" in res.request.path.lower()




def test_report_home_page(authenticated_client):
    res = authenticated_client.get('/r/')
    assert res.status_code == 200


def test_view_category(authenticated_client, db):
    rc = ReportController()
    cat = rc.create_category("cat1", "Cat Desc", "testuser")
    
    res = authenticated_client.get(f'/r/category/{cat.id}')
    assert res.status_code == 200
    assert "cat1" in res.data.decode('utf-8')


def test_sanitize_wod_report():
    html_raw = """
    <html>
        <body>
            <div onmouseover="return wodToolTip(this,'<b>Tooltip</b>');" onclick="return co('param');">
                Hello
            </div>
            <script>alert(1);</script>
        </body>
    </html>
    """
    doc = html.fromstring(html_raw)
    sanitized = sanitize_wod_report(doc)
    html_str = html.tostring(sanitized, encoding='unicode')
    
    # Tooltip and click handlers should be preserved if they match secure patterns
    assert "wodToolTip" in html_str
    assert "co(" in html_str
    # Scripts must be stripped out
    assert "<script>" not in html_str


def test_report_raw_retrieval(authenticated_client, app, db):
    rc = ReportController()
    cat = rc.create_category("cat1", "Cat Desc", "testuser")
    rc.create_report(cat.id, "myreport", "testuser")

    # Create dummy directory structure and index.html under app DATA_DIR
    report_dir = os.path.join(app.config['DATA_DIR'], 'testuser', 'cat1', 'myreport')
    os.makedirs(report_dir, exist_ok=True)
    report_file = os.path.join(report_dir, 'index.html')
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("<html><body>Test Report HTML Content</body></html>")

    # Request the raw route
    res = authenticated_client.get('/r/raw/testuser/cat1/myreport/')
    assert res.status_code == 200
    assert "Test Report HTML Content" in res.data.decode('utf-8')



def test_report_raw_csp_sandbox(authenticated_client, app, db):
    rc = ReportController()
    cat = rc.create_category("cat1", "Cat Desc", "testuser")
    rc.create_report(cat.id, "myreport", "testuser")

    report_dir = os.path.join(app.config['DATA_DIR'], 'testuser', 'cat1', 'myreport')
    os.makedirs(report_dir, exist_ok=True)
    with open(os.path.join(report_dir, 'index.html'), 'w', encoding='utf-8') as f:
        f.write("<html><body>Sandboxed</body></html>")

    res = authenticated_client.get('/r/raw/testuser/cat1/myreport/')
    assert res.status_code == 200
    csp = res.headers.get('Content-Security-Policy', '')
    assert 'sandbox' in csp
    assert 'allow-scripts' in csp
    # Must NOT allow same-origin, that would defeat the sandbox
    assert 'allow-same-origin' not in csp


def test_new_category_requires_login(client):
    res = client.get('/r/new_category')
    assert res.status_code == 302
    assert "login" in res.headers['Location']

    # Anonymous POST used to 500 (AttributeError on current_user.username)
    res = client.post('/r/new_category', data={'name': 'anoncat'})
    assert res.status_code == 302
    assert "login" in res.headers['Location']


def test_missing_report_returns_404(client, db):
    res = client.get('/r/report/99999')
    assert res.status_code == 404

    res = client.get('/r/report/99999/reader/')
    assert res.status_code == 404


def test_custom_404_page(client, db):
    res = client.get('/no/such/page')
    assert res.status_code == 404
    assert "返回首页" in res.data.decode('utf-8')


def test_like_unlike_counter_no_drift(authenticated_client, db):
    rc = ReportController()
    cat = rc.create_category("cat1", "Cat Desc", "testuser")
    rc.create_report(cat.id, "myreport", "testuser")
    rid = Report.query.filter_by(name="myreport").first().id

    # Double like only counts once
    authenticated_client.post(f'/r/report/{rid}/like')
    authenticated_client.post(f'/r/report/{rid}/like')
    assert int(rc.get_likes_cnt(rid)) == 1

    # Double unlike doesn't go negative
    authenticated_client.post(f'/r/report/{rid}/unlike')
    authenticated_client.post(f'/r/report/{rid}/unlike')
    assert int(rc.get_likes_cnt(rid)) == 0


def test_favorite_counter_no_drift(authenticated_client, db):
    rc = ReportController()
    cat = rc.create_category("cat1", "Cat Desc", "testuser")
    rc.create_report(cat.id, "myreport", "testuser")
    rid = Report.query.filter_by(name="myreport").first().id

    authenticated_client.post(f'/r/report/{rid}/add_favorite')
    authenticated_client.post(f'/r/report/{rid}/add_favorite')
    assert int(rc.get_favors(rid)) == 1

    authenticated_client.post(f'/r/report/{rid}/cancel_favorite')
    authenticated_client.post(f'/r/report/{rid}/cancel_favorite')
    assert int(rc.get_favors(rid)) == 0


def test_upload_flow(authenticated_client, app, db):
    rc = ReportController()
    cat = rc.create_category("cat1", "Cat Desc", "testuser")

    # Create a mock zip file
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('index.html', '<html><body>Uploaded Report HTML</body></html>')
        z.writestr('extra.html', '<html><body>Extra details</body></html>')
    
    zip_buffer.seek(0)
    
    # Post upload
    res = authenticated_client.post(
        f'/upload/process/{cat.id}',
        data={'filepond': (zip_buffer, 'my_new_report.zip')},
        content_type='multipart/form-data'
    )
    
    assert res.status_code == 200
    # Returns the UID (category_id/filename)
    assert f"{cat.id}/my_new_report.zip" in res.data.decode('utf-8')

    # Verify database report created
    reports = Report.query.filter_by(category_id=cat.id).all()
    assert len(reports) == 1
    assert reports[0].name == "my_new_report"

    # Verify files created in UPLOAD_DIR and DATA_DIR
    uploaded_zip = os.path.join(app.config['UPLOAD_DIR'], 'testuser', 'cat1', 'my_new_report.zip')
    extracted_html = os.path.join(app.config['DATA_DIR'], 'testuser', 'cat1', 'my_new_report', 'index.html')
    
    assert os.path.exists(uploaded_zip)
    assert os.path.exists(extracted_html)
    with open(extracted_html, 'r', encoding='utf-8') as f:
        assert "Uploaded Report HTML" in f.read()


def test_upload_preserves_chinese_report_filename(authenticated_client, app, db):
    rc = ReportController()
    cat = rc.create_category("cat1", "Cat Desc", "testuser")
    report_filename = "\u542b\u4e2d\u6587\u7684\u6218\u62a5.zip"
    report_name = "\u542b\u4e2d\u6587\u7684\u6218\u62a5"

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('index.html', '<html><body>Chinese Report HTML</body></html>')

    zip_buffer.seek(0)

    res = authenticated_client.post(
        f'/upload/process/{cat.id}',
        data={'filepond': (zip_buffer, report_filename)},
        content_type='multipart/form-data'
    )

    assert res.status_code == 200
    assert f"{cat.id}/{report_filename}" in res.data.decode('utf-8')

    reports = Report.query.filter_by(category_id=cat.id).all()
    assert len(reports) == 1
    assert reports[0].name == report_name

    uploaded_zip = os.path.join(app.config['UPLOAD_DIR'], 'testuser', 'cat1', report_filename)
    extracted_html = os.path.join(app.config['DATA_DIR'], 'testuser', 'cat1', report_name, 'index.html')

    assert os.path.exists(uploaded_zip)
    assert os.path.exists(extracted_html)
    with open(extracted_html, 'r', encoding='utf-8') as f:
        assert "Chinese Report HTML" in f.read()


def test_report_details_seo_meta(authenticated_client, db):
    rc = ReportController()
    cat = rc.create_category("cat1", "Cat Desc", "testuser")
    rc.create_report(cat.id, "myreport", "testuser")
    report = Report.query.filter_by(name="myreport").first()
    report.description = "[b]一次成功的副本[/b] 五人小队通关记录"
    db.session.commit()

    res = authenticated_client.get(f'/r/report/{report.id}')
    assert res.status_code == 200
    page = res.data.decode('utf-8')

    # meta description comes from the bbcode-stripped report description
    assert 'name="description"' in page
    assert '一次成功的副本' in page
    assert '[b]' not in page.split('name="description"')[1].split('>')[0]

    # OG tags + canonical
    assert 'property="og:title"' in page
    assert 'property="og:description"' in page
    assert 'property="og:url"' in page
    assert 'rel="canonical"' in page
    assert f'/r/report/{report.id}' in page


def test_report_details_seo_meta_without_description(authenticated_client, db):
    rc = ReportController()
    cat = rc.create_category("cat1", "Cat Desc", "testuser")
    rc.create_report(cat.id, "myreport", "testuser")
    report = Report.query.filter_by(name="myreport").first()

    res = authenticated_client.get(f'/r/report/{report.id}')
    assert res.status_code == 200
    page = res.data.decode('utf-8')
    # Falls back to an owner/title-based description instead of crashing
    assert 'name="description"' in page
    assert 'testuser 分享的 World of Dungeons 战报' in page


def test_sitemap_xml(client, db):
    from ohmywod.extensions import cache
    rc = ReportController()
    cat = rc.create_category("cat1", "Cat Desc", "someuser")
    rc.create_report(cat.id, "myreport", "someuser")
    report = Report.query.filter_by(name="myreport").first()

    # The sitemap is cached for an hour; session-scoped app means the
    # simple cache leaks across tests, so start from a clean slate.
    cache.delete("sitemap_xml")

    res = client.get('/sitemap.xml')
    assert res.status_code == 200
    assert res.mimetype == 'application/xml'
    body = res.data.decode('utf-8')
    assert '<urlset' in body
    assert f'/r/report/{report.id}' in body
    assert f'/r/category/{cat.id}' in body
    assert '<lastmod>' in body

    cache.delete("sitemap_xml")


def test_sitemap_excludes_deleted_reports(client, db):
    from ohmywod.extensions import cache
    rc = ReportController()
    cat = rc.create_category("cat1", "Cat Desc", "someuser")
    rc.create_report(cat.id, "myreport", "someuser")
    report = Report.query.filter_by(name="myreport").first()
    rid = report.id
    rc.delete_report(rid)

    cache.delete("sitemap_xml")

    res = client.get('/sitemap.xml')
    assert res.status_code == 200
    assert f'/r/report/{rid}' not in res.data.decode('utf-8')

    cache.delete("sitemap_xml")


def test_report_reader_has_tail_ad(authenticated_client, app, db):
    rc = ReportController()
    cat = rc.create_category("cat1", "Cat Desc", "testuser")
    rc.create_report(cat.id, "myreport", "testuser")
    report = Report.query.filter_by(name="myreport").first()

    report_dir = os.path.join(app.config['DATA_DIR'], 'testuser', 'cat1', 'myreport')
    os.makedirs(report_dir, exist_ok=True)
    with open(os.path.join(report_dir, 'index.html'), 'w', encoding='utf-8') as f:
        f.write("<html><body><div>Reader Content</div></body></html>")

    res = authenticated_client.get(f'/r/report/{report.id}/reader/')
    assert res.status_code == 200
    page = res.data.decode('utf-8')
    assert "Reader Content" in page
    # Content-tail ad unit is present and comes after the report content
    assert 'adsbygoogle' in page
    assert 'data-ad-slot="6513178276"' in page
    assert page.index('Reader Content') < page.index('reader-tail-ad')


def test_robots_txt_points_to_sitemap(client):
    res = client.get('/robots.txt')
    assert res.status_code == 200
    assert 'Sitemap:' in res.data.decode('utf-8')
    assert '/sitemap.xml' in res.data.decode('utf-8')
