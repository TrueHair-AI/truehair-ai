"""drop consent + experiment_session, tighten was_ai_recommended

Revision ID: d5e6f7a8b9c0
Revises: c2a3b4d5e6f7
Create Date: 2026-05-09 12:00:00.000000

Removes the IRB-era schema now that the experiment is over and the data
has been archived (issue #102): drop the `consent` and `experiment_session`
tables, then tighten `generated_image.was_ai_recommended` from nullable
to NOT NULL with a False default. Existing NULL rows are backfilled to
False before the column is altered so the constraint can be applied
cleanly.
"""

import sqlalchemy as sa
from alembic import op


revision = "d5e6f7a8b9c0"
down_revision = "c2a3b4d5e6f7"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table("consent")
    op.drop_table("experiment_session")

    # `false` literal (not `0`) so the backfill works on Postgres in addition
    # to SQLite — Postgres rejects integer literals into a boolean column.
    op.execute(
        sa.text(
            "UPDATE generated_image SET was_ai_recommended = false "
            "WHERE was_ai_recommended IS NULL"
        )
    )

    with op.batch_alter_table("generated_image") as batch_op:
        batch_op.alter_column(
            "was_ai_recommended",
            existing_type=sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        )


def downgrade():
    with op.batch_alter_table("generated_image") as batch_op:
        batch_op.alter_column(
            "was_ai_recommended",
            existing_type=sa.Boolean(),
            nullable=True,
            server_default=None,
        )

    op.create_table(
        "experiment_session",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("experiment_group", sa.String(length=20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_ping_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("experiment_session") as batch_op:
        batch_op.create_index(
            "ix_experiment_session_session_id", ["session_id"], unique=False
        )

    op.create_table(
        "consent",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("experiment_group", sa.String(length=20), nullable=False),
        sa.Column("consented_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", name="uq_consent_session_id"),
    )
