# -*- coding: utf-8 -*-

from ohmywod.extensions import client_ip_key
from ohmywod.controllers.user import UserController


def test_client_ip_key_prefers_cf_header(app):
    with app.test_request_context(headers={"CF-Connecting-IP": "203.0.113.7"}):
        assert client_ip_key() == "203.0.113.7"
    with app.test_request_context(environ_base={"REMOTE_ADDR": "10.1.2.3"}):
        assert client_ip_key() == "10.1.2.3"


def test_login_is_rate_limited(client, register_user):
    register_user("rl_login", "RL", "rl_login@example.com", "pw")
    headers = {"CF-Connecting-IP": "198.51.100.11"}

    statuses = []
    for _ in range(8):
        res = client.post("/login", data={"username": "rl_login", "password": "bad"},
                          headers=headers)
        statuses.append(res.status_code)

    # Per-username limit is 6/min -> a 429 shows up within the first 8 tries.
    assert 429 in statuses
    # The 429 page renders (standalone template).
    res = client.post("/login", data={"username": "rl_login", "password": "bad"},
                      headers=headers)
    assert res.status_code == 429
    assert "429" in res.data.decode("utf-8")


def test_register_is_rate_limited(client, db):
    headers = {"CF-Connecting-IP": "198.51.100.22"}
    statuses = []
    for _ in range(7):
        # Invalid payload (no user created); the limiter counts the POST anyway.
        res = client.post("/register", data={"username": ""}, headers=headers)
        statuses.append(res.status_code)
    assert 429 in statuses  # limit is 5/min


def test_register_honeypot_silently_drops(client, db):
    # Limiter disabled by default here; isolates the honeypot behaviour.
    res = client.post("/register", data={
        "username": "spambot", "display_name": "Spam",
        "email": "spam@example.com",
        "password1": "pw", "password2": "pw",
        "website": "http://spam.example",   # honeypot filled
    }, follow_redirects=True)
    assert res.status_code == 200
    assert UserController().get_db_user("spambot") is None


def test_register_normal_still_works_with_honeypot_field(client, db):
    res = client.post("/register", data={
        "username": "realuser", "display_name": "Real",
        "email": "real@example.com",
        "password1": "pw", "password2": "pw",
        "website": "",   # humans leave it blank
    }, follow_redirects=True)
    assert res.status_code == 200
    assert UserController().get_db_user("realuser") is not None


def test_feedback_is_rate_limited(client, db):
    headers = {"CF-Connecting-IP": "198.51.100.33"}
    statuses = []
    for _ in range(7):
        res = client.post("/feedback", data={"username": "rl", "feedback": "hi"},
                          headers=headers)
        statuses.append(res.status_code)
    assert 429 in statuses  # feedback limit is 5/min


def test_interaction_like_is_rate_limited(authenticated_client):
    # Report blueprint is mounted at /r; report 999999 doesn't exist so the
    # handler returns a JSON "not found", but the limiter sits outside
    # @login_required and counts every POST regardless.
    headers = {"CF-Connecting-IP": "198.51.100.44"}
    statuses = []
    for _ in range(22):
        res = authenticated_client.post("/r/report/999999/like", headers=headers)
        statuses.append(res.status_code)
    assert 429 in statuses  # interaction limit is 20/min


def test_interaction_endpoint_not_limited_under_threshold(authenticated_client):
    # A handful of favorites from one client must not trip the limiter, so real
    # browsing isn't throttled.
    headers = {"CF-Connecting-IP": "198.51.100.55"}
    for _ in range(5):
        res = authenticated_client.post("/r/report/999999/add_favorite",
                                        headers=headers)
        assert res.status_code == 200
