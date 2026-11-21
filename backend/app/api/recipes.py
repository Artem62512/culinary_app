from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.config import OWNER_ID
from app.core.security import require_auth
from app.models import Product, Recipe, RecipeIngredient
from app.schemas.recipe import (
    RecipeCreate, RecipeOut, RecipeIngredientOut,
    CalculationOut, NutritionOut, CostOut,
)
from app.services.calculator import (
    Ingredient, scale_ingredients, calc_recipe_kbju,
    calc_per_serving, calc_per_100g, calc_recipe_cost,
)
from app.services.pricing import get_latest_price_quote

router = APIRouter(dependencies=[Depends(require_auth)], prefix="/recipes", tags=["recipes"])


def _to_ingredient_list(recipe: Recipe, db: Session) -> list[Ingredient]:
    result = []
    for ri in recipe.ingredients:
        product = db.get(Product, ri.product_id)
        if product is None:
            continue
        price = get_latest_price_quote(db, product.id)
        result.append(Ingredient(
            product_id=product.id,
            name=product.name,
            amount=ri.amount,
            amount_text=ri.amount_text,
            amount_is_exact=ri.amount_is_exact,
            unit=ri.unit,
            calories=product.calories,
            proteins=product.proteins,
            fats=product.fats,
            carbs=product.carbs,
            kbju_status=product.kbju_status,
            price_per_kg=price["price_per_kg"] if price else None,
            price_per_liter=price["price_per_liter"] if price else None,
            price_per_piece=price["price_per_piece"] if price else None,
        ))
    return result


def _serialize_recipe(recipe: Recipe, db: Session) -> RecipeOut:
    ingredients = []
    for ri in recipe.ingredients:
        product = db.get(Product, ri.product_id)
        if product is None:
            continue
        ingredients.append(RecipeIngredientOut(
            id=ri.id,
            product_id=product.id,
            product_name=product.name,
            amount=ri.amount,
            unit=ri.unit,
            amount_text=ri.amount_text,
            amount_is_exact=ri.amount_is_exact,
            note=ri.note,
        ))
    return RecipeOut(
        id=recipe.id,
        title=recipe.title,
        description=recipe.description,
        base_servings=recipe.base_servings,
        instructions=recipe.instructions,
        created_at=recipe.created_at,
        ingredients=ingredients,
    )


def _validate_products(payload: RecipeCreate, db: Session) -> None:
    for ingredient in payload.ingredients:
        product = db.get(Product, ingredient.product_id)
        if product is None:
            raise HTTPException(404, f"Product {ingredient.product_id} not found")


def _apply_recipe_payload(recipe: Recipe, payload: RecipeCreate) -> None:
    recipe.title = payload.title
    recipe.description = payload.description
    recipe.base_servings = payload.base_servings
    recipe.instructions = payload.instructions
    recipe.ingredients.clear()
    for ingredient in payload.ingredients:
        recipe.ingredients.append(RecipeIngredient(
            product_id=ingredient.product_id,
            amount=ingredient.amount,
            amount_text=ingredient.amount_text,
            amount_is_exact=ingredient.amount_is_exact,
            unit=ingredient.unit,
            note=ingredient.note,
        ))


@router.get("", response_model=list[RecipeOut])
def list_recipes(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    recipes = (
        db.query(Recipe)
        .options(joinedload(Recipe.ingredients))
        .order_by(Recipe.created_at.desc())
        .offset(offset).limit(limit).all()
    )
    return [_serialize_recipe(recipe, db) for recipe in recipes]


@router.post("", response_model=RecipeOut, status_code=201)
def create_recipe(payload: RecipeCreate, db: Session = Depends(get_db)):
    _validate_products(payload, db)
    recipe = Recipe(
        user_id=OWNER_ID,
        title=payload.title,
        description=payload.description,
        base_servings=payload.base_servings,
        instructions=payload.instructions,
    )
    db.add(recipe)
    db.flush()
    for ingredient in payload.ingredients:
        recipe.ingredients.append(RecipeIngredient(
            product_id=ingredient.product_id,
            amount=ingredient.amount,
            amount_text=ingredient.amount_text,
            amount_is_exact=ingredient.amount_is_exact,
            unit=ingredient.unit,
            note=ingredient.note,
        ))
    db.commit()
    db.refresh(recipe)
    return _serialize_recipe(recipe, db)


@router.get("/{recipe_id}", response_model=RecipeOut)
def get_recipe(recipe_id: int, db: Session = Depends(get_db)):
    recipe = (
        db.query(Recipe)
        .options(joinedload(Recipe.ingredients))
        .filter_by(id=recipe_id)
        .first()
    )
    if recipe is None:
        raise HTTPException(404, "Recipe not found")
    return _serialize_recipe(recipe, db)


@router.put("/{recipe_id}", response_model=RecipeOut)
def update_recipe(recipe_id: int, payload: RecipeCreate, db: Session = Depends(get_db)):
    recipe = (
        db.query(Recipe)
        .options(joinedload(Recipe.ingredients))
        .filter_by(id=recipe_id)
        .first()
    )
    if recipe is None:
        raise HTTPException(404, "Recipe not found")

    # Validate every product before replacing any existing recipe data.
    _validate_products(payload, db)

    try:
        _apply_recipe_payload(recipe, payload)
        db.commit()
        db.refresh(recipe)
    except Exception:
        db.rollback()
        raise

    return _serialize_recipe(recipe, db)


@router.get("/{recipe_id}/calculate", response_model=CalculationOut)
def calculate_recipe(
    recipe_id: int,
    servings: int = Query(..., gt=0, description="Целевое число порций"),
    db: Session = Depends(get_db),
):
    recipe = (
        db.query(Recipe)
        .options(joinedload(Recipe.ingredients))
        .filter_by(id=recipe_id)
        .first()
    )
    if recipe is None:
        raise HTTPException(404, "Recipe not found")

    base_ingredients = _to_ingredient_list(recipe, db)
    scaled = scale_ingredients(base_ingredients, recipe.base_servings, servings)

    total = calc_recipe_kbju(scaled)
    per_serving = calc_per_serving(total, servings)
    per_100g = calc_per_100g(total)
    cost = calc_recipe_cost(scaled)

    return CalculationOut(
        recipe_id=recipe.id,
        recipe_title=recipe.title,
        target_servings=servings,
        ingredients=[
            RecipeIngredientOut(
                id=0,
                product_id=ingredient.product_id,
                product_name=ingredient.name,
                amount=ingredient.amount,
                amount_text=ingredient.amount_text,
                amount_is_exact=ingredient.amount_is_exact,
                unit=ingredient.unit,
                note=None,
            )
            for ingredient in scaled
        ],
        total=NutritionOut(**total),
        per_serving=NutritionOut(**per_serving),
        per_100g=NutritionOut(**per_100g),
        cost=CostOut(**cost),
    )


@router.delete("/{recipe_id}", status_code=204)
def delete_recipe(recipe_id: int, db: Session = Depends(get_db)):
    recipe = db.get(Recipe, recipe_id)
    if recipe is None:
        raise HTTPException(404, "Recipe not found")
    db.delete(recipe)
    db.commit()
    return None
