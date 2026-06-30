# -*- coding: utf-8 -*-

from flask_paginate import Pagination, get_page_args

def paginate(query_func, *args, **kwargs):
    """
    Helper to automatically handle Flask pagination.
    `query_func` is a function/method that accepts (offset=offset, limit=per_page, **kwargs)
    and returns (items, total_count).
    """
    page, per_page, offset = get_page_args(
        page_parameter='page',
        per_page_parameter='per_page'
    )
    items, total = query_func(*args, offset=offset, limit=per_page, **kwargs)
    pagination = Pagination(
        page=page,
        per_page=per_page,
        total=total,
        css_framework='bootstrap5'
    )
    return items, pagination, page, per_page, total
