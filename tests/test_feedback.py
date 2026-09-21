# -*- coding: utf-8 -*-
"""FBK-001 / FBK-002: login-gated feedback with owner email notification."""

from ohmywod.extensions import mail
from ohmywod.mailer import send_feedback_notification
from ohmywod.models.feedback import Feedback
from ohmywod.views.frontend import FEEDBACK_MAX_LENGTH


def test_feedback_form_shows_current_user_and_forum_fallback(authenticated_client):
    res = authenticated_client.get('/feedback')
    assert res.status_code == 200
    page = res.data.decode('utf-8')
    assert 'testuser' in page
    # No free-text "your name" input any more.
    assert 'name="username"' not in page
    # Escape hatch for people who can't log in (plan principle 1.3 #3).
    assert '[post:16014199]' in page


def test_login_page_points_feedback_visitors_to_forum(client):
    res = client.get('/login?next=/feedback')
    assert res.status_code == 200
    assert '[post:16014199]' in res.data.decode('utf-8')
    # The hint is specific to the feedback redirect, not every login.
    res = client.get('/login')
    assert '[post:16014199]' not in res.data.decode('utf-8')


def test_submit_stores_login_username_and_notifies(app, authenticated_client):
    app.config['FEEDBACK_NOTIFY_TO'] = 'owner@example.com'
    try:
        with mail.record_messages() as outbox:
            res = authenticated_client.post('/feedback', data={
                # Any submitted username must be ignored in favour of the login.
                'username': 'Spoofed Name',
                'feedback': '  上传后中文文件名丢失了  ',
            })
        assert res.status_code == 200
        assert '反馈已提交' in res.data.decode('utf-8')

        rows = Feedback.query.all()
        assert len(rows) == 1
        assert rows[0].username == 'testuser'
        assert rows[0].content == '上传后中文文件名丢失了'

        assert len(outbox) == 1
        msg = outbox[0]
        assert msg.recipients == ['owner@example.com']
        assert 'testuser' in msg.subject
        assert 'testuser' in msg.body
        assert '上传后中文文件名丢失了' in msg.body
        assert '/admin/feedback/' in msg.body
    finally:
        app.config['FEEDBACK_NOTIFY_TO'] = ''


def test_submit_without_recipient_configured_still_succeeds(app, authenticated_client):
    app.config['FEEDBACK_NOTIFY_TO'] = ''
    with mail.record_messages() as outbox:
        res = authenticated_client.post('/feedback', data={'feedback': 'hi'})
    assert res.status_code == 200
    assert Feedback.query.count() == 1
    assert len(outbox) == 0


def test_submit_survives_mail_failure(app, authenticated_client, monkeypatch):
    # Best-effort: an SMTP blip must not 500 or lose the feedback.
    app.config['FEEDBACK_NOTIFY_TO'] = 'owner@example.com'
    try:
        def boom(msg):
            raise RuntimeError('smtp down')
        monkeypatch.setattr(mail, 'send', boom)
        res = authenticated_client.post('/feedback', data={'feedback': 'still stored'})
        assert res.status_code == 200
        assert '反馈已提交' in res.data.decode('utf-8')
        assert Feedback.query.count() == 1
    finally:
        app.config['FEEDBACK_NOTIFY_TO'] = ''


def test_submit_rejects_empty_and_oversized_content(authenticated_client):
    for bad in ['', '   ', 'x' * (FEEDBACK_MAX_LENGTH + 1)]:
        res = authenticated_client.post('/feedback', data={'feedback': bad})
        assert res.status_code == 200
        assert '反馈已提交' not in res.data.decode('utf-8')
    assert Feedback.query.count() == 0


def test_links_in_content_are_accepted(authenticated_client):
    # Decision 2026-09-21: being logged in is the gate; no link filtering.
    res = authenticated_client.post('/feedback', data={
        'feedback': 'https://wod.everbird.me/r/ 这个页面打不开',
    })
    assert res.status_code == 200
    assert '反馈已提交' in res.data.decode('utf-8')
    assert Feedback.query.count() == 1


def test_send_feedback_notification_never_raises(app, db, monkeypatch):
    app.config['FEEDBACK_NOTIFY_TO'] = 'owner@example.com'
    try:
        fb = Feedback(username='u', content='c')
        db.session.add(fb)
        db.session.commit()

        def boom(msg):
            raise RuntimeError('smtp down')
        monkeypatch.setattr(mail, 'send', boom)
        assert send_feedback_notification(fb) is False
    finally:
        app.config['FEEDBACK_NOTIFY_TO'] = ''
