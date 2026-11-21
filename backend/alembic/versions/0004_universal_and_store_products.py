"""Separate universal ingredients from concrete store SKUs.

Revision ID: 0004_universal_store_products
Revises: 0003_custom_ingredients
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_universal_store_products"
down_revision = "0003_custom_ingredients"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    product_columns = {column["name"] for column in inspector.get_columns("products")}
    if "attributes" not in product_columns:
        with op.batch_alter_table("products") as batch:
            batch.add_column(sa.Column("attributes", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
    if "normalized_name" not in product_columns:
        with op.batch_alter_table("products") as batch:
            batch.add_column(sa.Column("normalized_name", sa.String(255), nullable=True))
        op.create_index("ix_products_normalized_name", "products", ["normalized_name"], unique=False)

    if "status" not in product_columns:
        with op.batch_alter_table("products") as batch:
            batch.add_column(sa.Column("status", sa.String(20), nullable=False, server_default="active"))
        op.create_index("ix_products_status", "products", ["status"], unique=False)

    tables = set(inspector.get_table_names())
    if "store_products" not in tables:
        op.create_table(
            "store_products",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("universal_product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("name", sa.String(500), nullable=False),
            sa.Column("manufacturer", sa.String(255), nullable=True),
            sa.Column("brand", sa.String(255), nullable=True),
            sa.Column("store_name", sa.String(120), nullable=False),
            sa.Column("package_amount", sa.Float(), nullable=True),
            sa.Column("package_unit", sa.String(20), nullable=True),
            sa.Column("barcode", sa.String(32), nullable=True),
            sa.Column("product_url", sa.String(1000), nullable=True),
            sa.Column("region", sa.String(120), nullable=True),
            sa.Column("attributes", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("status", sa.String(20), nullable=False, server_default="active"),
            sa.Column("source", sa.String(50), nullable=False, server_default="manual"),
            sa.Column("source_id", sa.String(120), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_store_products_universal_product_id", "store_products", ["universal_product_id"])
        op.create_index("ix_store_products_store_name", "store_products", ["store_name"])
        op.create_index("ix_store_products_barcode", "store_products", ["barcode"])
        op.create_index("ix_store_products_name", "store_products", ["name"])
        op.create_index("ix_store_products_status", "store_products", ["status"])

    if "store_product_prices" not in tables:
        op.create_table(
            "store_product_prices",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("store_product_id", sa.Integer(), sa.ForeignKey("store_products.id", ondelete="CASCADE"), nullable=False),
            sa.Column("price", sa.Float(), nullable=False),
            sa.Column("currency", sa.String(3), nullable=False, server_default="RUB"),
            sa.Column("region", sa.String(120), nullable=True),
            sa.Column("observed_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("source", sa.String(50), nullable=False, server_default="manual"),
        )
        op.create_index("ix_store_product_prices_store_product_id", "store_product_prices", ["store_product_id"])
        op.create_index("ix_store_product_prices_observed_at", "store_product_prices", ["observed_at"])


def downgrade() -> None:
    # Catalog data is user-owned. Destructive downgrade is intentionally disabled.
    pass
