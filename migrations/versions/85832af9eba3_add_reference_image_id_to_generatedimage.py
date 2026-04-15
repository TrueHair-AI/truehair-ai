"""add reference_image_id to GeneratedImage

Revision ID: 85832af9eba3
Revises: b7feb046b086
Create Date: 2026-04-13 11:30:02.438610

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "85832af9eba3"
down_revision = "b7feb046b086"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("generated_image", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("reference_image_id", sa.Integer(), nullable=True)
        )
        batch_op.alter_column("hairstyle_id", existing_type=sa.INTEGER(), nullable=True)
        batch_op.create_foreign_key(
            "fk_generated_image_reference_image_id",
            "user_image",
            ["reference_image_id"],
            ["id"],
        )


def downgrade():
    with op.batch_alter_table("generated_image", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_generated_image_reference_image_id", type_="foreignkey"
        )
        batch_op.alter_column(
            "hairstyle_id", existing_type=sa.INTEGER(), nullable=False
        )
        batch_op.drop_column("reference_image_id")
