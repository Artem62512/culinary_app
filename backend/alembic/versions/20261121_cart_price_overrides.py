"""Keep cart price edits separate and allow choosing a store offer.

Revision ID: 20261121_cart_price_overrides
Revises: 20261121_unified_recipe_products
"""
from alembic import op
import sqlalchemy as sa

revision = "20261121_cart_price_overrides"
down_revision = "20261121_unified_recipe_products"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("shopping_list_items")}
    with op.batch_alter_table("shopping_list_items") as batch:
        if "price_override" not in columns:
            batch.add_column(sa.Column("price_override", sa.Float(), nullable=True))
        if "selected_store_product_id" not in columns:
            batch.add_column(sa.Column(
                "selected_store_product_id",
                sa.Integer(),
                sa.ForeignKey(
                    "store_products.id",
                    ondelete="SET NULL",
                    name="fk_shopping_list_items_selected_store_product",
                ),
                nullable=True,
            ))


def downgrade() -> None:
    with op.batch_alter_table("shopping_list_items") as batch:
        batch.drop_column("selected_store_product_id")
        batch.drop_column("price_override")
