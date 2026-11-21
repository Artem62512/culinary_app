"""Add liter and piece rates to universal product price history.

Revision ID: 20261121_product_editable_prices
Revises: 20261121_cart_price_overrides
"""
from alembic import op
import sqlalchemy as sa

revision = "20261121_product_editable_prices"
down_revision = "20261121_cart_price_overrides"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("product_prices")}
    with op.batch_alter_table("product_prices") as batch:
        if "price_per_liter" not in columns:
            batch.add_column(sa.Column("price_per_liter", sa.Float(), nullable=True))
        if "price_per_piece" not in columns:
            batch.add_column(sa.Column("price_per_piece", sa.Float(), nullable=True))
        batch.alter_column("price", existing_type=sa.Float(), nullable=True)
        batch.alter_column("package_weight_g", existing_type=sa.Float(), nullable=True)
        batch.alter_column("price_per_kg", existing_type=sa.Float(), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("product_prices") as batch:
        batch.drop_column("price_per_piece")
        batch.drop_column("price_per_liter")
