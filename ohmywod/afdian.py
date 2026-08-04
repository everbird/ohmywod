# -*- coding: utf-8 -*-
"""Read-only Afdian (爱发电) open-API client for the sponsor wall (AFD-002).

Scope is deliberately tiny: sign requests per Afdian's MD5 scheme and call the
read-only ``query-sponsor`` endpoint. No SQLite writes, no webhooks, no order
verification (docs/afdian-integration-plan.md §6). Uses only the stdlib so the
optional P2 sponsor wall adds no new dependency.

Credentials come from Flask config: ``AFDIAN_USER_ID`` (non-secret,
account-specific) and ``AFDIAN_TOKEN`` (secret, rendered from sops by the
ohmywod-ops app role). When either is absent the client stays inert — callers
get an empty list, never an exception, so an unconfigured/dev environment
degrades cleanly. The caching + failure-degradation policy lives one layer up
(AFD-003); this module only signs and fetches.

Signature scheme (Afdian open API):
    sign = md5(token + "params" + params + "ts" + ts + "user_id" + user_id)
where ``params`` is the exact JSON string sent in the request body and ``ts`` is
a unix second. This must be reconciled against the current Afdian docs when real
credentials are wired (plan AFD-002 "Review 关注").
"""

import hashlib
import json
import time
import urllib.error
import urllib.request

from flask import current_app, has_app_context


QUERY_SPONSOR_URL = "https://afdian.com/api/open/query-sponsor"
QUERY_ORDER_URL = "https://afdian.com/api/open/query-order"
DEFAULT_TIMEOUT = 5
# Upper bound so a bad total_page from the API can never loop forever.
MAX_PAGES = 20
# afdian.com sits behind Cloudflare, which returns HTTP 403 "error code: 1010"
# (browser-signature ban) to the default Python-urllib User-Agent. A normal
# browser UA is required for the API to answer at all — verified 2026-08-04.
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


class AfdianError(Exception):
    """Any failure talking to Afdian. Callers degrade; must never surface as 500."""


def _looks_configured(value):
    """A value is usable only if non-empty and not an unrendered secret placeholder."""
    return bool(value) and not str(value).startswith("<secret:")


