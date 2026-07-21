"""add password columns to user

Revision ID: 48a0963e9b77
Revises: 95c19a94006d
Create Date: 2026-07-21 03:32:34.495102

HA-008 slice 1: give the SQLite ``user`` table its own password truth so
authentication can move off LDAP. Adds two nullable columns and changes no
behaviour on its own -- login still goes through LDAP until a later slice.

  * ``password``            -- self-describing password hash. Holds the
                               ``{SSHA}`` value imported from LDAP, or an
                               ``$argon2id$`` hash once a later slice rehashes
                               on login / handles native registration.
  * ``password_updated_at`` -- when the hash was last set natively (NULL for
                               LDAP-imported rows whose real mtime is unknown).

Both columns are nullable so the upgrade is a pure additive, online-safe DDL and
the downgrade cleanly removes them (nothing depends on them yet in this slice).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '48a0963e9b77'
down_revision = '95c19a94006d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('password', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('password_updated_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('password_updated_at')
        batch_op.drop_column('password')
