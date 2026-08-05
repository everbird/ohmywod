# -*- coding: utf-8 -*-
"""Tests for the merged thank-you wall (WMS-001..003).

Covers the manual WeChat-sponsor config parsing (anonymization, hidden-row
filtering, amount/date never leaking, fail-soft on malformed rows), the merge
with the Afdian wall, and the /thanks page rendering per-source icons with XSS
escaping. No network is touched; the Afdian source is monkeypatched.
"""

import pytest

from ohmywod import afdian, sponsors


@pytest.fixture(autouse=True)
def _restore_manual_sponsors(app):
    # The app fixture is session-scoped, so config mutations would otherwise leak
    # into later tests (e.g. Afdian's empty-state /thanks test). Snapshot/restore.
    had = "MANUAL_SPONSORS" in app.config
    prev = app.config.get("MANUAL_SPONSORS")
    yield
    if had:
        app.config["MANUAL_SPONSORS"] = prev
    else:
        app.config.pop("MANUAL_SPONSORS", None)


def _set_manual(app, value):
    app.config["MANUAL_SPONSORS"] = value


def test_manual_entries_empty_when_unconfigured(app):
    with app.app_context():
        app.config.pop("MANUAL_SPONSORS", None)
        assert sponsors.manual_sponsor_entries() == []


def test_manual_entries_non_list_config_is_inert(app):
    with app.app_context():
        _set_manual(app, "not-a-list")
        assert sponsors.manual_sponsor_entries() == []


def test_manual_entries_maps_normal_hidden_anonymous_and_malformed(app):
    with app.app_context():
        _set_manual(app, [
            {"display_name": "某某", "source": "wechat", "visible": True},
            {"display_name": "  ", "source": "wechat"},          # blank -> anonymous
            {"display_name": "匿名", "source": "wechat"},          # marker -> anonymous
            {"display_name": "隐藏我", "source": "wechat", "visible": False},  # hidden
            "not-a-dict",                                          # malformed -> skipped
            {"source": "wechat"},                                 # no name -> anonymous
        ])
        assert sponsors.manual_sponsor_entries() == [
            {"display_name": "某某", "source": "wechat"},
            {"display_name": afdian.ANONYMOUS_NAME, "source": "wechat"},
            {"display_name": afdian.ANONYMOUS_NAME, "source": "wechat"},
            {"display_name": afdian.ANONYMOUS_NAME, "source": "wechat"},
        ]


def test_manual_entries_never_leak_amount_or_date(app):
    with app.app_context():
        _set_manual(app, [
            {"display_name": "某某", "source": "wechat",
             "amount": "20.00", "sponsored_at": "2026-08-05", "note": "内部备注"},
        ])
        entries = sponsors.manual_sponsor_entries()
        assert entries == [{"display_name": "某某", "source": "wechat"}]
        blob = repr(entries)
        assert "20.00" not in blob
        assert "2026-08-05" not in blob
        assert "内部备注" not in blob


def test_manual_entries_blank_source_defaults_to_wechat(app):
    with app.app_context():
        _set_manual(app, [{"display_name": "某某"}])
        assert sponsors.manual_sponsor_entries() == [
            {"display_name": "某某", "source": "wechat"},
        ]


def test_thanks_entries_merges_afdian_and_manual(app, monkeypatch):
    monkeypatch.setattr(afdian, "sponsor_display_names", lambda: ["Alice", "Bob"])
    with app.app_context():
        _set_manual(app, [{"display_name": "微信朋友", "source": "wechat"}])
        assert sponsors.thanks_entries() == [
            {"display_name": "Alice", "source": "afdian"},
            {"display_name": "Bob", "source": "afdian"},
            {"display_name": "微信朋友", "source": "wechat"},
        ]


def test_thanks_entries_afdian_only(app, monkeypatch):
    monkeypatch.setattr(afdian, "sponsor_display_names", lambda: ["Alice"])
    with app.app_context():
        app.config.pop("MANUAL_SPONSORS", None)
        assert sponsors.thanks_entries() == [
            {"display_name": "Alice", "source": "afdian"},
        ]


def test_thanks_entries_manual_only(app, monkeypatch):
    monkeypatch.setattr(afdian, "sponsor_display_names", lambda: [])
    with app.app_context():
        _set_manual(app, [{"display_name": "微信朋友", "source": "wechat"}])
        assert sponsors.thanks_entries() == [
            {"display_name": "微信朋友", "source": "wechat"},
        ]


def test_thanks_page_renders_source_icons(client, app, monkeypatch):
    monkeypatch.setattr(afdian, "sponsor_display_names", lambda: ["Alice"])
    _set_manual(app, [
        {"display_name": "微信朋友", "source": "wechat"},
        {"display_name": "支付宝朋友", "source": "alipay"},
    ])
    res = client.get("/thanks")
    assert res.status_code == 200
    body = res.get_data(as_text=True)
    assert "Alice" in body
    assert "微信朋友" in body
    assert "支付宝朋友" in body
    # Afdian mug icon and both reward-code QR icons present, colour-tagged by source.
    assert "fa-mug-hot sponsor-source-icon sponsor-icon--afdian" in body
    assert "fa-qrcode sponsor-source-icon sponsor-icon--wechat" in body
    assert "fa-qrcode sponsor-source-icon sponsor-icon--alipay" in body


def test_manual_entries_preserve_alipay_source(app):
    with app.app_context():
        _set_manual(app, [{"display_name": "某某", "source": "alipay"}])
        assert sponsors.manual_sponsor_entries() == [
            {"display_name": "某某", "source": "alipay"},
        ]


def test_thanks_page_escapes_manual_names(client, app, monkeypatch):
    # Config-sourced names must go through Jinja autoescape just like nicknames.
    monkeypatch.setattr(afdian, "sponsor_display_names", lambda: [])
    _set_manual(app, [{"display_name": "<script>x</script>", "source": "wechat"}])
    res = client.get("/thanks")
    assert res.status_code == 200
    body = res.get_data(as_text=True)
    assert "<script>x</script>" not in body
    assert "&lt;script&gt;" in body


def test_thanks_page_hides_amount_and_date(client, app, monkeypatch):
    monkeypatch.setattr(afdian, "sponsor_display_names", lambda: [])
    _set_manual(app, [
        {"display_name": "某某", "source": "wechat",
         "amount": "20.00", "sponsored_at": "2026-08-05"},
    ])
    res = client.get("/thanks")
    body = res.get_data(as_text=True)
    assert "某某" in body
    assert "20.00" not in body
    assert "2026-08-05" not in body
