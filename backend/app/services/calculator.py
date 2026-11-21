
from dataclasses import dataclass
from typing import Iterable

UNIT_TO_GRAMS = {"g": 1.0, "kg": 1000.0}
UNIT_TO_ML = {"ml": 1.0, "l": 1000.0}

WEIGHT_UNITS = set(UNIT_TO_GRAMS)
VOLUME_UNITS = set(UNIT_TO_ML)
PIECE_UNITS = {"pcs"}


@dataclass
class Ingredient:
    product_id: int
    name: str
    amount: float
    unit: str
    calories: float | None = None
    proteins: float | None = None
    fats: float | None = None
    carbs: float | None = None
    kbju_status: str = "missing"
    price_per_kg: float | None = None
    price_per_liter: float | None = None
    price_per_piece: float | None = None
    amount_text: str | None = None
    amount_is_exact: bool = True


def convert_unit(amount: float, from_unit: str, to_unit: str) -> float:
    if from_unit == to_unit:
        return amount
    if from_unit in WEIGHT_UNITS and to_unit in WEIGHT_UNITS:
        return amount * UNIT_TO_GRAMS[from_unit] / UNIT_TO_GRAMS[to_unit]
    if from_unit in VOLUME_UNITS and to_unit in VOLUME_UNITS:
        return amount * UNIT_TO_ML[from_unit] / UNIT_TO_ML[to_unit]
    raise ValueError(f"Cannot convert {from_unit} -> {to_unit}")


def to_grams(amount: float, unit: str) -> float:
    if unit in WEIGHT_UNITS:
        return convert_unit(amount, unit, "g")
    if unit in VOLUME_UNITS:
        return convert_unit(amount, unit, "ml")
    if unit in PIECE_UNITS:
        return amount
    raise ValueError(f"Unknown unit: {unit}")


def scale_ingredients(
    ingredients: Iterable[Ingredient],
    base_servings: int,
    target_servings: int,
) -> list[Ingredient]:
    if base_servings <= 0 or target_servings <= 0:
        raise ValueError("Servings must be positive")

    k = target_servings / base_servings
    result = []

    for i in ingredients:
        if not i.amount_is_exact:
            new_amount = i.amount
        else:
            new_amount = i.amount * k

            if i.unit in PIECE_UNITS:
                new_amount = round(new_amount)
                if new_amount == 0:
                    new_amount = 1

        result.append(
            Ingredient(
                product_id=i.product_id,
                name=i.name,
                amount=round(new_amount, 2),
                unit=i.unit,
                calories=i.calories,
                proteins=i.proteins,
                fats=i.fats,
                carbs=i.carbs,
                kbju_status=i.kbju_status,
                price_per_kg=i.price_per_kg,
                price_per_liter=i.price_per_liter,
                price_per_piece=i.price_per_piece,
                amount_text=i.amount_text,
                amount_is_exact=i.amount_is_exact,
            )
        )

    return result


NUTRIENTS = ("calories", "proteins", "fats", "carbs")

NUTRIENT_LABELS = {
    "calories": "ккал",
    "proteins": "белки",
    "fats": "жиры",
    "carbs": "углеводы",
}


def _ingredient_factor(i: Ingredient) -> float | None:
    """Множитель для расчёта КБЖУ на 100 г."""
    if not i.amount_is_exact:
        return None

    if i.unit in WEIGHT_UNITS:
        return to_grams(i.amount, i.unit) / 100.0

    return None


