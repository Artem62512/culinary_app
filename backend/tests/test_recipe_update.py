from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models import Product, Recipe, RecipeIngredient, User
from app.api.recipes import create_recipe, update_recipe
from app.schemas.recipe import RecipeCreate, RecipeIngredientIn


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def seed_recipe(db):
    owner = User(email="owner@example.test", hashed_password="unused")
    flour = Product(name="Мука пшеничная", category="Бакалея", base_name="Мука")
    sugar = Product(name="Сахар", category="Бакалея", base_name="Сахар")
    db.add_all([owner, flour, sugar])
    db.flush()
    recipe = Recipe(
        user_id=owner.id,
        title="Старое название",
        description="Старое описание",
        base_servings=2,
        instructions="Старый текст",
    )
    db.add(recipe)
    db.flush()
    old_ingredient = RecipeIngredient(
        recipe_id=recipe.id, product_id=flour.id, amount=100, unit="g", note="просеять"
    )
    db.add(old_ingredient)
    db.commit()
    return recipe.id, old_ingredient.id, flour.id, sugar.id, recipe.created_at


def test_update_recipe_preserves_recipe_id_and_replaces_ingredients(db_session):
    recipe_id, old_ingredient_id, flour_id, sugar_id, created_at = seed_recipe(db_session)
    payload = RecipeCreate(
        title="Новое название",
        description="Новое описание",
        base_servings=4,
        instructions="Новая инструкция",
        ingredients=[
            RecipeIngredientIn(product_id=sugar_id, amount=75, unit="g", note="для теста"),
            RecipeIngredientIn(product_id=flour_id, amount=0.25, unit="kg"),
        ],
    )

    result = update_recipe(recipe_id, payload, db_session)

    assert result.id == recipe_id
    assert result.title == "Новое название"
    assert result.description == "Новое описание"
    assert result.base_servings == 4
    assert result.instructions == "Новая инструкция"
    assert len(result.ingredients) == 2
    assert {item.product_id for item in result.ingredients} == {flour_id, sugar_id}
    assert old_ingredient_id not in {item.id for item in result.ingredients}
    stored = db_session.get(Recipe, recipe_id)
    assert stored.created_at == created_at


def test_update_recipe_with_unknown_product_keeps_original_data(db_session):
    recipe_id, old_ingredient_id, flour_id, _, _ = seed_recipe(db_session)
    payload = RecipeCreate(
        title="Не должно сохраниться",
        base_servings=3,
        ingredients=[RecipeIngredientIn(product_id=99999, amount=10, unit="g")],
    )

    with pytest.raises(HTTPException) as exc:
        update_recipe(recipe_id, payload, db_session)

    assert exc.value.status_code == 404
    stored = db_session.get(Recipe, recipe_id)
    assert stored.title == "Старое название"
    assert len(stored.ingredients) == 1
    assert stored.ingredients[0].id == old_ingredient_id
    assert stored.ingredients[0].product_id == flour_id


def test_update_recipe_returns_404_for_missing_recipe(db_session):
    payload = RecipeCreate(
        title="Несуществующий",
        base_servings=1,
        ingredients=[RecipeIngredientIn(product_id=1, amount=10, unit="g")],
    )
    with pytest.raises(HTTPException) as exc:
        update_recipe(123456, payload, db_session)
    assert exc.value.status_code == 404


def test_recipe_ingredient_requires_catalog_product():
    with pytest.raises(Exception):
        RecipeIngredientIn(amount=10, unit="g")


