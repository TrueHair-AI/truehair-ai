"""add experiment session, rating, and consent tables

Revision ID: ae9086542a24
Revises: b7feb046b086
Create Date: 2026-04-13 12:07:11.892684

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "ae9086542a24"
down_revision = "85832af9eba3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "rating",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("generated_image_id", sa.Integer(), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("rating >= 1 AND rating <= 5", name="ck_rating_range"),
        sa.ForeignKeyConstraint(
            ["generated_image_id"],
            ["generated_image.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("generated_image_id"),
    )


def downgrade():
    op.drop_table("rating")
