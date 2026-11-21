"""Dynamic nutrition lookup for catalog products.

Primary source: VkusVill MCP product cards (Russian, exact product text).
Fallback source: USDA FoodData Central (verified generic composition).
"""
import html
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx

from app.core.database import SessionLocal
from app.models import Product
from app.api.products import normalize_product_name
from scripts.import_vkusvill import call_tool, clean_name, extract_kbju


USDA_SEARCH = "https://api.nal.usda.gov/fdc/v1/foods/search"
USDA_API_KEY = "DEMO_KEY"

RU_TO_USDA = {
    "молоко": "milk", "кефир": "kefir", "сливки": "cream",
    "сметана": "sour cream", "творог": "cottage cheese",
    "сыр": "cheese", "масло сливочное": "butter",
    "яйцо": "egg", "мука": "flour", "сахар": "sugar", "соль": "salt",
    "рис": "rice", "гречка": "buckwheat", "овсянка": "oats",
    "макароны": "pasta", "хлеб": "bread", "картофель": "potato",
    "морковь": "carrot", "лук": "onion", "чеснок": "garlic",
    "помидор": "tomato", "огурец": "cucumber", "кабачок": "zucchini",
    "яблоко": "apple", "банан": "banana", "апельсин": "orange",
    "курица": "chicken", "говядина": "beef", "свинина": "pork",
    "рыба": "fish", "лосось": "salmon", "тунец": "tuna",
    "шоколад": "chocolate", "йогурт": "yogurt",
}


def kbju_status(kbju: dict) -> str:
    vals = [kbju["calories"], kbju["proteins"], kbju["fats"], kbju["carbs"]]
    if all(value is not None for value in vals):
        return "full"
    if any(value is not None for value in vals):
        return "partial"
    return "missing"


def search_vkusvill_kbju(product: Product) -> dict:
    query = (product.base_name or product.name).strip()
    data = call_tool("vkusvill_products_search", {"q": query, "page": 1})
    if not data or not data.get("ok"):
        return {"proteins": None, "fats": None, "carbs": None, "calories": None}

    items = data.get("data", {}).get("items", [])
    normalized_variation = normalize_product_name(product.variation or "")
    candidates = []
    for item in items:
        name = clean_name(str(item.get("name") or ""))
        normalized_name = normalize_product_name(name)
        if normalized_variation:
            candidate_variation = normalize_product_name(product.variation or "")
            variation_visible = (
                candidate_variation in normalized_name
                or candidate_variation.replace(" ", "") in normalized_name.replace(" ", "")
            )
            if not variation_visible:
                continue
        candidates.append(item)

    for item in candidates or items:
        kbju = extract_kbju(item)
        if any(value is not None for value in kbju.values()):
            return kbju
    return {"proteins": None, "fats": None, "carbs": None, "calories": None}


def search_usda_kbju(product: Product) -> dict:
    base = normalize_product_name(product.base_name or product.name)
    query = RU_TO_USDA.get(base)
    if not query:
        query = next(
            (english for russian, english in RU_TO_USDA.items() if russian in base),
            None,
        )
    if not query:
        return {"proteins": None, "fats": None, "carbs": None, "calories": None}
    variation = normalize_product_name(product.variation or "")
    if query == "milk":
        if any(token in variation for token in ("32", "325", "whole", "цел")):
            query = "milk whole"
        elif any(token in variation for token in ("25", "20", "reduced", "сниж")):
            query = "milk"
        elif any(token in variation for token in ("10", "lowfat", "низк")):
            query = "milk"
        elif any(token in variation for token in ("0", "nonfat", "skim", "обезжир")):
            query = "milk"

    try:
        with httpx.Client(timeout=20) as client:
            response = client.get(
                USDA_SEARCH,
                params={
                    "api_key": USDA_API_KEY,
                    "query": query,
                    "pageSize": 10,
                    "dataType": "Foundation",
                },
            )
            response.raise_for_status()
            foods = response.json().get("foods", [])
    except Exception:
        return {"proteins": None, "fats": None, "carbs": None, "calories": None}

    nutrient_ids = {
        1003: "proteins",
        1004: "fats",
        1005: "carbs",
        1008: "calories",
    }
    def milk_rank(food: dict) -> int:
        description = str(food.get("description") or "").lower()
        if "32" in variation or "325" in variation or "whole" in variation:
            if "whole" in description:
                return 0
        if "25" in variation or "20" in variation or "reduced" in variation:
            if "reduced fat" in description:
                return 0
        if "10" in variation or "lowfat" in variation:
            if "lowfat" in description:
                return 0
        if "0" in variation or "nonfat" in variation or "skim" in variation:
            if "nonfat" in description or "fat free" in description:
                return 0
        return 1

    if query == "milk":
        foods = sorted(foods, key=milk_rank)

    for food in foods:
        description = str(food.get("description") or "").lower()
        if query.startswith("milk") and not description.startswith("milk,"):
            continue
        kbju = {"proteins": None, "fats": None, "carbs": None, "calories": None}
        for nutrient in food.get("foodNutrients", []):
            field = nutrient_ids.get(nutrient.get("nutrientId"))
            if field and nutrient.get("value") is not None:
                kbju[field] = float(nutrient["value"])
        if any(value is not None for value in kbju.values()):
            return kbju
    return {"proteins": None, "fats": None, "carbs": None, "calories": None}


def refresh_one_product(product_id: int) -> dict:
    with SessionLocal() as db:
        product = db.get(Product, product_id)
        if not product or product.status != "active":
            return {"updated_fields": 0, "status": "missing", "source": None}

        kbju = search_vkusvill_kbju(product)
        source = "vkusvill_nutrition" if any(v is not None for v in kbju.values()) else None
        if not source:
            kbju = search_usda_kbju(product)
            source = "usda" if any(v is not None for v in kbju.values()) else None

        updated_fields = 0
        for field in ("calories", "proteins", "fats", "carbs"):
            value = kbju[field]
            if value is not None and getattr(product, field) is None:
                setattr(product, field, value)
                updated_fields += 1

        if updated_fields:
            product.kbju_status = kbju_status({
                "calories": product.calories,
                "proteins": product.proteins,
                "fats": product.fats,
                "carbs": product.carbs,
            })
            if source and all(
                getattr(product, field) is not None
                for field in ("calories", "proteins", "fats", "carbs")
            ):
                product.verified = True
            product.source = source or product.source
            db.commit()
            db.refresh(product)

        return {
            "updated_fields": updated_fields,
            "status": product.kbju_status,
            "source": source,
        }

