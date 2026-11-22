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


def _package_details(
    amount: float,
    unit: str,
    quote: dict | None,
    package_amount_override: float | None = None,
    package_unit_override: str | None = None,
    package_amount_in_recipe_unit_override: float | None = None,
) -> tuple[float, str, float | None, int | None] | None:
    has_package_override = package_amount_override is not None
    package_amount = package_amount_override if has_package_override else (quote or {}).get("package_amount")
    package_unit = package_unit_override if has_package_override else (quote or {}).get("package_unit")
    if package_amount is None or package_unit is None:
        return None
    package = PACKAGE_UNITS.get(str(package_unit).strip().casefold())
    if package is None:
        return None
    package_base_amount = float(package_amount) * package[1]
    if package_base_amount <= 0:
        return None
    family = UNIT_FAMILY.get(unit)
    if package_amount_in_recipe_unit_override is not None:
        count = max(1, math.ceil(amount / package_amount_in_recipe_unit_override - 1e-9))
    elif family is None or package[0] != family:
        count = None
    else:
        base_amount = amount * UNIT_FACTORS[unit] if family != "pieces" else amount
        count = max(1, math.ceil(base_amount / package_base_amount - 1e-9))
    package_price = None if has_package_override else (quote or {}).get("package_price")
    return (
        float(package_amount),
        str(package_unit),
        float(package_price) if package_price is not None else None,
        count,
    )


def _package_basis_info(package_amount: float, package_unit: str) -> tuple[str, str, float] | None:
    package = PACKAGE_UNITS.get(package_unit.strip().casefold())
    if package is None:
        return None
    family, factor = package
    quantity = package_amount * factor
    if family in ("weight", "volume"):
        quantity /= 1000
    if quantity <= 0:
        return None
    rate_key = {
        "weight": "price_per_kg",
        "volume": "price_per_liter",
        "pieces": "price_per_piece",
    }[family]
    basis_unit = {"weight": "кг", "volume": "л", "pieces": "шт"}[family]
    return rate_key, basis_unit, quantity


