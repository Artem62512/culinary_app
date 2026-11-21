"""Allow recipe-local ingredients and later product matching.

Revision ID: 0003_custom_ingredients
Revises: 0002_product_catalog
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_custom_ingredients"
down_revision = "0002_product_catalog"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("recipe_ingredients") as batch:
        batch.alter_column("product_id", existing_type=sa.Integer(), nullable=True)
        batch.add_column(sa.Column("custom_name", sa.String(255), nullable=True))
        batch.add_column(sa.Column("matching_status", sa.String(20), nullable=False, server_default="not_matched"))
        batch.add_column(sa.Column("matched_product_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_recipe_ingredients_matched_product", "products", ["matched_product_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_recipe_ingredients_matched_product_id", "recipe_ingredients", ["matched_product_id"], unique=False)
    op.execute("UPDATE recipe_ingredients SET matching_status='matched' WHERE product_id IS NOT NULL")


def downgrade() -> None:
    # Keep recipe-local ingredient data; destructive downgrade is intentionally disabled.
    pass
