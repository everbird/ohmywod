"""Responsive controls must not change queries or desktop pagination."""
from urllib.parse import parse_qs, urlsplit

import pytest
from flask import render_template
from flask_paginate import Pagination
from lxml import html

from ohmywod.models.favorite import Favorite
from ohmywod.models.report import Report, ReportCategory


@pytest.fixture
def paged_data(db):
    categories = [ReportCategory(name=f"pager-{i:02}", owner="testuser") for i in range(23)]
    db.session.add_all(categories)
    db.session.flush()
    reports = [Report(name=f"pagination-report-{i:02}", owner="testuser", category_id=categories[0].id)
               for i in range(23)]
    db.session.add_all(reports)
    db.session.flush()
    db.session.add_all([Favorite(ftype="report", username="testuser", report_id=r.id, status=0)
                        for r in reports])
    db.session.commit()
    return categories[0].id


def compact_forms(page):
    return page.xpath('//form[@class="pager-jump"]')


@pytest.mark.parametrize("route", ["all", "category", "search", "favorite"])
@pytest.mark.parametrize("number", [1, 2, 3])
def test_shared_pager_on_all_four_pages(authenticated_client, paged_data, route, number):
    routes = {
        "all": "/r/all",
        "category": f"/r/category/{paged_data}",
        "search": "/r/search?q=pagination-report",
        "favorite": "/r/favor",
    }
    path = routes[route]
    separator = "&" if "?" in path else "?"
    response = authenticated_client.get(f"{path}{separator}page={number}&per_page=10")
    assert response.status_code == 200
    if route == "category":
        # The owner upload widget must not turn page inputs into FilePonds.
        assert b'$("#mypond").filepond({' in response.data
        assert b'$("input").filepond({' not in response.data
    page = html.fromstring(response.data)
    forms = compact_forms(page)
    assert len(forms) == 2
    assert [f.getparent().getparent().get("data-pagination-position") for f in forms] == ["top", "bottom"]
    assert len(page.xpath('//div[contains(@class,"pagination-desktop")]')) == 1
    assert len(page.xpath('//script[@defer and contains(@src, "js/pagination.js?v=")]')) == 1
    ids = page.xpath('//*[@id]/@id')
    assert len(ids) == len(set(ids))
    for form in forms:
        assert form.get("method") == "GET"
        assert form.get("action") == urlsplit(path).path
        field = form.xpath('.//input[@name="page"]')[0]
        assert field.get("value") == str(number)
        assert field.get("min") == "1" and field.get("max") == "3"
        assert field.get("step") == "1" and field.get("type") == "number"
        assert field.get("inputmode") == "numeric" and field.get("enterkeyhint") == "go"
        assert field.get("required") is not None
        assert page.xpath(f'//label[@for="{field.get("id")}"]')
        assert page.xpath(f'//*[@id="{field.get("aria-describedby")}"]')
        nav = form.getparent()
        for label, delta in (("上一页", -1), ("下一页", 1)):
            control = nav.xpath(f'./*[@aria-label="{label}"]')[0]
            if 1 <= number + delta <= 3:
                assert control.tag == "a"
                target = urlsplit(control.get("href"))
                assert target.path == urlsplit(path).path
                args = parse_qs(target.query)
                assert args["page"] == [str(number + delta)]
                assert args["per_page"] == ["10"]
                if route == "search":
                    assert args["q"] == ["pagination-report"]
            else:
                assert control.tag == "span" and control.get("aria-disabled") == "true"
                assert control.get("href") is None


def test_jump_retains_repeated_and_escaped_query_parameters(client, paged_data):
    path = '/r/all?page=2&page=9&per_page=10&tag=a&tag=b&q=%E5%9C%B0%E5%9F%8E%26%22%3C&empty='
    page = html.fromstring(client.get(path).data)
    for form in compact_forms(page):
        hidden = [(n.get("name"), n.get("value")) for n in form.xpath('.//input[@type="hidden"]')]
        assert hidden == [("per_page", "10"), ("tag", "a"), ("tag", "b"), ("q", '地城&"<'), ("empty", "")]
        args = parse_qs(form.getparent().xpath('./a[@rel="next"]/@href')[0].split("?", 1)[1], keep_blank_values=True)
        assert args["tag"] == ["a", "b"]
        assert args["q"] == ['地城&"<'] and args["empty"] == [""]
        assert args["page"] == ["3"]
        assert len(form.xpath('.//input[@name="page"]')) == 1
        assert not form.xpath('.//script')
        submitted = hidden + [("page", "3")]
        result = html.fromstring(client.get(form.get("action"), query_string=submitted).data)
        assert compact_forms(result)[0].xpath('.//input[@name="page"]/@value') == ["3"]


def test_query_cannot_change_compact_route_or_form_target(client, paged_data):
    page = html.fromstring(client.get(f'/r/category/{paged_data}?page=2&per_page=10&_external=1&_scheme=evil&category_id=999').data)
    for form in compact_forms(page):
        assert form.get("action") == f"/r/category/{paged_data}"
        for link in form.getparent().xpath('./a'):
            parsed = urlsplit(link.get("href"))
            assert parsed.scheme == parsed.netloc == ""
            assert parsed.path == form.get("action")
            assert parse_qs(parsed.query)["category_id"] == ["999"]


@pytest.mark.parametrize("total", [0, 1, 10])
def test_single_or_empty_page_has_no_extra_controls(app, total):
    with app.test_request_context('/r/all'):
        pagination = Pagination(page=1, per_page=10, total=total, css_framework='bootstrap5')
        rendered = render_template('_pagination.html', pagination=pagination)
        assert "pager-jump" not in rendered and "pagination-desktop" not in rendered


def test_empty_routes_do_not_load_pager_script(authenticated_client):
    for path in ('/r/all', '/r/search?q=absent', '/r/favor'):
        page = html.fromstring(authenticated_client.get(path).data)
        assert not compact_forms(page)
        assert not page.xpath('//script[contains(@src,"js/pagination.js")]')


@pytest.mark.parametrize("number", [1, 29, 58])
def test_desktop_markup_keeps_original_numeric_links(app, number):
    with app.test_request_context(f'/r/all?page={number}&per_page=10&tag=a&tag=b'):
        pagination = Pagination(page=number, per_page=10, total=580, css_framework='bootstrap5')
        original = html.fromstring(str(pagination.links))
        rendered = html.fromstring(render_template('_pagination.html', pagination=pagination))
        desktop = rendered.xpath('.//div[contains(@class,"pagination-desktop")]')[0][0]
        assert html.tostring(desktop).strip() == html.tostring(original).strip()
        top = render_template('_pagination.html', pagination=pagination, pagination_position='top')
        assert 'pagination-desktop' not in top


def test_pager_resources_are_static_and_versioned(client):
    js = client.get('/static/js/pagination.js?v=test')
    css = client.get('/static/css/custom.css?v=test')
    assert js.status_code == css.status_code == 200
    script = js.get_data(as_text=True)
    assert 'input.select()' in script and 'input.reportValidity()' in script
    assert 'setCustomValidity' in script and 'pageshow' in script
    assert 'fetch(' not in script and 'window.location' not in script
    styles = css.get_data(as_text=True)
    assert '@container pager (max-width: 559.98px)' in styles
    assert '@supports (container-type: inline-size)' in styles
    assert '.pager-step' in styles and 'height: 44px' in styles
