import math
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.config import OWNER_ID
from app.core.security import require_auth
from app.models import Product, Recipe, ShoppingList, ShoppingListItem, StoreProduct, StoreProductPrice
from app.schemas.shopping_list import (
    ShoppingCartItemUpdate, ShoppingListCreate, ShoppingListOut, ShoppingListItemOut,
)
from app.services.calculator import Ingredient, scale_ingredients, to_grams
from app.services.pricing import PACKAGE_UNITS, get_latest_price_quote, get_store_product_quote

router = APIRouter(dependencies=[Depends(require_auth)], prefix="/shopping-lists", tags=["shopping-lists"])

UNIT_FAMILY = {
    "g": "weight", "kg": "weight",
    "ml": "volume", "l": "volume",
    "pcs": "pieces",
}
UNIT_FACTORS = {"g": 1.0, "kg": 1000.0, "ml": 1.0, "l": 1000.0, "pcs": 1.0}
CULINARY_UNITS = {"cup", "clove", "bunch", "tbsp", "tsp", "pinch", "to_taste"}
CART_UNITS = set(UNIT_FAMILY) | CULINARY_UNITS


def _merge_units(items: list[Ingredient]):
    merged: dict[tuple[int, str], float] = {}
    names: dict[int, str] = {}
    units: dict[tuple[int, str], str] = {}
    for ingredient in items:
        names[ingredient.product_id] = ingredient.name
        if ingredient.unit in ("g", "kg"):
            family = "weight"
            amount = to_grams(ingredient.amount, ingredient.unit)
            unit = "g"
        elif ingredient.unit in ("ml", "l"):
            family = "volume"
            amount = ingredient.amount * UNIT_FACTORS[ingredient.unit]
            unit = "ml"
        elif ingredient.unit == "pcs":
            family, amount, unit = "pieces", ingredient.amount, "pcs"
        else:
            family, amount, unit = f"unit:{ingredient.unit}", ingredient.amount, ingredient.unit
        key = (ingredient.product_id, family)
        merged[key] = merged.get(key, 0.0) + amount
        units[key] = unit
    return merged, names, units


def _quote_for_cart_item(db: Session, item: ShoppingListItem, product: Product) -> dict | None:
    if item.selected_store_product_id is not None:
        selected = db.get(StoreProduct, item.selected_store_product_id)
        if selected and selected.universal_product_id == product.id:
            return get_store_product_quote(db, selected.id)
        return None
    return get_latest_price_quote(db, product.id)


def _cost_for_amount(amount: float, unit: str, quote: dict | None, override: float | None) -> float | None:
    family = UNIT_FAMILY.get(unit)
    if family is None:
        return None
    rate_key = {"weight": "price_per_kg", "volume": "price_per_liter", "pieces": "price_per_piece"}[family]
    rate = override if override is not None else (quote or {}).get(rate_key)
    if rate is None:
        return None
    if family == "weight":
        quantity = to_grams(amount, unit) / 1000
    elif family == "volume":
        quantity = amount * UNIT_FACTORS[unit] / 1000
    else:
        quantity = amount
    return round(rate * quantity, 2)


def _item_output(item: ShoppingListItem, product: Product, quote: dict | None) -> ShoppingListItemOut:
    family = UNIT_FAMILY.get(item.unit)
    catalog_price = None
    if quote:
        catalog_price = quote.get({
            "weight": "price_per_kg",
            "volume": "price_per_liter",
            "pieces": "price_per_piece",
        }.get(family))

    return ShoppingListItemOut(
        id=item.id,
        product_id=product.id,
        product_name=product.name,
        amount=round(item.amount, 2),
        unit=item.unit,
        cost=_cost_for_amount(item.amount, item.unit, quote, item.price_override),
        price_source="Изменена в корзине" if item.price_override is not None else (quote or {}).get("price_source"),
        observed_at=(quote or {}).get("observed_at"),
        store_name=(quote or {}).get("store_name"),
        store_product_name=(quote or {}).get("store_product_name"),
        manufacturer=(quote or {}).get("manufacturer"),
        selected_store_product_id=item.selected_store_product_id,
        offered_store_product_id=item.selected_store_product_id or (quote or {}).get("store_product_id"),
        price_override=item.price_override,
        price_basis_unit=(quote or {}).get("price_basis_unit") or {
            "weight": "кг", "volume": "л", "pieces": "шт"
        }.get(UNIT_FAMILY.get(item.unit, ""), None),
        catalog_price_per_basis=round(catalog_price, 2) if catalog_price is not None else None,
    )


