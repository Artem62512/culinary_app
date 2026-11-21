"""Idempotently seed universal products and aliases without overwriting user data."""
import re
import sys
import unicodedata
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models import Product, ProductAlias, ProductCategory
from app.services.catalog_seed_data import CATALOG_GROUPS


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold().replace("ё", "е")
    value = re.sub(r"[^\w]+", " ", value, flags=re.UNICODE)
    return " ".join(value.split())


def seed(db: Session) -> dict[str, int]:
    categories = {row.slug: row for row in db.query(ProductCategory).all()}
    required = {
        "vegetables": ("Овощи", "vegetables"),
        "fruits-berries": ("Фрукты и ягоды", "fruits-berries"),
        "meat": ("Мясо", "meat"),
        "poultry": ("Птица", "poultry"),
        "fish-seafood": ("Рыба и морепродукты", "fish-seafood"),
        "dairy": ("Молочные продукты", "dairy"),
        "eggs": ("Яйца", "eggs"),
        "grains-pasta": ("Крупы и макаронные изделия", "grains-pasta"),
        "legumes": ("Бобовые", "legumes"),
        "bakery": ("Хлеб и выпечка", "bakery"),
        "nuts-seeds": ("Орехи и семена", "nuts-seeds"),
        "sauces-spices": ("Соусы и специи", "sauces-spices"),
        "other": ("Другое", "other"),
    }
    for slug, (name, _) in required.items():
        if slug not in categories:
            category = ProductCategory(name=name, slug=slug)
            db.add(category)
            db.flush()
            categories[slug] = category

    existing_names: dict[str, Product] = {}
    for product in db.query(Product).all():
        normalized = normalize(product.name)
        if normalized:
            existing_names.setdefault(normalized, product)
        if product.normalized_name != normalized:
            product.normalized_name = normalized

    existing_aliases = {row.normalized_alias for row in db.query(ProductAlias).all()}
    alias_to_product_name = set(existing_names)
    inserted_products = 0
    inserted_aliases = 0

    for slug, groups in CATALOG_GROUPS.items():
        category = categories[slug]
        for base_name, variants, aliases in groups:
            names = [(base_name, "")]
            names.extend((f"{base_name} {variant}", variant) for variant in variants)
            base_product = None
            for name, variation in names:
                normalized = normalize(name)
                product = existing_names.get(normalized)
                if product is None:
                    product = Product(
                        name=name,
                        normalized_name=normalized,
                        category=category.name,
                        category_id=category.id,
                        base_name=base_name,
                        variation=variation or None,
                        attributes={"processing": variation} if variation else {},
                        status="active",
                        source="catalog_seed",
                        verified=False,
                        kbju_status="missing",
                    )
                    db.add(product)
                    db.flush()
                    existing_names[normalized] = product
                    alias_to_product_name.add(normalized)
                    inserted_products += 1
                if not variation:
                    base_product = product

            # Attach aliases only to the canonical base record; never reassign an existing alias.
            if base_product:
                for alias in aliases:
                    normalized_alias = normalize(alias)
                    if not normalized_alias or normalized_alias in existing_aliases or normalized_alias in alias_to_product_name:
                        continue
                    db.add(ProductAlias(
                        product_id=base_product.id,
                        alias=alias,
                        normalized_alias=normalized_alias,
                    ))
                    existing_aliases.add(normalized_alias)
                    inserted_aliases += 1

    db.commit()
    return {
        "products_added": inserted_products,
        "aliases_added": inserted_aliases,
        "products_total": db.query(Product).count(),
        "aliases_total": db.query(ProductAlias).count(),
        "categories_total": db.query(ProductCategory).count(),
    }


if __name__ == "__main__":
    with SessionLocal() as session:
        result = seed(session)
        for key, value in result.items():
            print(f"{key}: {value}")
