from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, model_validator


class ShoppingListCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    recipe_ids: list[int] = Field(..., min_length=1, max_length=100)
    servings: dict[int, int] | None = None

    @model_validator(mode="after")
    def validate_servings(self):
        if any(recipe_id <= 0 for recipe_id in self.recipe_ids):
            raise ValueError("recipe_ids must be positive")
        if self.servings and any(value <= 0 or value > 1000 for value in self.servings.values()):
            raise ValueError("servings must be between 1 and 1000")
        return self


class ShoppingListItemOut(BaseModel):
    id: int
    product_id: int
    product_name: str
    amount: float
    unit: str
    cost: float | None = None
    price_source: str | None = None
    observed_at: datetime | None = None
    store_name: str | None = None
    store_product_name: str | None = None
    manufacturer: str | None = None
    selected_store_product_id: int | None = None
    offered_store_product_id: int | None = None
    price_override: float | None = None
    price_basis_unit: str | None = None
    catalog_price_per_basis: float | None = None
    package_amount: float | None = None
    package_unit: str | None = None
    package_price: float | None = None
    package_price_override: float | None = None
    package_amount_override: float | None = None
    package_unit_override: str | None = None
    package_amount_in_recipe_unit_override: float | None = None
    price_mode: str = "basis"
    package_count: int | None = None


class ShoppingListOut(BaseModel):
    id: int
    title: str
    created_at: datetime
    items: list[ShoppingListItemOut]
    total_cost: float | None
    missing_prices: list[str]
    known_prices: int = 0
    item_count: int = 0
    coverage_percent: float = 100.0
    
    # Новые поля для КБЖУ
    total_calories: float = 0.0
    total_proteins: float = 0.0
    total_fats: float = 0.0
    total_carbs: float = 0.0

    model_config = ConfigDict(from_attributes=True)


class ShoppingCartItemUpdate(BaseModel):
    amount: float | None = Field(default=None, gt=0, le=100000, allow_inf_nan=False)
    unit: str | None = Field(default=None, pattern="^(g|kg|ml|l|pcs|cup|clove|bunch|tbsp|tsp|pinch|to_taste)$")
    price_override: float | None = Field(default=None, ge=0, le=10000000, allow_inf_nan=False)
    package_price_override: float | None = Field(default=None, ge=0, le=10000000, allow_inf_nan=False)
    package_amount_override: float | None = Field(default=None, gt=0, le=10000000, allow_inf_nan=False)
    package_unit_override: str | None = Field(default=None, pattern="^(г|кг|мл|л|шт)$")
    package_amount_in_recipe_unit_override: float | None = Field(default=None, gt=0, le=10000000, allow_inf_nan=False)
    price_mode: str | None = Field(default=None, pattern="^(basis|package)$")
    selected_store_product_id: int | None = Field(default=None, gt=0)