def _summarize_list(sl: ShoppingList, db: Session) -> ShoppingListOut:
    items = db.query(ShoppingListItem).filter_by(shopping_list_id=sl.id).all()
    items_out = []
    missing: list[str] = []
    total_cost = 0.0
    known_prices = 0
    total_calories = total_proteins = total_fats = total_carbs = 0.0

    for item in items:
        product = db.get(Product, item.product_id)
        if not product:
            continue
        quote = _quote_for_cart_item(db, item, product)
        output = _item_output(item, product, quote)
        items_out.append(output)
        if output.cost is None:
            missing.append(product.name)
        else:
            total_cost += output.cost
            known_prices += 1

        if product.kbju_status == "full" and item.unit == "g":
            factor = item.amount / 100.0
            total_calories += (product.calories or 0) * factor
            total_proteins += (product.proteins or 0) * factor
            total_fats += (product.fats or 0) * factor
            total_carbs += (product.carbs or 0) * factor

    count = len(items_out)
    return ShoppingListOut(
        id=sl.id, title=sl.title, created_at=sl.created_at,
        items=items_out,
        total_cost=round(total_cost, 2) if known_prices else None,
        missing_prices=missing,
        known_prices=known_prices,
        item_count=count,
        coverage_percent=round(known_prices / count * 100, 1) if count else 100.0,
        total_calories=round(total_calories, 1),
        total_proteins=round(total_proteins, 1),
        total_fats=round(total_fats, 1),
        total_carbs=round(total_carbs, 1),
    )


@router.post("", response_model=ShoppingListOut, status_code=201)
def create_shopping_list(payload: ShoppingListCreate, db: Session = Depends(get_db)):
    all_ingredients: list[Ingredient] = []
    for recipe_id in payload.recipe_ids:
        recipe = (
            db.query(Recipe)
            .options(joinedload(Recipe.ingredients))
            .filter_by(id=recipe_id)
            .first()
        )
        if not recipe:
            raise HTTPException(404, f"Recipe {recipe_id} not found")
        target = (payload.servings or {}).get(recipe_id, recipe.base_servings)
        base = []
        for recipe_ingredient in recipe.ingredients:
            product = db.get(Product, recipe_ingredient.product_id)
            if not product:
                continue
            quote = get_latest_price_quote(db, product.id)
            base.append(Ingredient(
                product_id=product.id, name=product.name,
                amount=recipe_ingredient.amount, unit=recipe_ingredient.unit,
                amount_is_exact=recipe_ingredient.amount_is_exact,
                price_per_kg=quote["price_per_kg"] if quote else None,
                price_per_liter=quote["price_per_liter"] if quote else None,
                price_per_piece=quote["price_per_piece"] if quote else None,
            ))
        all_ingredients.extend(scale_ingredients(base, recipe.base_servings, target))

    merged, _, units = _merge_units(all_ingredients)
    sl = ShoppingList(title=payload.title, user_id=OWNER_ID)
    db.add(sl)
    db.flush()
    for (product_id, _family), amount in merged.items():
        if amount <= 0:
            continue
        db.add(ShoppingListItem(
            shopping_list_id=sl.id, product_id=product_id,
            amount=amount, unit=units[(product_id, _family)], bought=False,
        ))
    db.commit()
    db.refresh(sl)
    return _summarize_list(sl, db)


@router.get("/cart/current")
def get_current_cart(db: Session = Depends(get_db)):
    sl = db.query(ShoppingList).filter_by(user_id=OWNER_ID, title="Моя корзина").first()
    if not sl:
        sl = ShoppingList(user_id=OWNER_ID, title="Моя корзина")
        db.add(sl)
        db.commit()
        db.refresh(sl)
    return _summarize_list(sl, db)


@router.post("/cart/add")
def add_to_cart(
    product_id: int,
    amount: float = Query(..., gt=0, le=100000),
    unit: str = Query(..., pattern="^(g|kg|ml|l|pcs|cup|clove|bunch|tbsp|tsp|pinch|to_taste)$"),
    db: Session = Depends(get_db),
):
    if not math.isfinite(amount):
        raise HTTPException(400, "Количество должно быть конечным числом")
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(404, "Product not found")

    sl = db.query(ShoppingList).filter_by(user_id=OWNER_ID, title="Моя корзина").first()
    if not sl:
        sl = ShoppingList(user_id=OWNER_ID, title="Моя корзина")
        db.add(sl)
        db.flush()

    candidates = db.query(ShoppingListItem).filter_by(
        shopping_list_id=sl.id, product_id=product_id
    ).all()
    incoming_family = UNIT_FAMILY.get(unit)
    item = next((
        candidate for candidate in candidates
        if (
            UNIT_FAMILY.get(candidate.unit) == incoming_family
            if incoming_family
            else candidate.unit == unit
        )
    ), None)

    if item:
        if incoming_family == "weight" and item.unit in ("g", "kg"):
            total_base = to_grams(item.amount, item.unit) + to_grams(amount, unit)
            item.unit = "kg" if total_base >= 1000 else "g"
            item.amount = total_base / (1000 if item.unit == "kg" else 1)
        elif incoming_family == "volume" and item.unit in ("ml", "l"):
            total_base = item.amount * UNIT_FACTORS[item.unit] + amount * UNIT_FACTORS[unit]
            item.unit = "l" if total_base >= 1000 else "ml"
            item.amount = total_base / UNIT_FACTORS[item.unit]
        else:
            item.amount += amount
    else:
        db.add(ShoppingListItem(
            shopping_list_id=sl.id, product_id=product_id,
            amount=amount, unit=unit, bought=False,
        ))
    db.commit()
    return _summarize_list(sl, db)


