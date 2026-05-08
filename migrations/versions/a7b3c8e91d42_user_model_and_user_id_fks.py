"""auth foundation — User table + user_id FKs + admin seed

Revision ID: a7b3c8e91d42
Revises: 6481d85c2633
Create Date: 2026-05-08 00:00:00.000000

Adds the `user` table that backs Google sign-in, plus nullable `user_id` FKs
on `visit`, `generated_image`, `rating`, and `recommendation`. Also seeds
`is_admin=True` rows for every email in the ADMIN_EMAILS env var with a
`pending:<email>` placeholder google_sub — the OAuth callback claims the row
on the admin's first real sign-in by matching email + placeholder.
"""

import os
import secrets
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision = "a7b3c8e91d42"
down_revision = "6481d85c2633"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("google_sub", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("avatar_url", sa.String(length=500), nullable=True),
        sa.Column(
            "is_admin",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("terms_accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("storage_salt", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("google_sub"),
    )
    with op.batch_alter_table("user") as batch_op:
        batch_op.create_index("ix_user_google_sub", ["google_sub"], unique=False)

    with op.batch_alter_table("visit") as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_visit_user_id", "user", ["user_id"], ["id"])

    with op.batch_alter_table("generated_image") as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_generated_image_user_id", "user", ["user_id"], ["id"]
        )

    with op.batch_alter_table("rating") as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_rating_user_id", "user", ["user_id"], ["id"])

    with op.batch_alter_table("recommendation") as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_recommendation_user_id", "user", ["user_id"], ["id"]
        )

    _seed_admins_from_env()


def downgrade():
    with op.batch_alter_table("recommendation") as batch_op:
        batch_op.drop_constraint("fk_recommendation_user_id", type_="foreignkey")
        batch_op.drop_column("user_id")

    with op.batch_alter_table("rating") as batch_op:
        batch_op.drop_constraint("fk_rating_user_id", type_="foreignkey")
        batch_op.drop_column("user_id")

    with op.batch_alter_table("generated_image") as batch_op:
        batch_op.drop_constraint("fk_generated_image_user_id", type_="foreignkey")
        batch_op.drop_column("user_id")

    with op.batch_alter_table("visit") as batch_op:
        batch_op.drop_constraint("fk_visit_user_id", type_="foreignkey")
        batch_op.drop_column("user_id")

    with op.batch_alter_table("user") as batch_op:
        batch_op.drop_index("ix_user_google_sub")

    op.drop_table("user")


def _seed_admins_from_env():
    """Insert one `is_admin=True` row per email in the ADMIN_EMAILS env var.

    `google_sub` starts as `pending:<email>` and gets replaced on the admin's
    first real Google sign-in (see app/routes/auth.py).
    """
    raw = os.environ.get("ADMIN_EMAILS", "") or ""
    emails = [e.strip().lower() for e in raw.split(",") if e.strip()]
    if not emails:
        return

    user_t = sa.table(
        "user",
        sa.column("google_sub", sa.String),
        sa.column("email", sa.String),
        sa.column("is_admin", sa.Boolean),
        sa.column("storage_salt", sa.String),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    now = datetime.now(timezone.utc)
    op.bulk_insert(
        user_t,
        [
            {
                "google_sub": f"pending:{email}",
                "email": email,
                "is_admin": True,
                "storage_salt": secrets.token_hex(32),
                "created_at": now,
            }
            for email in emails
        ],
    )
