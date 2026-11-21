"""Unify recipe ingredients with the product catalog.

Revision ID: 20261121_unified_recipe_products
Revises: dd49501a887f
Create Date: 2026-11-21
"""
import re
import unicodedata

from alembic import op
import sqlalchemy as sa

revision = "20261121_unified_recipe_products"
down_revision = "dd49501a887f"
branch_labels = None
depends_on = None


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold().replace("ё", "е")
    value = re.sub(r"[^\w]+", " ", value, flags=re.UNICODE)
    return " ".join(value.split())


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("recipe_ingredients")}
    required = {"product_id", "custom_name", "matched_product_id"}
    if not required.issubset(columns):
        raise RuntimeError(
            "Unified ingredient migration stopped; missing columns: "
            + ", ".join(sorted(required - columns))
        )

    # Build exact-name matches only. Aliases and fuzzy matches are deliberately
    # excluded: uncertain links must never be guessed during a data migration.
    product_rows = bind.execute(
        sa.text("SELECT id, name FROM products ORDER BY id")
    ).mappings().all()
    products_by_name = {}
    for row in product_rows:
        products_by_name.setdefault(_normalize(row["name"]), []).append(row["id"])

    other_category = bind.execute(
        sa.text("SELECT id, name FROM product_categories WHERE slug='other' LIMIT 1")
    ).mappings().first()
    category_id = other_category["id"] if other_category else None
    category_name = other_category["name"] if other_category else "Другое"

    ingredient_rows = bind.execute(
        sa.text("""
            SELECT id, product_id, custom_name
            FROM recipe_ingredients
            ORDER BY id
        """)
    ).mappings().all()

    unresolved = [
        row["id"] for row in ingredient_rows
        if row["product_id"] is None and not (row["custom_name"] or "").strip()
    ]
    if unresolved:
        raise RuntimeError(
            "Unified ingredient migration stopped; rows have neither product_id "
            "nor custom_name: " + ", ".join(map(str, unresolved))
        )

    for row in ingredient_rows:
        if row["product_id"] is not None:
            continue

        name = row["custom_name"].strip()
        normalized = _normalize(name)
        matches = products_by_name.get(normalized, [])

        if len(matches) > 1:
            raise RuntimeError(
                f"Ingredient {row['id']} ('{name}') matches multiple catalog products "
                f"by exact normalized name: {matches}. Resolve this manually first."
            )

        if len(matches) == 1:
            product_id = matches[0]
        else:
            result = bind.execute(
                sa.text("""
                    INSERT INTO products (
                        name, normalized_name, category, category_id,
                        base_name, variation, attributes, status,
                        calories, proteins, fats, carbs, kbju_status,
                        source, source_id, verified
                    ) VALUES (
                        :name, :normalized_name, :category, :category_id,
                        :base_name, NULL, '{}', 'active',
                        NULL, NULL, NULL, NULL, 'missing',
                        'manual', NULL, 0
                    )
                """),
                {
                    "name": name,
                    "normalized_name": normalized,
                    "category": category_name,
                    "category_id": category_id,
                    "base_name": name,
                },
            )
            product_id = result.lastrowid
            products_by_name.setdefault(normalized, []).append(product_id)

        # Ignore matched_product_id intentionally. The old match may be wrong;
        # the original ingredient name is the authoritative migration source.
        bind.execute(
            sa.text("UPDATE recipe_ingredients SET product_id=:product_id WHERE id=:id"),
            {"product_id": product_id, "id": row["id"]},
        )

    remaining = bind.execute(
        sa.text("SELECT id FROM recipe_ingredients WHERE product_id IS NULL")
    ).scalars().all()
    if remaining:
        raise RuntimeError(
            "Unified ingredient migration stopped; unresolved rows remain: "
            + ", ".join(map(str, remaining))
        )

    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("recipe_ingredients")}
    if "ix_recipe_ingredients_matched_product_id" in indexes:
        op.drop_index("ix_recipe_ingredients_matched_product_id", table_name="recipe_ingredients")

    foreign_keys = {
        fk.get("name")
        for fk in sa.inspect(bind).get_foreign_keys("recipe_ingredients")
    }
    with op.batch_alter_table("recipe_ingredients") as batch:
        if "fk_recipe_ingredients_matched_product" in foreign_keys:
            batch.drop_constraint("fk_recipe_ingredients_matched_product", type_="foreignkey")
        batch.alter_column(
            "product_id",
            existing_type=sa.Integer(),
            nullable=False,
        )
        batch.drop_column("custom_name")
        batch.drop_column("matching_status")
        batch.drop_column("matched_product_id")


def downgrade() -> None:
    # The migration creates catalog products and assigns recipe references.
    # A destructive reverse migration could lose ingredient names or merge intent.
    # Restore from a database backup instead of guessing how to split the entities.
    raise RuntimeError(
        "This data migration is intentionally irreversible. Restore the pre-migration database backup."
    )