def calc_recipe_kbju(ingredients: Iterable[Ingredient]) -> dict:
    """Считает только те значения КБЖУ, которые можно достоверно определить."""
    ingredients = list(ingredients)

    known = {key: 0.0 for key in NUTRIENTS}
    missing_components: set[str] = set()
    missing_ingredients: list[str] = []

    fully_covered = 0
    total_mass_grams = 0.0
    mass_unknown = False

    for ingredient in ingredients:
        factor = _ingredient_factor(ingredient)

        if ingredient.unit in WEIGHT_UNITS and ingredient.amount_is_exact:
            total_mass_grams += to_grams(ingredient.amount, ingredient.unit)
        else:
            mass_unknown = True

        ingredient_missing = []
        reasons = []

        if not ingredient.amount_is_exact:
            ingredient_missing.extend(NUTRIENTS)
            reasons.append("количество задано диапазоном или приблизительно")
        elif factor is None:
            ingredient_missing.extend(NUTRIENTS)
            reasons.append(
                "единицу измерения нельзя надёжно перевести в массу"
            )
        else:
            for key in NUTRIENTS:
                value = getattr(ingredient, key)

                if value is None:
                    ingredient_missing.append(key)
                else:
                    known[key] += value * factor

        absent = [
            NUTRIENT_LABELS[key]
            for key in NUTRIENTS
            if key in ingredient_missing
            and getattr(ingredient, key) is None
        ]

        if absent:
            reasons.append("нет данных: " + ", ".join(absent))

        if ingredient_missing:
            missing_components.update(ingredient_missing)
            missing_ingredients.append(
                f"{ingredient.name}: " + "; ".join(reasons)
            )
        else:
            fully_covered += 1

    total_count = len(ingredients)
    coverage = (
        round(fully_covered / total_count * 100, 1)
        if total_count
        else 100.0
    )

    result = {
        key: (
            round(known[key], 2)
            if key not in missing_components
            else None
        )
        for key in NUTRIENTS
    }

    result.update({
        f"known_{key}": round(known[key], 2)
        for key in NUTRIENTS
    })

    result.update({
        "accuracy": (
            "exact" if not missing_components else "approximate"
        ),
        "coverage_percent": coverage,
        "missing_components": [
            NUTRIENT_LABELS[key]
            for key in NUTRIENTS
            if key in missing_components
        ],
        "missing_ingredients": missing_ingredients,
        "total_mass_grams": (
            round(total_mass_grams, 2)
            if not mass_unknown
            else None
        ),
    })

    return result


def calc_per_100g(kbju: dict) -> dict:
    mass = kbju.get("total_mass_grams")

    if mass is None or mass <= 0:
        result = {key: None for key in NUTRIENTS}
        result.update({
            f"known_{key}": None
            for key in NUTRIENTS
        })
        result.update({
            "accuracy": "approximate",
            "coverage_percent": 0.0,
            "missing_components": [
                NUTRIENT_LABELS[key]
                for key in NUTRIENTS
            ],
            "missing_ingredients": (
                kbju.get("missing_ingredients", [])
                + [
                    "Неизвестна общая масса рецепта: "
                    "есть ингредиенты без точной массы"
                ]
            ),
        })
        return result

    factor = 100.0 / mass
    result = {}

    for key in NUTRIENTS:
        value = kbju.get(key)
        known_value = kbju.get(f"known_{key}")

        result[key] = (
            round(value * factor, 2)
            if value is not None
            else None
        )
        result[f"known_{key}"] = (
            round(known_value * factor, 2)
            if known_value is not None
            else None
        )

    result.update({
        "accuracy": kbju["accuracy"],
        "coverage_percent": kbju.get("coverage_percent", 100.0),
        "missing_components": kbju.get("missing_components", []),
        "missing_ingredients": kbju.get("missing_ingredients", []),
    })

    return result


def calc_per_serving(kbju: dict, servings: int) -> dict:
    if servings <= 0:
        raise ValueError("Servings must be positive")

    result = {}

    for key in NUTRIENTS:
        value = kbju.get(key)
        known_value = kbju.get(f"known_{key}", value)

        result[key] = (
            round(value / servings, 2)
            if value is not None
            else None
        )
        result[f"known_{key}"] = (
            round(known_value / servings, 2)
            if known_value is not None
            else None
        )

    result.update({
        "accuracy": kbju["accuracy"],
        "coverage_percent": kbju.get("coverage_percent", 100.0),
        "missing_components": kbju.get("missing_components", []),
        "missing_ingredients": kbju.get("missing_ingredients", []),
    })

    return result


def calc_recipe_cost(ingredients: Iterable[Ingredient]) -> dict:
    total = 0.0
    missing_prices = []
    known_ingredients = 0
    ingredient_count = 0

    for ingredient in ingredients:
        ingredient_count += 1
        if not ingredient.amount_is_exact:
            missing_prices.append(ingredient.name)
            continue

        if ingredient.unit in WEIGHT_UNITS and ingredient.price_per_kg is not None:
            total += ingredient.price_per_kg * to_grams(ingredient.amount, ingredient.unit) / 1000.0
        elif ingredient.unit in VOLUME_UNITS and ingredient.price_per_liter is not None:
            milliliters = convert_unit(ingredient.amount, ingredient.unit, "ml")
            total += ingredient.price_per_liter * milliliters / 1000.0
        elif ingredient.unit in PIECE_UNITS and ingredient.price_per_piece is not None:
            total += ingredient.price_per_piece * ingredient.amount
        else:
            missing_prices.append(ingredient.name)
            continue
        known_ingredients += 1

    return {
        "total_cost": round(total, 2) if known_ingredients else None,
        "currency": "RUB",
        "missing_prices": missing_prices,
        "known_ingredients": known_ingredients,
        "ingredient_count": ingredient_count,
        "coverage_percent": round(known_ingredients / ingredient_count * 100, 1) if ingredient_count else 100.0,
    }

