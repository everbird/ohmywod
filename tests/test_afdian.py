# -*- coding: utf-8 -*-
"""Tests for the read-only Afdian client (AFD-002).

Covers the signing scheme against a fixed vector, the "unconfigured =>
inert/degrade" contract, pagination in fetch_all_sponsors, and error
translation in query_sponsor. No network is touched: query_sponsor's HTTP call
is monkeypatched.
"""

import json

import pytest

from ohmywod import afdian


def test_sign_matches_known_vector():
    # md5("tokparams{\"page\":1}ts1700000000user_iduid"), precomputed independently.
    assert afdian.sign("tok", '{"page":1}', 1700000000, "uid") == (
        "d4e2bbe317787782837638e5ba8ef5e4"
    )


def test_looks_configured_rejects_empty_and_placeholder():
    assert afdian._looks_configured("real-token") is True
    assert afdian._looks_configured("") is False
    assert afdian._looks_configured(None) is False
    # Unrendered sops placeholder must not be treated as a real credential.
    assert afdian._looks_configured("<secret:afdian_token>") is False


def test_unconfigured_without_app_context_returns_empty():
    # No Flask app context -> no credentials -> inert, never raises.
    assert afdian.is_configured() is False
    assert afdian.fetch_all_sponsors() == []


def test_credentials_read_from_config(app):
    with app.app_context():
        app.config["AFDIAN_USER_ID"] = "uid123"
        app.config["AFDIAN_TOKEN"] = "tok123"
        assert afdian.is_configured() is True
        assert afdian._credentials() == ("uid123", "tok123")

        # Empty token -> unconfigured again.
        app.config["AFDIAN_TOKEN"] = ""
        assert afdian.is_configured() is False


def test_query_sponsor_error_ec_raises_without_token(monkeypatch):
    def fake_urlopen(req, timeout=None):
        raise AssertionError("network must not be hit in this test")

    # ec != 200 path is exercised via a fake response object.
    class FakeResp:
        def __init__(self, payload):
            self._payload = json.dumps(payload).encode("utf-8")

        def read(self):
            return self._payload

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(
        afdian.urllib.request, "urlopen",
        lambda req, timeout=None: FakeResp({"ec": 400, "em": "bad request"}),
    )
    with pytest.raises(afdian.AfdianError) as exc:
        afdian.query_sponsor("uid", "super-secret-token")
    # The raised message must not leak the token.
    assert "super-secret-token" not in str(exc.value)


def test_query_sponsor_sends_browser_user_agent(monkeypatch):
    # afdian.com's Cloudflare 403-bans the default urllib UA; the request must
    # carry a browser-like User-Agent or every call fails in production.
    captured = {}

    class FakeResp:
        def read(self):
            return b'{"ec":200,"em":"ok","data":{"list":[]}}'

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=None):
        captured["ua"] = req.get_header("User-agent")
        return FakeResp()

    monkeypatch.setattr(afdian.urllib.request, "urlopen", fake_urlopen)
    afdian.query_sponsor("uid", "tok")
    assert captured["ua"] == afdian.USER_AGENT
    assert "urllib" not in (captured["ua"] or "").lower()


def test_query_sponsor_network_failure_translates(monkeypatch):
    import urllib.error

    def boom(req, timeout=None):
        raise urllib.error.URLError("connection refused to https://afdian...")

    monkeypatch.setattr(afdian.urllib.request, "urlopen", boom)
    with pytest.raises(afdian.AfdianError) as exc:
        afdian.query_sponsor("uid", "super-secret-token")
    assert "super-secret-token" not in str(exc.value)
    # Only the class name is surfaced, not the underlying message.
    assert "URLError" in str(exc.value)


def test_fetch_all_sponsors_paginates(app, monkeypatch):
    pages = {
        1: {"total_page": 2, "list": [{"user": {"name": "a"}}]},
        2: {"total_page": 2, "list": [{"user": {"name": "b"}}]},
    }

    def fake_query(user_id, token, page=1, per_page=None, timeout=None):
        assert (user_id, token) == ("uid123", "tok123")
        return pages[page]

    monkeypatch.setattr(afdian, "query_sponsor", fake_query)
    with app.app_context():
        app.config["AFDIAN_USER_ID"] = "uid123"
        app.config["AFDIAN_TOKEN"] = "tok123"
        sponsors = afdian.fetch_all_sponsors(per_page=100)
    assert [s["user"]["name"] for s in sponsors] == ["a", "b"]


def test_fetch_all_sponsors_respects_max_pages(app, monkeypatch):
    # total_page always claims more pages; max_pages must stop the loop.
    def endless(user_id, token, page=1, per_page=None, timeout=None):
        return {"total_page": 9999, "list": [{"user": {"name": str(page)}}]}

    monkeypatch.setattr(afdian, "query_sponsor", endless)
    with app.app_context():
        app.config["AFDIAN_USER_ID"] = "uid123"
        app.config["AFDIAN_TOKEN"] = "tok123"
        sponsors = afdian.fetch_all_sponsors(max_pages=3)
    assert len(sponsors) == 3


# --- AFD-003 cache layer ---

@pytest.fixture
def configured_app(app):
    from ohmywod.extensions import cache
    with app.app_context():
        app.config["AFDIAN_USER_ID"] = "uid123"
        app.config["AFDIAN_TOKEN"] = "tok123"
        cache.delete(afdian._FRESH_KEY)
        cache.delete(afdian._LAST_GOOD_KEY)
        yield app


def test_get_sponsors_unconfigured_returns_empty(app):
    with app.app_context():
        app.config["AFDIAN_USER_ID"] = ""
        app.config["AFDIAN_TOKEN"] = ""
        assert afdian.get_sponsors() == []


def test_get_sponsors_miss_then_hit(configured_app, monkeypatch):
    calls = {"n": 0}

    def one_fetch(**kwargs):
        calls["n"] += 1
        return [{"user": {"name": "a"}}]

    monkeypatch.setattr(afdian, "fetch_all_sponsors", one_fetch)
    with configured_app.app_context():
        first = afdian.get_sponsors()   # miss -> fetch + cache
        second = afdian.get_sponsors()  # hit -> no second fetch
    assert first == second == [{"user": {"name": "a"}}]
    assert calls["n"] == 1


def test_get_sponsors_degrades_to_last_good_on_failure(configured_app, monkeypatch):
    from ohmywod.extensions import cache

    # Seed a successful refresh, then force a failure and drop only the fresh key.
    monkeypatch.setattr(afdian, "fetch_all_sponsors", lambda **k: [{"user": {"name": "a"}}])
    with configured_app.app_context():
        afdian.get_sponsors()
        cache.delete(afdian._FRESH_KEY)  # fresh expired; last-good survives

        def boom(**k):
            raise afdian.AfdianError("afdian request failed: URLError")

        monkeypatch.setattr(afdian, "fetch_all_sponsors", boom)
        degraded = afdian.get_sponsors()
    assert degraded == [{"user": {"name": "a"}}]


def test_get_sponsors_failure_without_cache_returns_empty(configured_app, monkeypatch):
    def boom(**k):
        raise afdian.AfdianError("afdian request failed: URLError")

    monkeypatch.setattr(afdian, "fetch_all_sponsors", boom)
    with configured_app.app_context():
        assert afdian.get_sponsors() == []
