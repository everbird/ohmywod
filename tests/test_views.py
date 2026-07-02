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
