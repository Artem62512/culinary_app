
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, model_validator


ALLOWED_UNITS = {
    "g", "kg", "ml", "l", "pcs",
    "cup", "clove", "bunch",
    "tbsp", "tsp", "pinch",
    "to_taste",
}


class RecipeIngredientIn(BaseModel):
    product_id: int = Field(..., gt=0)

    amount: float = Field(..., ge=0, le=100000, allow_inf_nan=False)
    amount_text: str | None = Field(default=None, max_length=100)
    amount_is_exact: bool = True

    unit: str
    note: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def validate_ingredient(self):
        if self.unit not in ALLOWED_UNITS:
            raise ValueError(f"Недопустимая единица измерения: {self.unit}")

        if self.amount_is_exact and self.amount <= 0:
            raise ValueError("Точное количество должно быть больше нуля")

        if not self.amount_is_exact and self.amount != 0:
            raise ValueError(
                "Для неточного количества amount должен быть равен 0"
            )

        if self.amount_text is not None:
            self.amount_text = self.amount_text.strip()
            if not self.amount_text:
                self.amount_text = None

        if not self.amount_is_exact and not self.amount_text:
            raise ValueError(
                "Для диапазона или неточного количества укажите исходный текст"
            )

        if self.unit == "to_taste" and self.amount_is_exact:
            raise ValueError("Единица «по вкусу» не может иметь точное количество")

        if self.unit == "to_taste" and not self.amount_text:
            self.amount_text = "по вкусу"

        return self

class RecipeIngredientOut(BaseModel):
    id: int
    product_id: int
    product_name: str

    amount: float
    amount_text: str | None = None
    amount_is_exact: bool = True

    unit: str
    note: str | None = None


class RecipeCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    base_servings: int = Field(..., gt=0)
    instructions: str | None = Field(default=None, max_length=10000)
    ingredients: list[RecipeIngredientIn] = Field(..., min_length=1)


class RecipeOut(BaseModel):
    id: int
    title: str
    description: str | None
    base_servings: int
    instructions: str | None
    created_at: datetime
    ingredients: list[RecipeIngredientOut]

    model_config = ConfigDict(from_attributes=True)


class NutritionOut(BaseModel):
    calories: float | None = None
    proteins: float | None = None
    fats: float | None = None
    carbs: float | None = None
    known_calories: float | None = None
    known_proteins: float | None = None
    known_fats: float | None = None
    known_carbs: float | None = None
    accuracy: str
    coverage_percent: float = 100.0
    missing_components: list[str] = Field(default_factory=list)
    missing_ingredients: list[str] = Field(default_factory=list)


class CostOut(BaseModel):
    total_cost: float | None
    currency: str
    missing_prices: list[str]
    known_ingredients: int = 0
    ingredient_count: int = 0
    coverage_percent: float = 100.0


class CalculationOut(BaseModel):
    recipe_id: int
    recipe_title: str
    target_servings: int
    ingredients: list[RecipeIngredientOut]
    total: NutritionOut
    per_serving: NutritionOut
    per_100g: NutritionOut
    cost: CostOut
