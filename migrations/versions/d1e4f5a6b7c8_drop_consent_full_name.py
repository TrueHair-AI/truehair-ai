"""Drop full_name column from Consent (IRB Section 6.3 — PII minimization)

Revision ID: d1e4f5a6b7c8
Revises: c3a1d2b4e5f6
Create Date: 2026-04-19 00:00:00.000000

IRB Section 6.3 specifies that the consent record stores only (a) the anonymous
session ID, (b) the experimental condition, and (c) the server-side consent
timestamp. The legacy `full_name` column was PII that contradicted the approved
protocol and is removed here.
"""

from alembic import op
import sqlalchemy as sa


revision = "d1e4f5a6b7c8"
down_revision = "c3a1d2b4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("consent") as batch_op:
        batch_op.drop_column("full_name")


def downgrade():
    with op.batch_alter_table("consent") as batch_op:
        batch_op.add_column(
            sa.Column(
                "full_name",
                sa.String(length=255),
                nullable=False,
                server_default="",
            )
        )