def sign(token, params, ts, user_id):
    """Afdian request signature.

    ``md5(token + "params" + params + "ts" + str(ts) + "user_id" + user_id)``.
    Callers must never log the raw pre-image (it contains the token).
    """
    raw = "{token}params{params}ts{ts}user_id{user_id}".format(
        token=token, params=params, ts=ts, user_id=user_id
    )
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def query_sponsor(user_id, token, page=1, per_page=None, *, timeout=DEFAULT_TIMEOUT):
    """Call read-only ``query-sponsor`` for one page; return the parsed ``data`` dict.

    Raises :class:`AfdianError` on any network / HTTP / decode / API-level
    failure, deliberately without echoing the request body or token in the
    message.
    """
    inner = {"page": int(page)}
    if per_page is not None:
        inner["per_page"] = int(per_page)
    # Signed and sent must be byte-identical; build the params string once.
    params = json.dumps(inner, separators=(",", ":"), sort_keys=True)
    ts = int(time.time())
    body = json.dumps(
        {
            "user_id": user_id,
            "params": params,
            "ts": ts,
            "sign": sign(token, params, ts, user_id),
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        QUERY_SPONSOR_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            # Required: Cloudflare 1010-bans the default urllib UA (see USER_AGENT).
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        # Only the exception class name — its message could echo body/token.
        raise AfdianError("afdian request failed: {}".format(exc.__class__.__name__))
    except ValueError:
        # json.JSONDecodeError is a ValueError subclass.
        raise AfdianError("afdian response was not valid JSON")

    if payload.get("ec") != 200:
        # ``em`` is Afdian's human-readable message (no token); safe to surface.
        raise AfdianError(
            "afdian api error ec={} em={}".format(payload.get("ec"), payload.get("em"))
        )
    return payload.get("data") or {}


def query_order(user_id, token, page=1, per_page=None, *, timeout=DEFAULT_TIMEOUT):
    """Call read-only ``query-order`` for one page; return the parsed ``data`` dict.

    Afdian exposes sponsor-plan custom field answers on orders (verified
    2026-08-04: ``remark`` contains the thank-you display name), not on
    ``query-sponsor``. This stays read-only and uses the same failure contract as
    :func:`query_sponsor`.
    """
    inner = {"page": int(page)}
    if per_page is not None:
        inner["per_page"] = int(per_page)
    params = json.dumps(inner, separators=(",", ":"), sort_keys=True)
    ts = int(time.time())
    body = json.dumps(
        {
            "user_id": user_id,
            "params": params,
            "ts": ts,
            "sign": sign(token, params, ts, user_id),
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        QUERY_ORDER_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise AfdianError("afdian request failed: {}".format(exc.__class__.__name__))
    except ValueError:
        raise AfdianError("afdian response was not valid JSON")

    if payload.get("ec") != 200:
        raise AfdianError(
            "afdian api error ec={} em={}".format(payload.get("ec"), payload.get("em"))
        )
    return payload.get("data") or {}


def _credentials():
    """``(user_id, token)`` from Flask config, or ``(None, None)`` if unconfigured."""
    if not has_app_context():
        return None, None
    cfg = current_app.config
    user_id = cfg.get("AFDIAN_USER_ID")
    token = cfg.get("AFDIAN_TOKEN")
    if _looks_configured(user_id) and _looks_configured(token):
        return user_id, token
    return None, None


def is_configured():
    """True only when both credentials are present (prod after ops render)."""
    user_id, _ = _credentials()
    return user_id is not None


def fetch_all_sponsors(*, per_page=100, max_pages=MAX_PAGES, timeout=DEFAULT_TIMEOUT):
    """Fetch every sponsor page with the configured credentials.

    Returns Afdian's ``data['list']`` entries concatenated across pages, or ``[]``
    when unconfigured. Raises :class:`AfdianError` on transport/API failure so the
    cache layer (AFD-003) can choose to serve the last good cache or an empty
    wall. Bounded by ``max_pages``.
    """
    user_id, token = _credentials()
    if user_id is None:
        return []
    sponsors = []
    page = 1
    while page <= max_pages:
        data = query_sponsor(user_id, token, page=page, per_page=per_page, timeout=timeout)
        sponsors.extend(data.get("list") or [])
        total_page = data.get("total_page") or 1
        if page >= total_page:
            break
        page += 1
    return sponsors


def fetch_all_orders(*, per_page=100, max_pages=MAX_PAGES, timeout=DEFAULT_TIMEOUT):
    """Fetch every order page with the configured credentials, or ``[]`` if inert."""
    user_id, token = _credentials()
    if user_id is None:
        return []
    orders = []
    page = 1
    while page <= max_pages:
        data = query_order(user_id, token, page=page, per_page=per_page, timeout=timeout)
        orders.extend(data.get("list") or [])
        total_page = data.get("total_page") or 1
        if page >= total_page:
            break
        page += 1
    return orders


# --- Cache layer (AFD-003): Afdian is the single source of truth; Redis only
# caches. Never writes SQLite, never touches the litestream / DR chain. ---

# Fresh copy honours the display-freshness vs. source-load trade-off (default 1h,
# override with AFDIAN_CACHE_TTL). The "last good" copy lives much longer so a
# transient Afdian/Cloudflare failure degrades to the previous result instead of
# an empty wall.
DEFAULT_CACHE_TTL = 3600
LAST_GOOD_TTL = 7 * 24 * 3600
_FRESH_KEY = "afdian_sponsors_fresh"
_LAST_GOOD_KEY = "afdian_sponsors_last_good"
_ORDER_OVERRIDES_FRESH_KEY = "afdian_order_display_overrides_fresh"
_ORDER_OVERRIDES_LAST_GOOD_KEY = "afdian_order_display_overrides_last_good"


def get_sponsors():
    """Cached sponsor list for the wall; Afdian stays the only source of truth.

    Serves the fresh Redis copy on hit. On miss, pulls from Afdian and refreshes
    both the fresh (TTL) and last-good (long-lived) copies. If Afdian is
    unreachable or errors, degrades to the last-good copy, else an empty list —
    never raises, never blocks the page. Returns ``[]`` when unconfigured.
    """
    from ohmywod.extensions import cache_get, cache_set

    if not is_configured():
        return []

    cached = cache_get(_FRESH_KEY)
    if cached is not None:
        return cached

    ttl = DEFAULT_CACHE_TTL
    if has_app_context():
        ttl = current_app.config.get("AFDIAN_CACHE_TTL", DEFAULT_CACHE_TTL)

    try:
        sponsors = fetch_all_sponsors()
    except AfdianError as error:
        if has_app_context():
            current_app.logger.warning(
                "afdian sponsor refresh failed (%s); serving last-good cache",
                error.__class__.__name__,
            )
        last_good = cache_get(_LAST_GOOD_KEY)
        return last_good if last_good is not None else []

    cache_set(_FRESH_KEY, sponsors, timeout=ttl)
    cache_set(_LAST_GOOD_KEY, sponsors, timeout=LAST_GOOD_TTL)
    return sponsors


def _order_user_key(order):
    if not isinstance(order, dict):
        return None
    return order.get("user_private_id") or order.get("user_id")


def _order_thanks_display_value(order):
    custom = _extract_thanks_display_field(order)
    if custom is None and isinstance(order, dict) and "remark" in order:
        # Real query-order response stores the custom-field answer directly in
        # remark without the field label (verified with a 2026-08-04 test order).
        custom = order.get("remark")
    if custom is None:
        return None
    return _canonical_text(custom)


def _thanks_display_overrides_from_orders(orders):
    ordered = sorted(
        (order for order in orders if isinstance(order, dict)),
        key=lambda order: order.get("create_time") or 0,
        reverse=True,
    )
    overrides = {}
    for order in ordered:
        key = _order_user_key(order)
        if not key or key in overrides:
            continue
        value = _order_thanks_display_value(order)
        if value is not None:
            overrides[key] = value
    return overrides


def get_thanks_display_overrides():
    """Cached ``user_private_id/user_id -> custom thank-you display name`` map.

    ``query-sponsor`` tells us who is currently a sponsor; ``query-order`` carries
    the sponsor-plan custom answer in ``remark``. Cache only this minimal mapping,
    never full order records, so amounts/order IDs/addresses do not leak into the
    display cache.
    """
    from ohmywod.extensions import cache_get, cache_set

    if not is_configured():
        return {}

    cached = cache_get(_ORDER_OVERRIDES_FRESH_KEY)
    if cached is not None:
        return cached

    ttl = DEFAULT_CACHE_TTL
    if has_app_context():
        ttl = current_app.config.get("AFDIAN_CACHE_TTL", DEFAULT_CACHE_TTL)

    try:
        overrides = _thanks_display_overrides_from_orders(fetch_all_orders())
    except AfdianError as error:
        if has_app_context():
            current_app.logger.warning(
                "afdian order refresh failed (%s); serving last-good display overrides",
                error.__class__.__name__,
            )
        last_good = cache_get(_ORDER_OVERRIDES_LAST_GOOD_KEY)
        return last_good if last_good is not None else {}

    cache_set(_ORDER_OVERRIDES_FRESH_KEY, overrides, timeout=ttl)
    cache_set(_ORDER_OVERRIDES_LAST_GOOD_KEY, overrides, timeout=LAST_GOOD_TTL)
    return overrides


# --- Display mapping (AFD-004): privacy-first thank-you wall. ---

ANONYMOUS_NAME = "匿名支持者"
THANKS_DISPLAY_FIELD_LABEL = "致谢页显示名（可选）"
_THANKS_DISPLAY_FIELD_ALIASES = (
    THANKS_DISPLAY_FIELD_LABEL,
    "致谢页显示名",
    "致谢页留名",
    "赞助者致谢显示名",
)
_CUSTOM_FIELD_CONTAINERS = (
    "custom_fields",
    "custom_field",
    "custom_info",
    "custom_data",
    "custom_values",
    "fields",
    "answers",
    "form",
    "forms",
    "order",
    "orders",
    "latest_order",
    "last_order",
    "remark",
    "remarks",
    "custom_order_id",
)
_CUSTOM_FIELD_LABEL_KEYS = ("name", "label", "title", "key", "field", "field_name", "question")
_CUSTOM_FIELD_VALUE_KEYS = ("value", "val", "content", "answer", "text")
_ANONYMOUS_MARKERS = {"匿名", "anonymous", "anon"}


def _canonical_text(value):
    return str(value or "").strip().strip('"\'“”‘’')


def _canonical_field_label(value):
    label = _canonical_text(value)
    return (
        label.replace(" ", "")
        .replace("　", "")
        .replace("（可选）", "")
        .replace("(可选)", "")
    )


def _is_thanks_display_field(value):
    label = _canonical_field_label(value)
    return bool(label) and any(
        label == _canonical_field_label(alias) for alias in _THANKS_DISPLAY_FIELD_ALIASES
    )


def _is_anonymous_request(value):
    return _canonical_text(value).lower() in _ANONYMOUS_MARKERS


def _extract_thanks_field_from_text(value):
    text = _canonical_text(value)
    if not text:
        return None

    if text[0] in "[{":
        try:
            return _extract_thanks_display_field(json.loads(text))
        except ValueError:
            pass

    for line in text.splitlines():
        for alias in _THANKS_DISPLAY_FIELD_ALIASES:
            index = line.find(alias)
            if index == -1:
                continue
            answer = line[index + len(alias):].strip()
            return answer.lstrip(":：=- ").strip()
    return None


def _extract_thanks_display_field(node):
    """Best-effort extraction of the Afdian custom thank-you display field.

    Afdian's public ``query-sponsor`` docs only guarantee ``user.name``; custom
    sponsor-plan fields are not documented in that response. Keep this parser
    defensive: if the field is absent or shaped differently, callers fall back to
    the Afdian nickname instead of failing the thank-you page.
    """
    if isinstance(node, str):
        return _extract_thanks_field_from_text(node)
    if isinstance(node, list):
        for item in node:
            value = _extract_thanks_display_field(item)
            if value is not None:
                return value
        return None
    if not isinstance(node, dict):
        return None

    for key, value in node.items():
        if _is_thanks_display_field(key):
            return value

    labels = [node.get(key) for key in _CUSTOM_FIELD_LABEL_KEYS]
    if any(_is_thanks_display_field(label) for label in labels):
        for key in _CUSTOM_FIELD_VALUE_KEYS:
            if key in node:
                return node.get(key)
        return ""

    for key in _CUSTOM_FIELD_CONTAINERS:
        if key not in node:
            continue
        value = _extract_thanks_display_field(node[key])
        if value is not None:
            return value
    return None


def _sponsor_user_key(entry):
    if not isinstance(entry, dict):
        return None
    user = entry.get("user") if isinstance(entry, dict) else None
    if not isinstance(user, dict):
        user = {}
    return user.get("user_private_id") or user.get("user_id")


def _sponsor_display_name(entry, overrides=None):
    if not isinstance(entry, dict):
        return ANONYMOUS_NAME

    custom_name = _extract_thanks_display_field(entry)
    if custom_name is None and overrides:
        key = _sponsor_user_key(entry)
        if key in overrides:
            custom_name = overrides[key]
    if custom_name is not None:
        custom_name = _canonical_text(custom_name)
        if _is_anonymous_request(custom_name):
            return ANONYMOUS_NAME
        if custom_name:
            return custom_name

    user = entry.get("user") if isinstance(entry, dict) else None
    name = ((user or {}).get("name") or "").strip()
    return name or ANONYMOUS_NAME


def sponsor_display_names():
    """Display-ready sponsor names for the thank-you wall.

    Privacy-first per plan AFD-004 / SUP-006: show the sponsor-plan custom field
    ``致谢页显示名（可选）`` when Afdian exposes it; if it is blank, fall back to
    the Afdian nickname; if it is ``匿名`` or no usable name exists, show
    :data:`ANONYMOUS_NAME`. Never exposes amount, user_id, avatar, or order data.
    """
    overrides = get_thanks_display_overrides()
    return [_sponsor_display_name(entry, overrides=overrides) for entry in get_sponsors()]