def _cost_for_amount(
    amount: float,
    unit: str,
    quote: dict | None,
    override: float | None,
    package_price_override: float | None = None,
    package_amount_override: float | None = None,
    package_unit_override: str | None = None,
    package_amount_in_recipe_unit_override: float | None = None,
    price_mode: str | None = None,
) -> float | None:
    package = _package_details(
        amount,
        unit,
        quote,
        package_amount_override,
        package_unit_override,
        package_amount_in_recipe_unit_override,
    )
    if price_mode == "package":
        if package is None or package[3] is None:
            return None
        package_price = package_price_override if package_price_override is not None else package[2]
        return round(package_price * package[3], 2) if package_price is not None else None
    family = UNIT_FAMILY.get(unit)
    if family is None:
        if (
            price_mode != "basis"
            or package is None
            or package_amount_in_recipe_unit_override is None
        ):
            return None
        basis_info = _package_basis_info(package[0], package[1])
        if basis_info is None:
            return None
        rate_key, _, package_quantity = basis_info
        rate = override if override is not None else (quote or {}).get(rate_key)
        if rate is None:
            package_price = (
                package_price_override
                if package_price_override is not None
                else package[2]
            )
            if package_price is None:
                return None
            rate = package_price / package_quantity
        amount_in_basis_units = (
            package_quantity * amount / package_amount_in_recipe_unit_override
        )
        return round(rate * amount_in_basis_units, 2)

    if price_mode is None and package is not None and package[3] is not None:
        if package_price_override is not None:
            return round(package_price_override * package[3], 2)
        if family == "pieces" and override is None and package[2] is not None:
            return round(package[2] * package[3], 2)
    rate_key = {"weight": "price_per_kg", "volume": "price_per_liter", "pieces": "price_per_piece"}[family]
    rate = override if override is not None else (quote or {}).get(rate_key)
    if rate is None and package is not None:
        basis_info = _package_basis_info(package[0], package[1])
        if basis_info is not None and basis_info[0] == rate_key:
            package_price = (
                package_price_override
                if package_price_override is not None
                else package[2]
            )
            if package_price is not None:
                rate = package_price / basis_info[2]
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
    package = _package_details(
        item.amount,
        item.unit,
        quote,
        item.package_amount_override,
        item.package_unit_override,
        item.package_amount_in_recipe_unit_override,
    )
    basis_info = (
        _package_basis_info(package[0], package[1])
        if package is not None
        else None
    )
    basis_rate_key = basis_info[0] if family is None and basis_info else {
        "weight": "price_per_kg",
        "volume": "price_per_liter",
        "pieces": "price_per_piece",
    }.get(family)
    catalog_price = (quote or {}).get(basis_rate_key) if basis_rate_key else None
    if item.package_amount_override is not None and basis_info and quote:
        quote_basis = _package_basis_info(
            float(quote.get("package_amount") or 0),
            str(quote.get("package_unit") or ""),
        )
        if quote_basis and quote_basis[0] != basis_info[0]:
            catalog_price = None
    if catalog_price is None and package is not None and basis_info:
        package_price = (
            item.package_price_override
            if item.package_price_override is not None
            else package[2]
        )
        if package_price is not None:
            catalog_price = package_price / basis_info[2]
    package_amount = package[0] if package else None
    package_unit = package[1] if package else None
    catalog_package_price = package[2] if package else None
    package_count = package[3] if package else None
    price_mode = item.price_mode
    if price_mode is None:
        price_mode = (
            "package"
            if family is None or package is not None and (
                item.package_price_override is not None
                or family == "pieces" and package[2] is not None
            )
            else "basis"
        )

    return ShoppingListItemOut(
        id=item.id,
        product_id=product.id,
        product_name=product.name,
        amount=round(item.amount, 2),
        unit=item.unit,
        cost=_cost_for_amount(
            item.amount,
            item.unit,
            quote,
            item.price_override,
            item.package_price_override,
            item.package_amount_override,
            item.package_unit_override,
            item.package_amount_in_recipe_unit_override,
            item.price_mode,
        ),
        price_source=(
            "Изменена в корзине"
            if (
                item.price_mode == "package" and item.package_price_override is not None
                or item.price_mode == "basis" and item.price_override is not None
                or item.price_mode is None and (
                    item.price_override is not None or item.package_price_override is not None
                )
            )
            else (quote or {}).get("price_source")
        ),
        observed_at=(quote or {}).get("observed_at"),
        store_name=(quote or {}).get("store_name"),
        store_product_name=(quote or {}).get("store_product_name"),
        manufacturer=(quote or {}).get("manufacturer"),
        selected_store_product_id=item.selected_store_product_id,
        offered_store_product_id=item.selected_store_product_id or (quote or {}).get("store_product_id"),
        price_override=item.price_override,
        price_basis_unit=(
            basis_info[1]
            if item.package_amount_override is not None and basis_info
            else (
                (quote or {}).get("price_basis_unit")
                or (basis_info[1] if basis_info else None)
            )
        ),
        catalog_price_per_basis=round(catalog_price, 2) if catalog_price is not None else None,
        package_amount=package_amount,
        package_unit=package_unit,
        package_price=catalog_package_price,
        package_price_override=item.package_price_override,
        package_amount_override=item.package_amount_override,
        package_unit_override=item.package_unit_override,
        package_amount_in_recipe_unit_override=item.package_amount_in_recipe_unit_override,
        price_mode=price_mode,
        package_count=package_count,
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
    new_unit = payload.unit if payload.unit is not None else item.unit
    package_override_fields = {"package_amount_override", "package_unit_override"}
    if package_override_fields.intersection(payload.model_fields_set):
        if not package_override_fields.issubset(payload.model_fields_set):
            raise HTTPException(422, "Размер упаковки и единицу нужно указать или сбросить вместе")
        if (payload.package_amount_override is None) != (payload.package_unit_override is None):
            raise HTTPException(422, "Размер упаковки и единицу нужно указать или сбросить вместе")
        if payload.package_amount_override is not None:
            package = PACKAGE_UNITS.get(payload.package_unit_override.casefold())
            if package is None:
                raise HTTPException(422, "Недопустимая единица упаковки")
    if item.price_override is not None and UNIT_FAMILY.get(new_unit) != UNIT_FAMILY.get(item.unit):
        raise HTTPException(422, "Сначала сбросьте цену корзины, чтобы изменить тип единицы")

    if payload.amount is not None:
        item.amount = payload.amount
    if payload.unit is not None and payload.unit != item.unit:
        item.package_amount_in_recipe_unit_override = None
        if UNIT_FAMILY.get(payload.unit) is None:
            item.price_mode = "package"
    if payload.unit is not None:
        item.unit = payload.unit
    if "price_override" in payload.model_fields_set:
        item.price_override = payload.price_override
    if "package_price_override" in payload.model_fields_set:
        item.package_price_override = payload.package_price_override
    if package_override_fields.issubset(payload.model_fields_set):
        item.package_amount_override = payload.package_amount_override
        item.package_unit_override = payload.package_unit_override
        item.package_amount_in_recipe_unit_override = None
        if UNIT_FAMILY.get(item.unit) is None:
            item.price_mode = "package"
    if "package_amount_in_recipe_unit_override" in payload.model_fields_set:
        if payload.package_amount_in_recipe_unit_override is not None:
            effective_package_amount = item.package_amount_override
            effective_package_unit = item.package_unit_override
            if effective_package_amount is None:
                quote = _quote_for_cart_item(db, item, product) or {}
                effective_package_amount = quote.get("package_amount")
                effective_package_unit = quote.get("package_unit")
            if effective_package_amount is None or effective_package_unit is None:
                raise HTTPException(422, "Сначала укажите размер упаковки")
        item.package_amount_in_recipe_unit_override = payload.package_amount_in_recipe_unit_override
    if payload.price_mode is not None:
        item.price_mode = payload.price_mode
    if "selected_store_product_id" in payload.model_fields_set:
        if (
            payload.selected_store_product_id != item.selected_store_product_id
            and item.package_amount_override is None
        ):
            item.package_amount_in_recipe_unit_override = None
            if UNIT_FAMILY.get(item.unit) is None:
                item.price_mode = "package"
        item.selected_store_product_id = payload.selected_store_product_id

    db.commit()
    sl = db.get(ShoppingList, item.shopping_list_id)
    return _summarize_list(sl, db)


@router.post("/cart/item/{item_id}/save-price", response_model=ShoppingListOut)
def save_cart_price_to_history(item_id: int, db: Session = Depends(get_db)):
    item = db.get(ShoppingListItem, item_id)
    if item is None:
        raise HTTPException(404, "Cart item not found")
    if item.price_override is None and item.package_price_override is None:
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
    if item.package_price_override is not None:
        if item.package_price_override <= 0:
            raise HTTPException(422, "Цена упаковки в истории должна быть больше нуля")
        db.add(StoreProductPrice(
            store_product_id=store_product.id,
            price=item.package_price_override,
            currency="RUB",
            region=store_product.region,
            source="manual",
        ))
        db.commit()
        sl = db.get(ShoppingList, item.shopping_list_id)
        return _summarize_list(sl, db)
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
