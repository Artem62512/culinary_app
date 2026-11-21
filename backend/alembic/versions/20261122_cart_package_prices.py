"""Add package price overrides to shopping cart items.

Revision ID: 20261122_cart_package_prices
Revises: 20261121_cart_price_overrides
"""
from alembic import op
import sqlalchemy as sa

revision = "20261122_cart_package_prices"
down_revision = "20261121_cart_price_overrides"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("shopping_list_items")
    }
    if "package_price_override" not in columns:
        with op.batch_alter_table("shopping_list_items") as batch:
            batch.add_column(sa.Column("package_price_override", sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("shopping_list_items") as batch:
        batch.drop_column("package_price_override")
