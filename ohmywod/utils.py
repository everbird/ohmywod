# -*- coding: utf-8 -*-

from flask_paginate import Pagination, get_page_args

# A6: user-controlled ?per_page= must be bounded. Without a cap a request can
# ask for a huge page (unbounded query + template render); a negative value
# would even become SQLite `LIMIT -1` == no limit at all.
MAX_PER_PAGE = 100
DEFAULT_PER_PAGE = 10


def clamped_page_args():
    """`get_page_args()` with page/per_page clamped and offset recomputed.

    ``get_page_args`` derives ``offset = (page - 1) * per_page`` from the raw
    user input, so clamping ``per_page`` afterwards *must* recompute ``offset``
    or page 2+ silently uses the wrong slice.
    """
    page, per_page, _ = get_page_args(
        page_parameter='page',
        per_page_parameter='per_page'
    )
    page = max(1, page or 1)
    per_page = max(1, min(per_page or DEFAULT_PER_PAGE, MAX_PER_PAGE))
    offset = (page - 1) * per_page
    return page, per_page, offset


def paginate(query_func, *args, **kwargs):
    """
    Helper to automatically handle Flask pagination.
    `query_func` is a function/method that accepts (offset=offset, limit=per_page, **kwargs)
    and returns (items, total_count).
    """
    page, per_page, offset = clamped_page_args()
    items, total = query_func(*args, offset=offset, limit=per_page, **kwargs)
    pagination = Pagination(
        page=page,
        per_page=per_page,
        total=total,
        css_framework='bootstrap5'
    )
    return items, pagination, page, per_page, total


# A1: usernames and category names flow straight into filesystem paths
# (DATA_DIR/UPLOAD_DIR). A name that is absolute or contains "/" / ".." escapes
# the configured root (Path("/a") / "/tmp/x" -> "/tmp/x"). Reject anything that
# is not a single, safe path segment. Character validation is the first layer;
# upload.py also does a final resolve()-based containment check.
def is_safe_path_segment(value):
    """True iff ``value`` is usable as a single, contained path segment."""
    if not value:
        return False
    if value in (".", ".."):
        return False
    # Leading dot -> hidden/relative names; keep names on-disk predictable.
    if value.startswith("."):
        return False
    if "/" in value or "\\" in value:
        return False
    # Control chars (incl. NUL) and DEL have no place in a name.
    if any(ord(c) < 0x20 or ord(c) == 0x7f for c in value):
        return False
    # All-whitespace collapses to nothing useful on disk.
    if not value.strip():
        return False
    return True


def is_safe_next_url(target):
    """True iff ``target`` is a local, same-site relative path (A4).

    Flask-Login 0.6.3 ships no ``url_has_allowed_host_and_scheme`` helper, so we
    check by hand: accept only a single leading ``/``. Reject ``//host`` and
    ``/\\host`` — browsers treat both as protocol-relative -> off-site redirect.
    """
    return (
        bool(target)
        and target.startswith("/")
        and not target.startswith("//")
        and not target.startswith("/\\")
    )


def path_segment_validator(message="不能包含路径分隔符或以点开头（如 / \\ .. 等）。"):
    """WTForms validator wrapping :func:`is_safe_path_segment`."""
    from wtforms.validators import ValidationError

    def _validate(form, field):
        if field.data and not is_safe_path_segment(field.data):
            raise ValidationError(message)

    return _validate
