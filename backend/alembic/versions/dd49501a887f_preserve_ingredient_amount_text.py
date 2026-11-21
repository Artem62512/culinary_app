
"""preserve ingredient amount text

Revision ID: dd49501a887f
Revises: 0004_universal_store_products
Create Date: 2026-11-20 14:05:02.917227
"""

from alembic import op
import sqlalchemy as sa

revision = "dd49501a887f"
down_revision = "0004_universal_store_products"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "recipe_ingredients" not in inspector.get_table_names():
        raise RuntimeError("Table recipe_ingredients does not exist")

    columns = {
        column["name"]
        for column in inspector.get_columns("recipe_ingredients")
    }

    with op.batch_alter_table("recipe_ingredients") as batch:
        if "amount_text" not in columns:
            batch.add_column(
                sa.Column("amount_text", sa.String(length=100), nullable=True)
            )

        if "amount_is_exact" not in columns:
            batch.add_column(
                sa.Column(
                    "amount_is_exact",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.text("1"),
                )
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "recipe_ingredients" not in inspector.get_table_names():
        return

    columns = {
        column["name"]
        for column in inspector.get_columns("recipe_ingredients")
    }

    with op.batch_alter_table("recipe_ingredients") as batch:
        if "amount_is_exact" in columns:
            batch.drop_column("amount_is_exact")

        if "amount_text" in columns:
            batch.drop_column("amount_text")
