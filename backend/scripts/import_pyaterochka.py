"""Import real Pyaterochka SKUs and prices for existing universal products.

This importer uses pyaterochka_api (an unofficial client) and may require
Camoufox browser assets. It deliberately uses exact normalized-name matches
and never guesses ambiguous universal-product associations.
"""
import asyncio
import html
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from human_requests import HumanContext, HumanPage
from pyaterochka_api import PyaterochkaAPI

from app.api.products import normalize_product_name
from app.core.database import SessionLocal
from app.models import Product, RecipeIngredient, StoreProduct, StoreProductPrice


PACKAGE_PATTERN = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(кг|г|мл|л|шт\.?)(?!\w)",
    re.IGNORECASE,
)


def extract_package(*values: object) -> tuple[float | None, str | None]:
    for value in values:
        if not value:
            continue
        text = html.unescape(str(value)).replace("\xa0", " ").strip()
        match = PACKAGE_PATTERN.search(text)
        if match:
            amount = float(match.group(1).replace(",", "."))
            unit = match.group(2).lower().rstrip(".")
            if unit in ("г", "грамм", "гр"):
                unit = "г"
            elif unit in ("кг",):
                unit = "кг"
            elif unit in ("мл",):
                unit = "мл"
            elif unit in ("л",):
                unit = "л"
            elif unit.startswith("шт"):
                unit = "шт"
            return amount, unit
    return None, None


def extract_current_price(item: dict) -> float | None:
    prices = item.get("prices") or {}
    for field in ("cpd_promo_price", "discount", "regular"):
        value = prices.get(field)
        if value not in (None, ""):
            try:
                price = float(str(value).replace(",", "."))
                if price > 0:
                    return price
            except (TypeError, ValueError):
                continue
    return None


def strip_package_text(name: str) -> str:
    text = html.unescape(name or "").replace("\xa0", " ").strip()
    text = re.sub(
        r",?\s*\d+(?:[.,]\d+)?\s*(?:кг|г|мл|л|шт\.?)(?!\w).*$",
        "",
        text,
        flags=re.IGNORECASE,
    )
    return re.sub(r"\s+", " ", text).strip(" ,")


def is_exact_universal_match(universal: Product, item: dict) -> bool:
    catalog_name = normalize_product_name(universal.name)
    stripped_name = normalize_product_name(strip_package_text(str(item.get("name") or "")))
    if catalog_name == stripped_name:
        return True

    if universal.base_name and universal.variation:
        candidate = normalize_product_name(
            f"{universal.base_name} {universal.variation}"
        )
        if candidate == stripped_name:
            return True
        base = normalize_product_name(universal.base_name)
        variation = normalize_product_name(universal.variation)
        if (
            base
            and variation
            and base in stripped_name
            and variation in stripped_name
        ):
            return True
    return False


async def import_products(
    limit: int = 20,
    offset: int = 0,
    batch_size: int | None = None,
) -> dict:
    inserted_skus = updated_skus = inserted_prices = 0
    searched_products = 0
    matched_products = 0
    unmatched_products = 0

    async with PyaterochkaAPI(headless=True) as api:
        # pyaterochka_api 0.2.2 and human_requests 0.2.2 need these wrappers
        # for the current Camoufox/Playwright combination.
        api.ctx.__class__ = HumanContext
        api.page.__class__ = HumanPage

        storage = await api.ctx.local_storage()
        origin_storage = storage.get("https://5ka.ru", {})
        import json
        delivery = json.loads(origin_storage.get("DeliveryPanelStore", "{}"))
        sap_code = delivery.get("selectedStore", {}).get("sapCode")
        region = (
            delivery.get("selectedAddress", {}).get("shopAddress")
            or delivery.get("selectedStore", {}).get("shopAddress")
        )
        if not sap_code:
            raise RuntimeError("Пятёрочка: не удалось определить SAP-код магазина")

        with SessionLocal() as db:
            query = (
                db.query(Product)
                .filter(Product.status == "active")
                .order_by(Product.id)
            )
            universals = query.offset(offset).limit(batch_size).all() if batch_size is not None else query.offset(offset).all()
            cache: dict[int, list[dict]] = {}

            for universal in universals:
                searched_products += 1
                query = universal.name
                response = await api.Catalog.search(
                    sap_code_store_id=sap_code,
                    query=query,
                    include_restrict=False,
                    limit=limit,
                )
                if response.status_code != 200:
                    unmatched_products += 1
                    continue
                payload = response.json()
                products = payload.get("products") or []
                cache[universal.id] = products

                exact_items = [
                    item for item in products
                    if item.get("is_available") is not False
                    and is_exact_universal_match(universal, item)
                ]
                if exact_items:
                    matched_products += 1
                else:
                    unmatched_products += 1
                print(
                    f"[{searched_products}/{len(universals)}] "
                    f"{universal.name}: найдено точных SKU {len(exact_items)}",
                    flush=True,
                )

                for item in exact_items:
                    plu = item.get("plu")
                    if plu is None:
                        continue
                    full_name = str(item.get("name") or "").strip()
                    if not full_name:
                        continue

                    amount, unit = extract_package(
                        item.get("property_clarification"),
                        item.get("package_quantity"),
                        full_name,
                    )
                    price = extract_current_price(item)
                    if price is None:
                        continue

                    source_id = f"pyaterochka:{plu}"
                    sku = (
                        db.query(StoreProduct)
                        .filter_by(source="pyaterochka", source_id=source_id)
                        .first()
                    )
                    if sku:
                        sku.name = full_name
                        sku.package_amount = amount
                        sku.package_unit = unit
                        sku.region = region
                        updated_skus += 1
                    else:
                        sku = StoreProduct(
                            universal_product_id=universal.id,
                            name=full_name,
                            manufacturer=None,
                            brand=None,
                            store_name="Пятёрочка",
                            package_amount=amount,
                            package_unit=unit,
                            barcode=None,
                            product_url=None,
                            region=region,
                            attributes={},
                            status="active",
                            source="pyaterochka",
                            source_id=source_id,
                        )
                        db.add(sku)
                        db.flush()
                        inserted_skus += 1

                    db.add(StoreProductPrice(
                        store_product_id=sku.id,
                        price=price,
                        currency="RUB",
                        region=region,
                        source="pyaterochka",
                    ))
                    inserted_prices += 1

                db.commit()

    return {
        "sap_code": sap_code,
        "catalog_products_searched": searched_products,
        "catalog_products_matched": matched_products,
        "catalog_products_unmatched": unmatched_products,
        "store_skus_inserted": inserted_skus,
        "store_skus_updated": updated_skus,
        "price_observations_inserted": inserted_prices,
    }


