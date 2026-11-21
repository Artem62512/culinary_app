"""Merge package cart prices with editable universal prices.

Revision ID: 20261122_merge_cart_price_migrations
Revises: 20261121_product_editable_prices, 20261122_cart_package_prices
"""

revision = "20261122_merge_cart_price_migrations"
down_revision = (
    "20261121_product_editable_prices",
    "20261122_cart_package_prices",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
