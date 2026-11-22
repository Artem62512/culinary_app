"""Allow manual conversion between package and recipe units in the cart.

Revision ID: 20261122_manual_cart_package_equivalence
Revises: 20261122_manual_cart_packages
"""
from alembic import op
import sqlalchemy as sa


revision = "20261122_manual_cart_package_equivalence"
down_revision = "20261122_manual_cart_packages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("shopping_list_items")
    }
    if "package_amount_in_recipe_unit_override" not in columns:
        with op.batch_alter_table("shopping_list_items") as batch:
            batch.add_column(
                sa.Column("package_amount_in_recipe_unit_override", sa.Float(), nullable=True)
            )


def downgrade() -> None:
    with op.batch_alter_table("shopping_list_items") as batch:
        batch.drop_column("package_amount_in_recipe_unit_override")
