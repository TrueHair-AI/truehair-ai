"""add used_custom_reference column to generated_image

Revision ID: c2a3b4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-05-08 16:00:00.000000

Tracks whether a GeneratedImage row was produced from a user-uploaded
reference image instead of a catalog hairstyle. NOT NULL with a False
default so existing rows backfill cleanly. When True, hairstyle_id is
NULL — the two paths are mutually exclusive (catalog OR reference, not
both, per Sprint 6 planning).
"""

import sqlalchemy as sa
from alembic import op

revision = "c2a3b4d5e6f7"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("generated_image") as batch_op:
        batch_op.add_column(
            sa.Column(
                "used_custom_reference",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )


def downgrade():
    with op.batch_alter_table("generated_image") as batch_op:
        batch_op.drop_column("used_custom_reference")
