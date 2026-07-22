# -*- coding: utf-8 -*-

from datetime import datetime
from ohmywod.models.user import User
from ohmywod.models.report import Report, ReportCategory, ReportDetails


def test_user_creation(db):
    user = User(username="testuser", display_name="Test User", email="test@example.com")
    db.session.add(user)
    db.session.commit()

    assert user.id is not None
    assert user.username == "testuser"
    assert user.display_name == "Test User"
    assert user.email == "test@example.com"
    assert isinstance(user.joined_at, datetime)
    # Flask-Login identity is the primary key (HA-008 session invalidation).
    assert user.get_id() == str(user.id)


def test_report_category_properties(db):
    category = ReportCategory(name="testcat", owner="testuser", display_name="Test Category", description="[b]bold description[/b]")
    db.session.add(category)
    db.session.commit()

    assert category.id is not None
    assert category.title == "Test Category"
    assert "<strong>bold description</strong>" in category.description_rendered
    assert category.is_deleted is not True

    # Fallback title
    category_no_disp = ReportCategory(name="testcat2", owner="testuser")
    db.session.add(category_no_disp)
    db.session.commit()
    assert category_no_disp.title == "testcat2"


def test_report_properties_and_relations(db):
    category = ReportCategory(name="testcat", owner="testuser")
    db.session.add(category)
    db.session.commit()

    report = Report(category_id=category.id, owner="testuser", name="test_report", display_name="Test Report", description="[i]italic[/i]")
    db.session.add(report)
    db.session.commit()

    assert report.id is not None
    assert report.title == "Test Report"
    assert "<em>italic</em>" in report.description_rendered
    assert report.is_deleted is not True
    assert report.category.id == category.id

    # Test display reports list under category
    assert len(category.display_reports) == 1
    assert category.display_reports_count == 1

    # Mark report deleted
    report.status = 1
    db.session.commit()
    assert report.is_deleted is True
    assert len(category.display_reports) == 0
    assert category.display_reports_count == 0
