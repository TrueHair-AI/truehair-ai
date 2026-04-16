"""add reference_image_id to GeneratedImage

Revision ID: 85832af9eba3
Revises: b7feb046b086
Create Date: 2026-04-13 11:30:02.438610

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision = "85832af9eba3"
down_revision = "b7feb046b086"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    columns = [col["name"] for col in inspector.get_columns("generated_image")]

    with op.batch_alter_table("generated_image", schema=None) as batch_op:
        if "reference_image_id" not in columns:
            batch_op.add_column(
                sa.Column("reference_image_id", sa.Integer(), nullable=True)
            )

        # Always safe to alter_column if it's already nullable, but let's check
        batch_op.alter_column("hairstyle_id", existing_type=sa.INTEGER(), nullable=True)

        # Check if the foreign key already exists
        fks = inspector.get_foreign_keys("generated_image")
        fk_names = [fk["name"] for fk in fks]
        if "fk_generated_image_reference_image_id" not in fk_names:
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
