from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator


class ProductBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    category: str | None = Field(default=None, max_length=100)
    category_id: int | None = Field(default=None, gt=0)
    category_name: str | None = None
    base_name: str | None = Field(default=None, max_length=255)
    variation: str | None = Field(default=None, max_length=255)
    calories: float | None = Field(default=None, ge=0, le=10000, allow_inf_nan=False)
    proteins: float | None = Field(default=None, ge=0, le=1000, allow_inf_nan=False)
    fats: float | None = Field(default=None, ge=0, le=1000, allow_inf_nan=False)
    carbs: float | None = Field(default=None, ge=0, le=1000, allow_inf_nan=False)
    attributes: dict = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Название продукта не может быть пустым")
        return value


class ProductCreate(ProductBase):
    source: str = Field(default="manual", max_length=50)


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    category_id: int | None = Field(default=None, gt=0)
    base_name: str | None = Field(default=None, max_length=255)
    variation: str | None = Field(default=None, max_length=255)
    calories: float | None = Field(default=None, ge=0, le=10000, allow_inf_nan=False)
    proteins: float | None = Field(default=None, ge=0, le=1000, allow_inf_nan=False)
    fats: float | None = Field(default=None, ge=0, le=1000, allow_inf_nan=False)
    carbs: float | None = Field(default=None, ge=0, le=1000, allow_inf_nan=False)
    attributes: dict | None = None
    verified: bool | None = None

    @field_validator("name")
    @classmethod
    def strip_optional_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("Название продукта не может быть пустым")
        return value

    @field_validator("base_name", "variation")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else value


class ProductOut(ProductBase):
    id: int
    kbju_status: str
    source: str
    source_id: str | None = None
    verified: bool
    status: str = "active"
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ProductCategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

    @field_validator("name", "slug")
    @classmethod
    def strip_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Значение не может быть пустым")
        return value


class ProductCategoryOut(BaseModel):
    id: int
    name: str
    slug: str
    model_config = ConfigDict(from_attributes=True)


class ProductAliasCreate(BaseModel):
    alias: str = Field(..., min_length=1, max_length=255)

    @field_validator("alias")
    @classmethod
    def strip_alias(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Синоним не может быть пустым")
        return value


class ProductAliasOut(BaseModel):
    id: int
    product_id: int
    alias: str
    model_config = ConfigDict(from_attributes=True)


class StoreProductCreate(BaseModel):
    universal_product_id: int = Field(..., gt=0)
    name: str = Field(..., min_length=1, max_length=500)
    manufacturer: str | None = Field(default=None, max_length=255)
    brand: str | None = Field(default=None, max_length=255)
    store_name: str = Field(..., min_length=1, max_length=120)
    package_amount: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    package_unit: str | None = Field(default=None, pattern="^(г|кг|мл|л|шт)$")
    barcode: str | None = Field(default=None, max_length=32)
    product_url: str | None = Field(default=None, max_length=1000)
    region: str | None = Field(default=None, max_length=120)
    attributes: dict = Field(default_factory=dict)
    source: str = Field(default="manual", max_length=50)
    source_id: str | None = Field(default=None, max_length=120)

    @field_validator("name", "store_name")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Поле не может быть пустым")
        return value

    @model_validator(mode="after")
    def validate_package(self):
        if (self.package_amount is None) != (self.package_unit is None):
            raise ValueError("Масса/объём упаковки и единица измерения должны задаваться вместе")
        return self


class StoreProductOut(BaseModel):
    id: int
    universal_product_id: int
    name: str
    manufacturer: str | None
    brand: str | None
    store_name: str
    package_amount: float | None
    package_unit: str | None
    barcode: str | None
    product_url: str | None
    region: str | None
    attributes: dict
    status: str
    source: str
    source_id: str | None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class StoreProductPriceCreate(BaseModel):
    price: float = Field(..., gt=0, allow_inf_nan=False)
    currency: str = Field(default="RUB", min_length=3, max_length=3)
    region: str | None = Field(default=None, max_length=120)
    source: str = Field(default="manual", max_length=50)


class StoreProductPriceOut(BaseModel):
    id: int
    store_product_id: int
    price: float
    currency: str
    region: str | None
    observed_at: datetime
    source: str
    model_config = ConfigDict(from_attributes=True)


class ProductStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(active|inactive|archived)$")


class ProductUnitPriceUpdate(BaseModel):
    price_per_kg: float | None = Field(default=None, ge=0, le=10000000, allow_inf_nan=False)
    price_per_liter: float | None = Field(default=None, ge=0, le=10000000, allow_inf_nan=False)
    price_per_piece: float | None = Field(default=None, ge=0, le=10000000, allow_inf_nan=False)


class ProductUnitPricesOut(BaseModel):
    product_id: int
    price_per_kg: float | None = None
    price_per_liter: float | None = None
    price_per_piece: float | None = None
    updated_at: datetime | None = None
