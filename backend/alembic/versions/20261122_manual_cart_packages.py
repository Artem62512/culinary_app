"""Allow manual package sizes and persistent cart price modes.

Revision ID: 20261122_manual_cart_packages
Revises: 20261122_merge_cart_price_migrations
"""
from alembic import op
import sqlalchemy as sa


revision = "20261122_manual_cart_packages"
down_revision = "20261122_merge_cart_price_migrations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("shopping_list_items")
    }
    with op.batch_alter_table("shopping_list_items") as batch:
        if "package_amount_override" not in columns:
            batch.add_column(sa.Column("package_amount_override", sa.Float(), nullable=True))
        if "package_unit_override" not in columns:
            batch.add_column(sa.Column("package_unit_override", sa.String(20), nullable=True))
        if "price_mode" not in columns:
            batch.add_column(sa.Column("price_mode", sa.String(20), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("shopping_list_items") as batch:
        batch.drop_column("price_mode")
        batch.drop_column("package_unit_override")
        batch.drop_column("package_amount_override")
