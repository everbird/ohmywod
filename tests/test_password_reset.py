# -*- coding: utf-8 -*-

import time

from ohmywod.controllers.user import UserController
from ohmywod.extensions import mail
from ohmywod.tokens import generate_reset_token, verify_reset_token


def test_token_roundtrip(db):
    u = UserController().save("tok", "T", "tok@example.com", "pw")
    token = generate_reset_token(u)
    assert verify_reset_token(token).id == u.id


def test_token_rejects_tampered_and_garbage(db):
    u = UserController().save("tok2", "T", "tok2@example.com", "pw")
    token = generate_reset_token(u)
    assert verify_reset_token(token + "x") is None
    assert verify_reset_token("not-a-token") is None
    assert verify_reset_token(None) is None
    assert verify_reset_token("") is None


def test_token_expires(db):
    u = UserController().save("tok3", "T", "tok3@example.com", "pw")
    token = generate_reset_token(u)
    time.sleep(1)
    # A zero-second window makes any already-issued token expired.
    assert verify_reset_token(token, max_age=0) is None


def test_token_single_use_after_password_change(db):
    uc = UserController()
    u = uc.save("tok4", "T", "tok4@example.com", "oldpw")
    token = generate_reset_token(u)
    assert verify_reset_token(token) is not None
    # Changing the password re-hashes it, so the old link no longer validates.
    uc.set_password("tok4", "newpw")
    assert verify_reset_token(token) is None


def test_forgot_password_sends_mail_for_known_email(client, db):
    UserController().save("known", "K", "known@example.com", "pw")
    with mail.record_messages() as outbox:
        res = client.post("/forgot-password",
                          data={"email": "known@example.com"},
                          follow_redirects=True)
    assert res.status_code == 200
    assert len(outbox) == 1
    assert outbox[0].recipients == ["known@example.com"]
    assert "/reset-password/" in outbox[0].body


def test_forgot_password_silent_for_unknown_email(client, db):
    with mail.record_messages() as outbox:
        res = client.post("/forgot-password",
                          data={"email": "nobody@example.com"},
                          follow_redirects=True)
    # Same 200 + notice, but nothing is actually sent -> no enumeration.
    assert res.status_code == 200
    assert len(outbox) == 0


def test_reset_password_end_to_end(client, db):
    uc = UserController()
    uc.save("e2e", "E", "e2e@example.com", "oldpw")
    user = uc.get_db_user("e2e")
    token = generate_reset_token(user)

    res = client.post(f"/reset-password/{token}",
                      data={"password1": "brandnew", "password2": "brandnew"},
                      follow_redirects=True)
    assert res.status_code == 200
    # New password works, old one doesn't.
    assert uc.authenticate("e2e", "brandnew") is not None
    assert uc.authenticate("e2e", "oldpw") is None


def test_reset_password_invalid_token_redirects(client, db):
    res = client.get("/reset-password/bogus", follow_redirects=True)
    assert res.status_code == 200
    assert "无效或已过期" in res.get_data(as_text=True)
