"""Import VkusVill SKUs as store products linked to universal recipe ingredients.

Legacy rows in ``products`` are left untouched for backwards compatibility.
"""
import sys
import re
import time
import html
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
from app.core.database import SessionLocal
from app.models import Product, ProductCategory, StoreProduct, StoreProductPrice
from app.api.products import normalize_product_name

MCP_URL = "https://mcp.vkusvill.ru/mcp"
HEADERS = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
CATEGORY_BY_QUERY = {
    "молоко": "dairy", "хлеб": "bakery", "яйцо": "eggs", "мука": "grains-pasta",
    "сахар": "other", "масло сливочное": "dairy", "сыр": "dairy", "курица": "poultry",
}


def call_tool(name: str, arguments: dict):
    payload = {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": name, "arguments": arguments}}
    with httpx.Client(timeout=30) as client:
        response = client.post(MCP_URL, json=payload, headers=HEADERS)
        if response.status_code != 200:
            print(f"  [error] {name}: status {response.status_code}")
            return None
        try:
            return json.loads(response.json()["result"]["content"][0]["text"])
        except (KeyError, IndexError, json.JSONDecodeError):
            return None


def clean_name(name: str) -> str:
    name = html.unescape(name or "")
    name = re.sub(r"<[^>]+>", "", name)
    return re.sub(r"\s+", " ", name).strip()


def parse_name(full_name: str) -> tuple[str, str | None]:
    """Return a useful generic base and a meaningful variant, excluding package size."""
    name = clean_name(full_name)
    without_pack = re.sub(r",?\s*\d+(?:[,.]\d+)?\s*(?:кг|г|мг|л|мл)\b.*$", "", name, flags=re.I).strip(" ,")
    fat = re.search(r"(\d+(?:[,.]\d+)?\s*%)", without_pack)
    if fat:
        base = (without_pack[:fat.start()] + without_pack[fat.end():]).strip(" ,")
        base = re.sub(r"\b(?:в бутылке|в пакете|в коробке|упаковка)\b", "", base, flags=re.I)
        base = re.sub(r"\s+(?:жирности|жирн\.?|до)\s*$", "", base, flags=re.I).strip()
        base = re.sub(r"\s+", " ", base)
        return base or without_pack, fat.group(1).replace(" ", "")
    parts = without_pack.split(",", 1)
    return parts[0].strip(), (parts[1].strip() if len(parts) > 1 and parts[1].strip() else None)


def parse_kbju(text: str) -> dict:
    result = {"proteins": None, "fats": None, "carbs": None, "calories": None}
    for field, pattern in {
        "proteins": r"белки\s+([\d.,]+)\s*г",
        "fats": r"жиры\s+([\d.,]+)\s*г",
        "carbs": r"углеводы\s+([\d.,]+)\s*г",
        "calories": r"([\d.,]+)\s*ккал",
    }.items():
        match = re.search(pattern, text or "", re.I)
        if match:
            result[field] = float(match.group(1).replace(",", "."))
    if any(value is None for value in (result["proteins"], result["fats"], result["carbs"])):
        gram_values = re.findall(r"([\d.,]+)\s*(?:г|гр\.?)(?![а-я])", text or "", re.I)
        if len(gram_values) < 3:
            gram_values = re.findall(r"(?<![\d.,])(\d+(?:[.,]\d+)?)", text or "")
        values = [float(value.replace(",", ".")) for value in gram_values[:3]]
        if len(values) >= 1 and result["proteins"] is None:
            result["proteins"] = values[0]
        if len(values) >= 2 and result["fats"] is None:
            result["fats"] = values[1]
        if len(values) >= 3 and result["carbs"] is None:
            result["carbs"] = values[2]
    return result


def extract_kbju(item: dict) -> dict:
    for prop in item.get("properties", []):
        if "Пищевая и энергетическая ценность" in prop.get("name", ""):
            return parse_kbju(prop.get("value", ""))
    return {"proteins": None, "fats": None, "carbs": None, "calories": None}


def extract_package(name: str) -> tuple[float | None, str | None]:
    name = html.unescape(clean_name(name)).replace("\xa0", " ")
    match = re.search(r"(\d+(?:[,.]\d+)?)\s*(кг|г|мл|л|шт\.?)(?!\w)", name, re.I)
    if not match:
        return None, None
    unit = match.group(2).lower().rstrip(".")
    return float(match.group(1).replace(",", ".")), unit


def import_products(queries: list[str], max_pages: int = 1):
    inserted_skus = inserted_universal = updated_skus = 0
    with SessionLocal() as db:
        categories = {row.slug: row for row in db.query(ProductCategory).all()}
        for query in queries:
            print(f"\n=== Query: {query} ===")
            for page in range(1, max_pages + 1):
                data = call_tool("vkusvill_products_search", {"q": query, "page": page})
                if not data or not data.get("ok"):
                    print(f"  page {page}: no data")
                    break
                items = data.get("data", {}).get("items", [])
                if not items:
                    break
                for item in items:
                    source_id = str(item.get("id") or "")
                    if not source_id:
                        continue
                    source_id = f"vkusvill:{source_id}"
                    full_name = clean_name(item.get("name", ""))
                    if not full_name:
                        continue
                    base_name, variation = parse_name(full_name)
                    universal_name = f"{base_name} {variation}".strip() if variation else base_name
                    normalized = normalize_product_name(universal_name)

                    sku = db.query(StoreProduct).filter_by(source="vkusvill", source_id=source_id).first()
                    if sku:
                        sku.name = full_name
                        sku.manufacturer = item.get("manufacturer") or sku.manufacturer
                        sku.brand = item.get("brand") or sku.brand
                        sku.product_url = item.get("url") or item.get("link") or sku.product_url
                        sku.region = item.get("region") or sku.region
                        amount, unit = extract_package(full_name)
                        sku.package_amount = amount or sku.package_amount
                        sku.package_unit = unit or sku.package_unit
                        updated_skus += 1
                    else:
                        category_slug = CATEGORY_BY_QUERY.get(query.casefold(), "other")
                        category = categories.get(category_slug) or categories.get("other")
                        universal = db.query(Product).filter(Product.normalized_name == normalized).first()
                        if not universal:
                            normalized_base = normalize_product_name(base_name)
                            normalized_variation = normalize_product_name(variation or "")
                            if normalized_base and normalized_variation:
                                universal = next(
                                    (
                                        candidate for candidate in db.query(Product).filter(Product.status == "active").all()
                                        if candidate.base_name
                                        and candidate.variation
                                        and normalize_product_name(candidate.base_name) == normalized_base
                                        and normalize_product_name(candidate.variation) == normalized_variation
                                    ),
                                    None,
                                )
                        kbju = extract_kbju(item)
                        if not universal:
                            universal = Product(
                                name=universal_name,
                                normalized_name=normalized,
                                base_name=base_name,
                                variation=variation,
                                category=category.name if category else None,
                                category_id=category.id if category else None,
                                attributes={"fat_percent": variation} if variation and "%" in variation else {},
                                calories=kbju["calories"], proteins=kbju["proteins"],
                                fats=kbju["fats"], carbs=kbju["carbs"],
                                kbju_status="full" if all(v is not None for v in kbju.values()) else "partial" if any(v is not None for v in kbju.values()) else "missing",
                                source="vkusvill_nutrition", verified=all(v is not None for v in kbju.values()),
                            )
                            db.add(universal)
                            db.flush()
                            inserted_universal += 1
                        else:
                            for field, value in kbju.items():
                                if getattr(universal, field) is None and value is not None:
                                    setattr(universal, field, value)
                            vals = [universal.calories, universal.proteins, universal.fats, universal.carbs]
                            universal.kbju_status = "full" if all(v is not None for v in vals) else "partial" if any(v is not None for v in vals) else "missing"

                        amount, unit = extract_package(full_name)
                        sku = StoreProduct(
                            universal_product_id=universal.id,
                            name=full_name,
                            manufacturer=item.get("manufacturer"),
                            brand=item.get("brand"),
                            store_name="ВкусВилл",
                            package_amount=amount,
                            package_unit=unit,
                            barcode=str(item.get("barcode")) if item.get("barcode") else None,
                            product_url=item.get("url") or item.get("link"),
                            region=item.get("region"),
                            attributes={},
                            source="vkusvill",
                            source_id=source_id,
                        )
                        db.add(sku)
                        db.flush()
                        inserted_skus += 1
                    price_data = item.get("price")
                    price_value = None
                    if isinstance(price_data, dict):
                        price_value = price_data.get("current")
                    elif isinstance(price_data, (int, float)):
                        price_value = price_data
                    try:
                        price_value = float(str(price_value).replace(",", ".")) if price_value is not None else None
                    except ValueError:
                        price_value = None
                    if price_value and price_value > 0:
                        db.add(StoreProductPrice(
                            store_product_id=sku.id,
                            price=price_value,
                            currency="RUB",
                            region=item.get("region"),
                            source="vkusvill",
                        ))

                db.commit()
                print(f"  page {page}: processed {len(items)} items")
                if not data.get("data", {}).get("meta", {}).get("has_more"):
                    break
                time.sleep(0.5)
    print(f"\nDone. Store SKUs inserted: {inserted_skus}, universal products inserted: {inserted_universal}, SKUs updated: {updated_skus}")


if __name__ == "__main__":
    import_products(["молоко", "хлеб", "яйцо", "мука", "сахар", "масло сливочное", "сыр", "курица"], max_pages=1)
