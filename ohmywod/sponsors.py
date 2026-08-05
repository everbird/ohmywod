# -*- coding: utf-8 -*-
"""Merged thank-you wall: Afdian (auto) + manually maintained WeChat sponsors.

Scope is intentionally tiny (docs/wechat-manual-sponsors-plan.md). WeChat reward
codes are just QR images — the site gets no reliable server callback, payer
nickname, or order state — so integrating the WeChat merchant API is far more
maintenance than an interest project warrants. Instead, the (currently few)
WeChat-sourced sponsors are maintained by hand in the ``MANUAL_SPONSORS`` config
list, and this module merges them with the read-only Afdian wall for /thanks.

Privacy stays consistent with the Afdian wall (AFD-004): only ``display_name``
and ``source`` ever reach the template. The internal ``amount`` / ``sponsored_at``
maintenance fields never enter the display path, front-end shows no amount or
date, and ``visible: False`` entries are dropped. Malformed config fails soft —
bad entries are skipped so the page never 500s.
"""

from flask import current_app, has_app_context

from ohmywod import afdian
from ohmywod.afdian import ANONYMOUS_NAME, _canonical_text, _is_anonymous_request


# Source tags drive the per-channel icon on the thank-you wall. Afdian entries
# come from the cached read-only API; WeChat / Alipay entries are hand-maintained
# reward-code channels in MANUAL_SPONSORS.
SOURCE_AFDIAN = "afdian"
SOURCE_WECHAT = "wechat"
SOURCE_ALIPAY = "alipay"


def _manual_sponsors_config():
    """Raw ``MANUAL_SPONSORS`` list from Flask config, or ``[]`` when unset/inert."""
    if not has_app_context():
        return []
    raw = current_app.config.get("MANUAL_SPONSORS")
    if not isinstance(raw, (list, tuple)):
        return []
    return list(raw)


def _manual_display_name(value):
    """Same anonymization contract as the Afdian wall: blank / ``匿名`` -> anonymous."""
    text = _canonical_text(value)
    if not text or _is_anonymous_request(text):
        return ANONYMOUS_NAME
    return text


def _manual_source(value):
    """Normalize the configured source tag; unknown/blank falls back to WeChat."""
    text = _canonical_text(value)
    return text or SOURCE_WECHAT


def manual_sponsor_entries():
    """Display-ready manual sponsor entries: ``[{display_name, source}]``.

    Reads ``MANUAL_SPONSORS`` from config, drops ``visible is False`` rows,
    anonymizes blank/``匿名`` names, and deliberately omits the internal
    ``amount`` / ``sponsored_at`` maintenance fields so they can never reach the
    template. Non-dict / unparseable rows are skipped (fail-soft), never raised.
    """
    entries = []
    for item in _manual_sponsors_config():
        if not isinstance(item, dict):
            continue
        if item.get("visible") is False:
            continue
        entries.append({
            "display_name": _manual_display_name(item.get("display_name")),
            "source": _manual_source(item.get("source")),
        })
    return entries


def thanks_entries():
    """Unified thank-you wall entries across every channel: ``[{display_name, source}]``.

    Afdian sponsors first (tagged ``afdian``), then the manual WeChat list. Each
    entry carries only ``display_name`` and ``source`` — the source lets the
    template pick a per-channel icon. Afdian failures already degrade to
    last-good/empty inside :mod:`ohmywod.afdian`, so this never raises.
    """
    afdian_entries = [
        {"display_name": name, "source": SOURCE_AFDIAN}
        for name in afdian.sponsor_display_names()
    ]
    return afdian_entries + manual_sponsor_entries()
