"""add error_log table for server-side error logging

Revision ID: e5f6a7b8c9d0
Revises: a7b3c8e91d42
Create Date: 2026-05-08 12:00:00.000000

Persists server-side errors (uncaught exceptions + view-caught exceptions
that called current_app.logger.error/.exception) so they survive Heroku's
~1-week log retention. See issue #17.
"""

import sqlalchemy as sa
from alembic import op

revision = "e5f6a7b8c9d0"
down_revision = "a7b3c8e91d42"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "error_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("route", sa.String(length=255), nullable=True),
        sa.Column("method", sa.String(length=10), nullable=True),
        sa.Column("exception_class", sa.String(length=255), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("traceback", sa.Text(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], name="fk_error_log_user_id"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("error_log") as batch_op:
        batch_op.create_index("ix_error_log_timestamp", ["timestamp"], unique=False)


def downgrade():
    with op.batch_alter_table("error_log") as batch_op:
        batch_op.drop_index("ix_error_log_timestamp")
    op.drop_table("error_log")
