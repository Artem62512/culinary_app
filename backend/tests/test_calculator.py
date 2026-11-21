import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from app.services.calculator import (
    Ingredient, convert_unit, to_grams, scale_ingredients,
    calc_recipe_kbju, calc_per_serving, calc_recipe_cost,
)


def test_convert_weight():
    assert convert_unit(1, "kg", "g") == 1000
    assert convert_unit(500, "g", "kg") == 0.5
    assert convert_unit(2, "l", "ml") == 2000


def test_convert_incompatible():
    with pytest.raises(ValueError):
        convert_unit(1, "kg", "ml")


def test_scale_ingredients():
    ing = [Ingredient(product_id=1, name="Мука", amount=200, unit="g")]
    scaled = scale_ingredients(ing, base_servings=2, target_servings=6)
    assert scaled[0].amount == 600


def test_scale_invalid_servings():
    with pytest.raises(ValueError):
        scale_ingredients([], 0, 4)


def test_kbju_full():
    ings = [
        Ingredient(product_id=1, name="Мука", amount=200, unit="g",
                   calories=342, proteins=10.3, fats=1.1, carbs=69.9, kbju_status="full"),
    ]
    result = calc_recipe_kbju(ings)
    assert result["calories"] == pytest.approx(684.0, rel=0.01)
    assert result["accuracy"] == "exact"


def test_kbju_approximate():
    ings = [
        Ingredient(product_id=1, name="Мука", amount=100, unit="g",
                   calories=342, proteins=10.3, fats=1.1, carbs=69.9, kbju_status="full"),
        Ingredient(product_id=2, name="Секрет", amount=50, unit="g",
                   calories=None, proteins=None, fats=None, carbs=None, kbju_status="missing"),
    ]
    result = calc_recipe_kbju(ings)
    assert result["accuracy"] == "approximate"
    assert result["calories"] is None
    assert result["known_calories"] == pytest.approx(342.0)
    assert "Секрет" in result["missing_ingredients"][0]


def test_per_serving():
    kbju = {"calories": 600, "proteins": 30, "fats": 20, "carbs": 60,
            "known_calories": 600, "known_proteins": 30, "known_fats": 20, "known_carbs": 60,
            "accuracy": "exact", "coverage_percent": 100,
            "missing_components": [], "missing_ingredients": []}
    per = calc_per_serving(kbju, 3)
    assert per["calories"] == 200
    assert per["proteins"] == 10


def test_partial_kbju_keeps_only_known_component_as_subtotal():
    ingredient = Ingredient(product_id=1, name="Продукт", amount=100, unit="g",
                            calories=120, proteins=4, fats=None, carbs=10, kbju_status="partial")
    result = calc_recipe_kbju([ingredient])
    assert result["calories"] == 120
    assert result["proteins"] == 4
    assert result["fats"] is None
    assert result["known_fats"] == 0
    assert result["carbs"] == 10
    assert result["coverage_percent"] == 0


def test_piece_units_are_not_treated_as_grams():
    ingredient = Ingredient(product_id=1, name="Яйцо", amount=2, unit="pcs",
                            calories=150, proteins=13, fats=10, carbs=1, kbju_status="full")
    result = calc_recipe_kbju([ingredient])
    assert result["calories"] is None
    assert result["known_calories"] == 0
    assert result["accuracy"] == "approximate"


def test_volume_unit_is_not_treated_as_mass():
    ingredient = Ingredient(product_id=1, name="Молоко", amount=100, unit="ml",
                            calories=60, proteins=3, fats=3, carbs=5, kbju_status="full")
    result = calc_recipe_kbju([ingredient])
    assert result["calories"] is None
    assert result["missing_components"] == ["ккал", "белки", "жиры", "углеводы"]


def test_kilograms_are_converted_to_grams_for_nutrition():
    ingredient = Ingredient(product_id=1, name="Рис", amount=1, unit="kg",
                            calories=350, proteins=7, fats=1, carbs=78, kbju_status="full")
    result = calc_recipe_kbju([ingredient])
    assert result["calories"] == 3500
    assert result["accuracy"] == "exact"


def test_cost():
    ings = [
        Ingredient(product_id=1, name="Мука", amount=500, unit="g", price_per_kg=80),
        Ingredient(product_id=2, name="Сахар", amount=100, unit="g", price_per_kg=100),
    ]
    result = calc_recipe_cost(ings)
    assert result["total_cost"] == pytest.approx(50.0, rel=0.01)
    assert result["missing_prices"] == []


def test_cost_missing_price():
    ings = [Ingredient(product_id=1, name="Мука", amount=500, unit="g", price_per_kg=None)]
    result = calc_recipe_cost(ings)
    assert result["total_cost"] is None
    assert "Мука" in result["missing_prices"]


def test_per_100g_calculation_uses_total_recipe_mass():
    from app.services.calculator import calc_per_100g
    ingredients = [
        Ingredient(product_id=1, name="Овсянка", amount=100, unit="g",
                   calories=370, proteins=13, fats=7, carbs=62, kbju_status="full"),
        Ingredient(product_id=2, name="Сахар", amount=100, unit="g",
                   calories=400, proteins=0, fats=0, carbs=100, kbju_status="full"),
    ]
    per_100g = calc_per_100g(calc_recipe_kbju(ingredients))
    assert per_100g["calories"] == 385
    assert per_100g["proteins"] == 6.5
    assert per_100g["accuracy"] == "exact"


def test_per_100g_is_unknown_when_recipe_mass_is_not_known():
    from app.services.calculator import calc_per_100g
    ingredients = [Ingredient(product_id=1, name="Молоко", amount=100, unit="ml",
                              calories=60, proteins=3, fats=3, carbs=5, kbju_status="full")]
    per_100g = calc_per_100g(calc_recipe_kbju(ingredients))
    assert per_100g["calories"] is None
    assert per_100g["known_calories"] is None
    assert any("общая масса" in x for x in per_100g["missing_ingredients"])


def test_recipe_cost_converts_weight_volume_and_piece_prices():
    ingredients = [
        Ingredient(product_id=1, name="Мука", amount=250, unit="g", price_per_kg=240),
        Ingredient(product_id=2, name="Молоко", amount=0.25, unit="l", price_per_liter=120),
        Ingredient(product_id=3, name="Яйцо", amount=2, unit="pcs", price_per_piece=3.5),
    ]
    result = calc_recipe_cost(ingredients)
    assert result["total_cost"] == pytest.approx(97.0)
    assert result["known_ingredients"] == 3
    assert result["coverage_percent"] == 100


def test_recipe_cost_marks_culinary_units_unknown():
    ingredient = Ingredient(product_id=1, name="Мука", amount=1, unit="cup", price_per_kg=100)
    result = calc_recipe_cost([ingredient])
    assert result["total_cost"] is None
    assert result["missing_prices"] == ["Мука"]
