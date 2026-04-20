"""Refactor image pipeline: remove UserImage, drop image references

Revision ID: f0e2aaf0c2c7
Revises: d1e4f5a6b7c8
Create Date: 2026-04-19 22:04:12.964568

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f0e2aaf0c2c7"
down_revision = "d1e4f5a6b7c8"
branch_labels = None
depends_on = None


def upgrade():
    # SQLite doesn't name FK constraints in the baseline schema, so drop_constraint
    # fails. On SQLite, batch_alter_table recreates the table and FKs to dropped
    # columns are discarded automatically.
    is_sqlite = op.get_bind().dialect.name == "sqlite"

    with op.batch_alter_table("generated_image", schema=None) as batch_op:
        if not is_sqlite:
            batch_op.drop_constraint(
                "fk_generated_image_reference_image_id", type_="foreignkey"
            )
            batch_op.drop_constraint(
                "generated_image_user_image_id_fkey", type_="foreignkey"
            )
        batch_op.drop_column("image_url")
        batch_op.drop_column("user_image_id")
        batch_op.drop_column("reference_image_id")

    with op.batch_alter_table("recommendation", schema=None) as batch_op:
        if not is_sqlite:
            batch_op.drop_constraint(
                "recommendation_user_image_id_fkey", type_="foreignkey"
            )
        batch_op.drop_column("user_image_id")

    op.drop_table("user_image")


def downgrade():
    op.create_table(
        "user_image",
        sa.Column("id", sa.INTEGER(), nullable=False),
        sa.Column("image_url", sa.VARCHAR(length=255), nullable=False),
        sa.Column("created_at", sa.DATETIME(), nullable=True),
        sa.Column("session_id", sa.VARCHAR(length=36), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    with op.batch_alter_table("recommendation", schema=None) as batch_op:
        batch_op.add_column(sa.Column("user_image_id", sa.INTEGER(), nullable=False))
        batch_op.create_foreign_key(
            "recommendation_user_image_id_fkey",
            "user_image",
            ["user_image_id"],
            ["id"],
        )

    with op.batch_alter_table("generated_image", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("reference_image_id", sa.INTEGER(), nullable=True)
        )
        batch_op.add_column(sa.Column("user_image_id", sa.INTEGER(), nullable=False))
        batch_op.add_column(
            sa.Column("image_url", sa.VARCHAR(length=255), nullable=False)
        )
        batch_op.create_foreign_key(
            "generated_image_user_image_id_fkey",
            "user_image",
            ["user_image_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_generated_image_reference_image_id",
            "user_image",
            ["reference_image_id"],
            ["id"],
        )
