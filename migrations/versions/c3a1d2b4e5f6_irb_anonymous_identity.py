"""IRB anonymous identity — replace user_id FKs with session_id strings, drop user table

Revision ID: c3a1d2b4e5f6
Revises: ae9086542a24
Create Date: 2026-04-19 00:00:00.000000

Per IRB Sections 2.1 and 6.5, the study must be fully anonymous. This migration:
  - Wipes existing rows in tables that reference `user` (pre-IRB-approval data).
  - Replaces `user_id` integer FKs with `session_id` VARCHAR(36) columns.
  - Drops the `user` table entirely.

Irreversible: downgrading past this revision cannot reconstruct PII, so
`downgrade()` is intentionally unimplemented.
"""

from alembic import op
import sqlalchemy as sa


revision = "c3a1d2b4e5f6"
down_revision = "ae9086542a24"
branch_labels = None
depends_on = None


def upgrade():
    # Wipe rows before schema change so NOT NULL session_id adds succeed.
    op.execute("DELETE FROM rating")
    op.execute("DELETE FROM recommendation")
    op.execute("DELETE FROM generated_image")
    op.execute("DELETE FROM user_image")
    op.execute("DELETE FROM consent")
    op.execute("DELETE FROM experiment_session")
    op.execute("DELETE FROM visit")

    with op.batch_alter_table("visit") as batch_op:
        batch_op.drop_column("user_id")
        batch_op.add_column(
            sa.Column("session_id", sa.String(length=36), nullable=True)
        )

    with op.batch_alter_table("experiment_session") as batch_op:
        batch_op.drop_column("user_id")
        batch_op.add_column(
            sa.Column("session_id", sa.String(length=36), nullable=False)
        )
        batch_op.create_index(
            "ix_experiment_session_session_id", ["session_id"], unique=False
        )

    with op.batch_alter_table("consent") as batch_op:
        batch_op.drop_column("user_id")
        batch_op.add_column(
            sa.Column("session_id", sa.String(length=36), nullable=False)
        )
        batch_op.create_unique_constraint("uq_consent_session_id", ["session_id"])

    with op.batch_alter_table("rating") as batch_op:
        batch_op.drop_column("user_id")
        batch_op.add_column(
            sa.Column("session_id", sa.String(length=36), nullable=False)
        )

    with op.batch_alter_table("generated_image") as batch_op:
        batch_op.drop_column("user_id")
        batch_op.add_column(
            sa.Column("session_id", sa.String(length=36), nullable=False)
        )

    with op.batch_alter_table("recommendation") as batch_op:
        batch_op.drop_column("user_id")
        batch_op.add_column(
            sa.Column("session_id", sa.String(length=36), nullable=False)
        )

    with op.batch_alter_table("user_image") as batch_op:
        batch_op.drop_column("user_id")
        batch_op.add_column(
            sa.Column("session_id", sa.String(length=36), nullable=False)
        )

    op.drop_table("user")


def downgrade():
    raise NotImplementedError(
        "Downgrading past the IRB anonymity migration is not supported: "
        "the `user` table's PII rows cannot be reconstructed."
    )
