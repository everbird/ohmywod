# -*- coding: utf-8 -*-

import base64
from datetime import datetime

from ohmywod.models.user import User
from ohmywod.ldif_import import (
    parse_ldif,
    extract_users,
    import_users,
    run_import,
)


def _b64(s):
    return base64.b64encode(s.encode("utf-8")).decode("ascii")


# Mirrors a real `slapcat -o ldif-wrap=no` shape: an OU and the LDAP admin role
# (both must be ignored), plus three inetOrgPerson accounts. Passwords and the
# unicode displayName come through as base64 (`::`) exactly like on prod.
SAMPLE_LDIF = f"""version: 1

dn: ou=users,dc=everbird,dc=me
objectClass: organizationalUnit
ou: users

dn: cn=admin,dc=everbird,dc=me
objectClass: simpleSecurityObject
objectClass: organizationalRole
cn: admin

dn: cn=john,ou=users,dc=everbird,dc=me
objectClass: inetOrgPerson
cn: john
sn: john
displayName: John Doe
mail: john@example.com
userPassword:: {_b64('{ssha}JOHNHASH')}
createTimestamp: 20230624033240Z

dn: cn=jane,ou=users,dc=everbird,dc=me
objectClass: inetOrgPerson
cn: jane
sn: jane
displayName: Jane
mail: jane@example.com
userPassword:: {_b64('{ssha}JANEHASH')}

dn: cn=ghost,ou=users,dc=everbird,dc=me
objectClass: inetOrgPerson
cn: ghost
sn: ghost
displayName:: {_b64('幽灵 用户')}
mail: ghost@example.com
userPassword:: {_b64('{ssha}GHOSTHASH')}
createTimestamp: 20220101000000Z
"""


def test_model_has_password_columns():
    cols = User.__table__.columns
    assert "password" in cols
    assert "password_updated_at" in cols


def test_parse_and_extract_filters_and_decodes():
    users = extract_users(parse_ldif(SAMPLE_LDIF))
    by_name = {u.username: u for u in users}

    # ou=users and cn=admin are not inetOrgPerson -> excluded.
    assert set(by_name) == {"john", "jane", "ghost"}

    assert by_name["john"].display_name == "John Doe"
    assert by_name["john"].email == "john@example.com"
    assert by_name["john"].password == "{ssha}JOHNHASH"
    assert by_name["john"].created_at == datetime(2023, 6, 24, 3, 32, 40)

    # base64-encoded unicode displayName is decoded.
    assert by_name["ghost"].display_name == "幽灵 用户"
    assert by_name["ghost"].created_at == datetime(2022, 1, 1, 0, 0, 0)


def test_parse_handles_line_folding():
    folded = (
        "dn: cn=wrap,ou=users,dc=everbird,dc=me\n"
        "objectClass: inetOrgPerson\n"
        "cn: wrap\n"
        "displayName: Hello \n"
        " World\n"
        "mail: wrap@example.com\n"
    )
    users = extract_users(parse_ldif(folded))
    assert len(users) == 1
    assert users[0].display_name == "Hello World"


def test_import_fills_missing_and_creates(db):
    # Existing SQLite rows: john has no password yet, jane already has one.
    db.session.add(User(username="john", display_name="John (db)",
                        email="john@example.com"))
    db.session.add(User(username="jane", display_name="Jane (db)",
                        email="jane@example.com", password="{ssha}OLDJANE"))
    db.session.commit()

    users = extract_users(parse_ldif(SAMPLE_LDIF))
    stats = import_users(db.session, users)

    assert stats["total"] == 3
    assert stats["created"] == 1
    assert stats["password_filled"] == 1
    assert stats["skipped_has_password"] == 1
    assert stats["password_overwritten"] == 0

    john = User.query.filter_by(username="john").first()
    assert john.password == "{ssha}JOHNHASH"
    # Existing identity fields are NOT clobbered by the import.
    assert john.display_name == "John (db)"

    jane = User.query.filter_by(username="jane").first()
    assert jane.password == "{ssha}OLDJANE"

    ghost = User.query.filter_by(username="ghost").first()
    assert ghost is not None
    assert ghost.password == "{ssha}GHOSTHASH"
    assert ghost.display_name == "幽灵 用户"
    assert ghost.email == "ghost@example.com"
    assert ghost.joined_at == datetime(2022, 1, 1, 0, 0, 0)


def test_import_force_overwrites_existing_password(db):
    db.session.add(User(username="jane", display_name="Jane",
                        email="jane@example.com", password="{ssha}OLDJANE"))
    db.session.commit()

    users = [u for u in extract_users(parse_ldif(SAMPLE_LDIF)) if u.username == "jane"]
    stats = import_users(db.session, users, force=True)

    assert stats["password_overwritten"] == 1
    assert stats["skipped_has_password"] == 0
    assert User.query.filter_by(username="jane").first().password == "{ssha}JANEHASH"


def test_import_is_idempotent(db):
    users = extract_users(parse_ldif(SAMPLE_LDIF))

    first = import_users(db.session, users)
    assert first["created"] == 3
    assert first["password_filled"] == 0  # all created rows carry the hash already

    second = import_users(db.session, users)
    assert second["created"] == 0
    assert second["password_filled"] == 0
    assert second["skipped_has_password"] == 3
    assert User.query.count() == 3


def test_dry_run_writes_nothing(db):
    users = extract_users(parse_ldif(SAMPLE_LDIF))
    stats = import_users(db.session, users, dry_run=True)

    assert stats["created"] == 3
    assert User.query.count() == 0


def test_cli_import_dry_run(tmp_path, runner, db):
    ldif_file = tmp_path / "users.ldif"
    ldif_file.write_text(SAMPLE_LDIF, encoding="utf-8")

    result = runner.invoke(args=[
        "import-ldap-users", "--ldif", str(ldif_file), "--dry-run"])

    assert result.exit_code == 0, result.output
    assert "DRY-RUN" in result.output
    assert "total: 3" in result.output
    assert User.query.count() == 0