def test_recipe_with_product_missing_kbju_is_included_as_missing_data(db_session):
    from app.api.recipes import calculate_recipe

    recipe_id, _, _, _, _ = seed_recipe(db_session)
    unknown = Product(name="Редкий ингредиент", calories=None, proteins=None,
                      fats=None, carbs=None, kbju_status="missing")
    db_session.add(unknown)
    db_session.commit()

    payload = RecipeCreate(
        title="Частичный расчёт",
        base_servings=1,
        ingredients=[RecipeIngredientIn(product_id=unknown.id, amount=100, unit="g")],
    )
    update_recipe(recipe_id, payload, db_session)
    result = calculate_recipe(recipe_id, servings=1, db=db_session)
    assert result.total.accuracy == "approximate"
    assert result.cost.missing_prices == ["Редкий ингредиент"]


def test_recipe_preserves_exact_range_and_to_taste_amounts(db_session):
    from app.api.recipes import calculate_recipe

    recipe_id, _, _, _, _ = seed_recipe(db_session)
    flour = Product(name="Мука", kbju_status="missing")
    salt = Product(name="Соль", kbju_status="missing")
    pepper = Product(name="Перец", kbju_status="missing")
    db_session.add_all([flour, salt, pepper])
    db_session.commit()

    payload = RecipeCreate(
        title="Проверка количества",
        base_servings=2,
        ingredients=[
            RecipeIngredientIn(
                product_id=flour.id,
                amount=0.5,
                amount_text="1/2",
                amount_is_exact=True,
                unit="cup",
            ),
            RecipeIngredientIn(
                product_id=salt.id,
                amount=0,
                amount_text="0,5–1",
                amount_is_exact=False,
                unit="tbsp",
            ),
            RecipeIngredientIn(
                product_id=pepper.id,
                amount=0,
                amount_text="по вкусу",
                amount_is_exact=False,
                unit="to_taste",
            ),
        ],
    )

    saved = update_recipe(recipe_id, payload, db_session)

    flour_out = next(item for item in saved.ingredients if item.product_id == flour.id)
    salt_out = next(item for item in saved.ingredients if item.product_id == salt.id)
    pepper_out = next(item for item in saved.ingredients if item.product_id == pepper.id)

    assert (flour_out.amount, flour_out.amount_text, flour_out.amount_is_exact) == (0.5, "1/2", True)
    assert (salt_out.amount, salt_out.amount_text, salt_out.amount_is_exact) == (0, "0,5–1", False)
    assert (pepper_out.amount, pepper_out.amount_text, pepper_out.amount_is_exact) == (0, "по вкусу", False)

    calculated = calculate_recipe(recipe_id, servings=4, db=db_session)

    flour_calc = next(item for item in calculated.ingredients if item.product_name == "Мука")
    salt_calc = next(item for item in calculated.ingredients if item.product_name == "Соль")
    pepper_calc = next(item for item in calculated.ingredients if item.product_name == "Перец")

    assert flour_calc.amount == 1.0
    assert flour_calc.amount_text == "1/2"
    assert salt_calc.amount == 0
    assert salt_calc.amount_text == "0,5–1"
    assert salt_calc.amount_is_exact is False
    assert pepper_calc.amount == 0
    assert pepper_calc.amount_text == "по вкусу"
    assert pepper_calc.amount_is_exact is False



def test_create_recipe_uses_only_catalog_product_and_returns_product_name(db_session):
    owner = User(email="owner@example.test", hashed_password="unused")
    product = Product(name="Масло растительное", calories=None, proteins=None,
                      fats=None, carbs=None, kbju_status="missing")
    db_session.add_all([owner, product])
    db_session.commit()

    result = create_recipe(
        RecipeCreate(
            title="Новый рецепт",
            base_servings=2,
            ingredients=[
                RecipeIngredientIn(
                    product_id=product.id,
                    amount=2,
                    amount_text="2",
                    amount_is_exact=True,
                    unit="tbsp",
                )
            ],
        ),
        db_session,
    )

    assert len(result.ingredients) == 1
    ingredient = result.ingredients[0]
    assert ingredient.product_id == product.id
    assert ingredient.product_name == "Масло растительное"
    assert not hasattr(ingredient, "custom_name")
    assert ingredient.amount_text == "2"
