# -*- coding: utf-8 -*-

import pytest
from ohmywod.controllers.user import UserController
from ohmywod.controllers.report import ReportController
from ohmywod.controllers.feedback import FeedbackController
from ohmywod.models.user import User
from ohmywod.models.report import Report, ReportCategory
from ohmywod.models.feedback import Feedback


def test_user_controller(db):
    uc = UserController()
    
    # Save a user
    res = uc.save("john", "John Doe", "john@example.com", "mypassword")
    assert res is True
    
    # Check SQL DB
    db_user = uc.get_db_user("john")
    assert db_user is not None
    assert db_user.display_name == "John Doe"
    assert db_user.email == "john@example.com"
    
    # Check LDAP User
    ldap_user = uc.get_ldap_user_by_username("john")
    assert ldap_user is not None
    assert ldap_user.username == "john"
    assert ldap_user.dn == "cn=john,ou=users,dc=everbird,dc=me"
    
    # Check get by email
    ldap_by_email = uc.get_ldap_user_by_email("john@example.com")
    assert ldap_by_email is not None
    assert ldap_by_email.username == "john"
    
    # Update user
    uc.update_user("john", display_name="John Updated", email="johnnew@example.com")
    
    db_user_updated = uc.get_db_user("john")
    assert db_user_updated.display_name == "John Updated"
    assert db_user_updated.email == "johnnew@example.com"
    
    ldap_user_updated = uc.get_ldap_user_by_username("john")
    # For MockLDAPConnection, modify updates entries.
    # LDAPUser gets attributes back. Let's make sure it doesn't throw.
    assert ldap_user_updated is not None


def test_report_controller(db):
    rc = ReportController()
    
    # Create category
    cat = rc.create_category("cat1", "Category 1", "john")
    assert cat.id is not None
    assert cat.name == "cat1"
    
    # Create report
    rc.create_report(cat.id, "report1", "john")
    
    # Get categories and reports
    cats = rc.get_cateogories_by_user("john")
    assert len(cats) == 1
    assert cats[0].name == "cat1"
    
    reps = rc.get_reports_by_user("john")
    assert len(reps) == 1
    assert reps[0].name == "report1"
    
    # Test Redis views stats
    r_id = reps[0].id
    assert rc.get_views(r_id) is None or int(rc.get_views(r_id)) == 0
    rc.incr_views(r_id)
    assert int(rc.get_views(r_id)) == 1
    
    # Test likes
    rc.like("john", r_id)
    likes = rc.get_likes("john")
    # Smembers returns set of bytes
    assert b"1" in likes or str(r_id).encode('utf-8') in likes
    
    rc.unlike("john", r_id)
    assert len(rc.get_likes("john")) == 0
    
    # Test Favorites
    favor = rc.add_favor("john", r_id)
    assert favor is not None
    assert rc.check_favor("john", r_id) is True
    
    fav_reports, total = rc.get_favorite_reports("john")
    assert total == 1
    assert fav_reports[0].id == r_id
    
    rc.cancel_favor("john", r_id)
    assert rc.check_favor("john", r_id) is False
    
    # Delete report
    rc.delete_report(r_id)
    assert reps[0].status == 1 # soft deleted
    
    # Delete category (should also mark reports under it as status=1)
    # Create new report to test cascade
    rc.create_report(cat.id, "report2", "john")
    reps_before = rc.get_reports_by_user("john")
    assert len(reps_before) == 1 # only report2, report1 is soft-deleted
    
    rc.delete_category(cat.id)
    assert cat.status == 1
    reps_after = rc.get_reports_by_user("john")
    assert len(reps_after) == 0


def test_feedback_controller(db):
    fc = FeedbackController()
    fb = fc.create_feedback("john", "This site is awesome!")
    
    assert fb.id is not None
    assert fb.username == "john"
    assert fb.content == "This site is awesome!"
    
    feedbacks = Feedback.query.all()
    assert len(feedbacks) == 1
    assert feedbacks[0].content == "This site is awesome!"


def test_report_controller_system_stats_and_latest(db):
    rc = ReportController()
    
    from ohmywod.controllers.user import UserController
    uc = UserController()
    uc.save("stats_john", "Stats John", "statsjohn@example.com", "password")
    
    cat = rc.create_category("stats_cat", "Category Stats", "stats_john")
    rc.create_report(cat.id, "report_latest_1", "stats_john")
    rc.create_report(cat.id, "report_latest_2", "stats_john")
    
    # Check stats
    stats = rc.get_system_stats()
    assert stats['users'] >= 1
    assert stats['categories'] >= 1
    assert stats['reports'] >= 2
    
    # Check latest reports
    latest = rc.get_latest_reports(limit=5)
    assert len(latest) >= 2
    assert latest[0].name in ["report_latest_1", "report_latest_2"]