async def import_one_product(product_id: int, limit: int = 10) -> dict:
    """Refresh exact Pyaterochka offers for one universal catalog product."""
    inserted_skus = updated_skus = inserted_prices = 0

    async with PyaterochkaAPI(headless=True) as api:
        api.ctx.__class__ = HumanContext
        api.page.__class__ = HumanPage

        storage = await api.ctx.local_storage()
        origin_storage = storage.get("https://5ka.ru", {})
        import json
        delivery = json.loads(origin_storage.get("DeliveryPanelStore", "{}"))
        sap_code = delivery.get("selectedStore", {}).get("sapCode")
        region = (
            delivery.get("selectedAddress", {}).get("shopAddress")
            or delivery.get("selectedStore", {}).get("shopAddress")
        )
        if not sap_code:
            raise RuntimeError("Пятёрочка: не удалось определить SAP-код магазина")

        with SessionLocal() as db:
            universal = db.get(Product, product_id)
            if not universal or universal.status != "active":
                return {
                    "sap_code": sap_code,
                    "store_skus_inserted": 0,
                    "store_skus_updated": 0,
                    "price_observations_inserted": 0,
                }

            response = await api.Catalog.search(
                sap_code_store_id=sap_code,
                query=universal.name,
                include_restrict=False,
                limit=limit,
            )
            if response.status_code == 200:
                payload = response.json()
                exact_items = [
                    item for item in (payload.get("products") or [])
                    if item.get("is_available") is not False
                    and is_exact_universal_match(universal, item)
                ]

                for item in exact_items:
                    plu = item.get("plu")
                    full_name = str(item.get("name") or "").strip()
                    if plu is None or not full_name:
                        continue
                    amount, unit = extract_package(
                        item.get("property_clarification"),
                        item.get("package_quantity"),
                        full_name,
                    )
                    price = extract_current_price(item)
                    if price is None:
                        continue

                    source_id = f"pyaterochka:{plu}"
                    sku = (
                        db.query(StoreProduct)
                        .filter_by(source="pyaterochka", source_id=source_id)
                        .first()
                    )
                    if sku:
                        sku.name = full_name
                        sku.package_amount = amount
                        sku.package_unit = unit
                        sku.region = region
                        updated_skus += 1
                    else:
                        sku = StoreProduct(
                            universal_product_id=universal.id,
                            name=full_name,
                            manufacturer=None,
                            brand=None,
                            store_name="Пятёрочка",
                            package_amount=amount,
                            package_unit=unit,
                            barcode=None,
                            product_url=None,
                            region=region,
                            attributes={},
                            status="active",
                            source="pyaterochka",
                            source_id=source_id,
                        )
                        db.add(sku)
                        db.flush()
                        inserted_skus += 1

                    db.add(StoreProductPrice(
                        store_product_id=sku.id,
                        price=price,
                        currency="RUB",
                        region=region,
                        source="pyaterochka",
                    ))
                    inserted_prices += 1

                db.commit()

    return {
        "sap_code": sap_code,
        "store_skus_inserted": inserted_skus,
        "store_skus_updated": updated_skus,
        "price_observations_inserted": inserted_prices,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Импорт точных товаров и цен Пятёрочки")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--batch-size", type=int, default=None)
    args = parser.parse_args()
    print(
        asyncio.run(
            import_products(
                limit=args.limit,
                offset=args.offset,
                batch_size=args.batch_size,
            )
        )
    )
