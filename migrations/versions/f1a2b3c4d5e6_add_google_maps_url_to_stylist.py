"""add google_maps_url column to stylist

Revision ID: f1a2b3c4d5e6
Revises: e5f6a7b8c9d0
Create Date: 2026-05-08 14:00:00.000000

Stores a canonical Google Maps URL per stylist so the directory card can
render a Maps icon next to phone / email / website. Nullable — existing
rows are left empty until the seeder repopulates them.
"""

import sqlalchemy as sa
from alembic import op

revision = "f1a2b3c4d5e6"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("stylist") as batch_op:
        batch_op.add_column(
            sa.Column("google_maps_url", sa.String(length=500), nullable=True)
        )


def downgrade():
    with op.batch_alter_table("stylist") as batch_op:
        batch_op.drop_column("google_maps_url")
