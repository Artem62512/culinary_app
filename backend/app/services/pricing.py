"""Resolve the preferred usable RUB price for a universal product.

Rates are normalized to RUB/kg, RUB/liter, or RUB/piece. No conversions
between mass and volume are attempted.
"""
from sqlalchemy.orm import Session
from app.models import ProductPrice, StoreProduct, StoreProductPrice


STORE_PRIORITY = {
    "вкусвилл": 0,
    "vkusvill": 0,
    "яндекс лавка": 1,
    "лавка": 1,
    "yandex lavka": 1,
    "пятёрочка": 2,
    "пятерочка": 2,
    "pyaterochka": 2,
}

PACKAGE_UNITS = {
    "г": ("weight", 1.0),
    "гр": ("weight", 1.0),
    "g": ("weight", 1.0),
    "кг": ("weight", 1000.0),
    "kg": ("weight", 1000.0),
    "мл": ("volume", 1.0),
    "ml": ("volume", 1.0),
    "л": ("volume", 1000.0),
    "l": ("volume", 1000.0),
    "шт": ("pieces", 1.0),
    "шт.": ("pieces", 1.0),
    "pcs": ("pieces", 1.0),
    "pc": ("pieces", 1.0),
}


def _store_priority(store_name: str) -> int:
    return STORE_PRIORITY.get(store_name.strip().casefold(), 3)


def get_store_product_quote(db: Session, store_product_id: int) -> dict | None:
    store_product = db.get(StoreProduct, store_product_id)
    if not store_product or store_product.status != "active" or store_product.package_amount is None:
        return None
    package = PACKAGE_UNITS.get((store_product.package_unit or "").strip().casefold())
    if package is None:
        return None
    family, unit_factor = package
    base_amount = float(store_product.package_amount) * unit_factor
    if base_amount <= 0:
        return None
    price = (
        db.query(StoreProductPrice)
        .filter_by(store_product_id=store_product_id, currency="RUB")
        .filter(StoreProductPrice.price > 0)
        .order_by(StoreProductPrice.observed_at.desc())
        .first()
    )
    if not price:
        return None
    normalized_price = float(price.price) / base_amount
    return {
        "price_per_kg": normalized_price * 1000 if family == "weight" else None,
        "price_per_liter": normalized_price * 1000 if family == "volume" else None,
        "price_per_piece": normalized_price if family == "pieces" else None,
        "price_source": price.source,
        "observed_at": price.observed_at,
        "store_name": store_product.store_name,
        "store_product_id": store_product.id,
        "store_product_name": store_product.name,
        "manufacturer": store_product.manufacturer,
        "price_basis_unit": {"weight": "кг", "volume": "л", "pieces": "шт"}[family],
        "package_amount": float(store_product.package_amount),
        "package_unit": (store_product.package_unit or "").strip(),
        "package_price": float(price.price),
    }


def get_latest_price_quote(db: Session, universal_product_id: int) -> dict | None:
    candidates: list[tuple[int, object, dict]] = []

    legacy_rows = (
        db.query(ProductPrice)
        .filter_by(product_id=universal_product_id)
        .order_by(ProductPrice.updated_at.desc(), ProductPrice.id.desc())
        .all()
    )
    legacy_rates = {}
    legacy_seen = set()
    legacy_latest = None
    for legacy in legacy_rows:
        if legacy.updated_at and legacy_latest is None:
            legacy_latest = legacy.updated_at
        for field in ("price_per_kg", "price_per_liter", "price_per_piece"):
            value = getattr(legacy, field, None)
            if field in legacy_seen:
                continue
            if value is not None:
                legacy_seen.add(field)
                if value > 0:
                    legacy_rates[field] = float(value)
    if legacy_rates:
        candidates.append((4, legacy_latest or legacy_rows[0].updated_at, {
            "price_per_kg": legacy_rates.get("price_per_kg"),
            "price_per_liter": legacy_rates.get("price_per_liter"),
            "price_per_piece": legacy_rates.get("price_per_piece"),
            "price_source": "manual",
            "observed_at": legacy_latest,
            "store_name": None,
            "store_product_id": None,
            "store_product_name": None,
            "manufacturer": None,
            "price_basis_unit": (
                "кг" if legacy_rates.get("price_per_kg") is not None
                else "л" if legacy_rates.get("price_per_liter") is not None
                else "шт"
            ),
        }))

    store_prices = (
        db.query(StoreProductPrice, StoreProduct)
        .join(StoreProduct, StoreProduct.id == StoreProductPrice.store_product_id)
        .filter(
            StoreProduct.universal_product_id == universal_product_id,
            StoreProduct.status == "active",
            StoreProductPrice.currency == "RUB",
            StoreProductPrice.price > 0,
            StoreProduct.package_amount.isnot(None),
        )
        .order_by(StoreProductPrice.observed_at.desc())
        .all()
    )
    for price, store_product in store_prices:
        package = PACKAGE_UNITS.get((store_product.package_unit or "").strip().casefold())
        if package is None:
            continue
        family, unit_factor = package
        base_amount = float(store_product.package_amount) * unit_factor
        if base_amount <= 0:
            continue
        normalized_price = float(price.price) / base_amount
        quote = {
            "price_per_kg": normalized_price * 1000 if family == "weight" else None,
            "price_per_liter": normalized_price * 1000 if family == "volume" else None,
            "price_per_piece": normalized_price if family == "pieces" else None,
            "price_source": price.source,
            "observed_at": price.observed_at,
            "store_name": store_product.store_name,
            "store_product_id": store_product.id,
            "store_product_name": store_product.name,
            "manufacturer": store_product.manufacturer,
            "price_basis_unit": {"weight": "кг", "volume": "л", "pieces": "шт"}[family],
            "package_amount": float(store_product.package_amount),
            "package_unit": (store_product.package_unit or "").strip(),
            "package_price": float(price.price),
        }
        candidates.append((_store_priority(store_product.store_name), price.observed_at, quote))

    if not candidates:
        return None
    return min(candidates, key=lambda item: (item[0], -item[1].timestamp()))[2]


def get_latest_price_per_kg(db: Session, universal_product_id: int) -> float | None:
    quote = get_latest_price_quote(db, universal_product_id)
    return quote["price_per_kg"] if quote else None
