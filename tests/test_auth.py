# -*- coding: utf-8 -*-

import base64
import hashlib

from ohmywod.models.user import User
from ohmywod.controllers.user import UserController
from ohmywod import security
from ohmywod.app import load_user


def _make_ssha(password, salt=b"saltsalt"):
    # Same shape as OpenLDAP {SSHA}: base64(sha1(password + salt) + salt).
    digest = hashlib.sha1(password.encode("utf-8") + salt).digest()
    return "{SSHA}" + base64.b64encode(digest + salt).decode("ascii")


def test_lazy_ssha_upgrade_on_login(db):
    # A user imported from LDAP carries an {SSHA} hash.
    u = User(username="ssha_user", display_name="S", email="s@example.com",
             password=_make_ssha("secret"))
    db.session.add(u)
    db.session.commit()
    assert u.password.startswith("{SSHA}")

    uc = UserController()
    assert uc.authenticate("ssha_user", "wrong") is None       # SSHA still verifies
    assert uc.authenticate("ssha_user", "secret") is not None  # success -> upgrade

    refreshed = uc.get_db_user("ssha_user")
    assert refreshed.password.startswith("$argon2")            # rehashed
    assert refreshed.password_updated_at is not None
    # Still works after the upgrade.
    assert uc.authenticate("ssha_user", "secret") is not None
    assert uc.authenticate("ssha_user", "secret2") is None


def test_load_user_by_id_and_rejects_legacy_dn(db):
    u = UserController().save("id_user", "I", "i@example.com", "pw")
    assert load_user(str(u.id)).id == u.id
    # Sessions minted before the cutover stored an LDAP DN -> logged out.
    assert load_user("cn=id_user,ou=users,dc=everbird,dc=me") is None
    assert load_user("not-an-int") is None
    assert load_user(None) is None


def test_register_creates_sqlite_user_and_can_login(client, db):
    res = client.post("/register", data={
        "username": "alice", "display_name": "Alice",
        "email": "alice@example.com",
        "password1": "alicepw", "password2": "alicepw",
    }, follow_redirects=True)
    assert res.status_code == 200

    user = UserController().get_db_user("alice")
    assert user is not None
    assert user.password.startswith("$argon2")  # hashed, never plaintext

    res = client.post("/login", data={
        "username": "alice", "password": "alicepw",
    }, follow_redirects=True)
    assert "/r/" in res.request.path


def test_profile_change_password(authenticated_client):
    # authenticated_client is logged in as testuser / password123.
    res = authenticated_client.post("/profile", data={
        "display_name": "Test User", "email": "test@example.com",
        "old_password": "password123",
        "new_password1": "brandnew", "new_password2": "brandnew",
    }, follow_redirects=True)
    assert "更新成功。" in res.data.decode("utf-8")

    uc = UserController()
    assert uc.authenticate("testuser", "brandnew") is not None
    assert uc.authenticate("testuser", "password123") is None


def test_profile_wrong_old_password_rejected(authenticated_client):
    res = authenticated_client.post("/profile", data={
        "display_name": "Test User", "email": "test@example.com",
        "old_password": "not-the-password",
        "new_password1": "brandnew", "new_password2": "brandnew",
    })
    assert "旧密码不匹配。" in res.data.decode("utf-8")
    # Password unchanged.
    assert UserController().authenticate("testuser", "password123") is not None


def test_set_password_cli(runner, register_user):
    register_user("cli_user", "C", "c@example.com", "oldpw")

    res = runner.invoke(args=["set-password", "cli_user"], input="newpw\nnewpw\n")
    assert res.exit_code == 0, res.output

    uc = UserController()
    assert uc.authenticate("cli_user", "newpw") is not None
    assert uc.authenticate("cli_user", "oldpw") is None

    # Unknown user exits non-zero.
    res2 = runner.invoke(args=["set-password", "ghost"], input="x\nx\n")
    assert res2.exit_code != 0


def test_password_never_stored_plaintext_on_register(client, db):
    client.post("/register", data={
        "username": "plaincheck", "display_name": "P",
        "email": "p@example.com",
        "password1": "supersecret", "password2": "supersecret",
    }, follow_redirects=True)
    user = UserController().get_db_user("plaincheck")
    assert user.password != "supersecret"
    assert user.password.startswith("$argon2")
    assert security.verify_password(user.password, "supersecret")
