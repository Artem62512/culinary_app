"""Add normalized product categories and searchable aliases.

Revision ID: 0002_product_catalog
Revises: 0001_single_owner
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_product_catalog"
down_revision = "0001_single_owner"
branch_labels = None
depends_on = None

CATEGORIES = [
    ("Овощи", "vegetables"),
    ("Фрукты и ягоды", "fruits-berries"),
    ("Мясо", "meat"),
    ("Птица", "poultry"),
    ("Рыба и морепродукты", "fish-seafood"),
    ("Молочные продукты", "dairy"),
    ("Яйца", "eggs"),
    ("Крупы и макаронные изделия", "grains-pasta"),
    ("Бобовые", "legumes"),
    ("Хлеб и выпечка", "bakery"),
    ("Орехи и семена", "nuts-seeds"),
    ("Соусы и специи", "sauces-spices"),
    ("Другое", "other"),
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "product_categories" not in tables:
        op.create_table(
            "product_categories",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(100), nullable=False, unique=True),
            sa.Column("slug", sa.String(100), nullable=False, unique=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_product_categories_slug", "product_categories", ["slug"], unique=False)

    if "product_aliases" not in tables:
        op.create_table(
            "product_aliases",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
            sa.Column("alias", sa.String(255), nullable=False),
            sa.Column("normalized_alias", sa.String(255), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("normalized_alias", name="uq_product_alias_normalized"),
        )
        op.create_index("ix_product_aliases_product_id", "product_aliases", ["product_id"], unique=False)
        op.create_index("ix_product_aliases_normalized_alias", "product_aliases", ["normalized_alias"], unique=False)

    product_columns = {c["name"] for c in inspector.get_columns("products")}
    if "category_id" not in product_columns:
        with op.batch_alter_table("products") as batch:
            batch.add_column(sa.Column("category_id", sa.Integer(), nullable=True))
            batch.create_foreign_key("fk_products_category_id_product_categories", "product_categories", ["category_id"], ["id"], ondelete="SET NULL")
        op.create_index("ix_products_category_id", "products", ["category_id"], unique=False)

    categories = bind.execute(sa.text("SELECT id, name, slug FROM product_categories")).mappings().all()
    existing_slugs = {row["slug"] for row in categories}
    for name, slug in CATEGORIES:
        if slug not in existing_slugs:
            bind.execute(sa.text("INSERT INTO product_categories (name, slug) VALUES (:name, :slug)"), {"name": name, "slug": slug})

    ids = {row["slug"]: row["id"] for row in bind.execute(sa.text("SELECT id, slug FROM product_categories")).mappings()}
    mapping = {
        "молоко": "dairy", "масло сливочное": "dairy", "сыр": "dairy",
        "яйцо": "eggs", "хлеб": "bakery", "курица": "poultry",
        "мука": "grains-pasta", "сахар": "other",
    }
    if "category_id" in {c["name"] for c in sa.inspect(bind).get_columns("products")}:
        rows = bind.execute(sa.text("SELECT id, category FROM products WHERE category_id IS NULL")).mappings().all()
        for row in rows:
            legacy = (row["category"] or "").strip().casefold().replace("ё", "е")
            slug = mapping.get(legacy, "other")
            bind.execute(sa.text("UPDATE products SET category_id=:category_id WHERE id=:id"), {"category_id": ids[slug], "id": row["id"]})


def downgrade() -> None:
    # Catalog data is user-editable; destructive downgrade is intentionally disabled.
    pass