@router.patch("/cart/item/{item_id}", response_model=ShoppingListOut)
def update_cart_item(item_id: int, payload: ShoppingCartItemUpdate, db: Session = Depends(get_db)):
    item = db.get(ShoppingListItem, item_id)
    if item is None:
        raise HTTPException(404, "Cart item not found")
    if payload.unit is not None and payload.unit not in CART_UNITS:
        raise HTTPException(422, "Недопустимая единица измерения")
    product = db.get(Product, item.product_id)
    if product is None:
        raise HTTPException(404, "Product not found")
    if "selected_store_product_id" in payload.model_fields_set and payload.selected_store_product_id is not None:
        offer = db.get(StoreProduct, payload.selected_store_product_id)
        if not offer or offer.universal_product_id != product.id or offer.status != "active":
            raise HTTPException(422, "Предложение не относится к этому активному продукту")
        package = PACKAGE_UNITS.get((offer.package_unit or "").strip().casefold())
        family = UNIT_FAMILY.get(item.unit)
        if family and package and package[0] != family:
            raise HTTPException(422, "Единица предложения несовместима с количеством в корзине")
    new_unit = payload.unit if payload.unit is not None else item.unit
    if item.price_override is not None and UNIT_FAMILY.get(new_unit) != UNIT_FAMILY.get(item.unit):
        raise HTTPException(422, "Сначала сбросьте цену корзины, чтобы изменить тип единицы")

    if payload.amount is not None:
        item.amount = payload.amount
    if payload.unit is not None:
        item.unit = payload.unit
    if "price_override" in payload.model_fields_set:
        item.price_override = payload.price_override
    if "selected_store_product_id" in payload.model_fields_set:
        item.selected_store_product_id = payload.selected_store_product_id

    db.commit()
    sl = db.get(ShoppingList, item.shopping_list_id)
    return _summarize_list(sl, db)


@router.post("/cart/item/{item_id}/save-price", response_model=ShoppingListOut)
def save_cart_price_to_history(item_id: int, db: Session = Depends(get_db)):
    item = db.get(ShoppingListItem, item_id)
    if item is None:
        raise HTTPException(404, "Cart item not found")
    if item.price_override is None:
        raise HTTPException(409, "Сначала укажите новую цену для этой корзины")
    product = db.get(Product, item.product_id)
    if product is None:
        raise HTTPException(404, "Product not found")
    quote = _quote_for_cart_item(db, item, product)
    store_product_id = (
        item.selected_store_product_id
        if item.selected_store_product_id is not None
        else (quote or {}).get("store_product_id")
    )
    store_product = db.get(StoreProduct, store_product_id) if store_product_id else None
    if not store_product or store_product.package_amount is None:
        raise HTTPException(409, "Для сохранения цены выберите предложение с размером упаковки")
    package = PACKAGE_UNITS.get((store_product.package_unit or "").strip().casefold())
    family = UNIT_FAMILY.get(item.unit)
    if package is None or family is None or package[0] != family:
        raise HTTPException(422, "Единица цены не совместима с выбранным предложением")
    if item.price_override <= 0:
        raise HTTPException(422, "Цена в истории должна быть больше нуля")
    package_amount = float(store_product.package_amount) * package[1]
    divisor = 1000 if family in ("weight", "volume") else 1
    package_price = item.price_override * package_amount / divisor
    db.add(StoreProductPrice(
        store_product_id=store_product.id,
        price=package_price,
        currency="RUB",
        region=store_product.region,
        source="manual",
    ))
    db.commit()
    sl = db.get(ShoppingList, item.shopping_list_id)
    return _summarize_list(sl, db)


@router.delete("/cart/item/{item_id}")
def remove_from_cart(item_id: int, db: Session = Depends(get_db)):
    item = db.get(ShoppingListItem, item_id)
    if item is None:
        raise HTTPException(404, "Cart item not found")
    db.delete(item)
    db.commit()
    return {"ok": True}


@router.get("/{list_id}", response_model=ShoppingListOut)
def get_shopping_list(list_id: int, db: Session = Depends(get_db)):
    sl = db.get(ShoppingList, list_id)
    if not sl:
        raise HTTPException(404, "Shopping list not found")
    return _summarize_list(sl, db)
