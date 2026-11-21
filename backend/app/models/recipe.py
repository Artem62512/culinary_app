
from datetime import datetime
from sqlalchemy import String, Integer, Float, ForeignKey, DateTime, Boolean, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class Recipe(Base):
    __tablename__ = "recipes"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    base_servings: Mapped[int] = mapped_column(Integer, default=1)
    instructions: Mapped[str | None] = mapped_column(String(10000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    ingredients: Mapped[list["RecipeIngredient"]] = relationship(back_populates="recipe", cascade="all, delete-orphan")


class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredients"

    id: Mapped[int] = mapped_column(primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)

    amount: Mapped[float] = mapped_column(Float)
    amount_text: Mapped[str | None] = mapped_column(String(100), nullable=True)
    amount_is_exact: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("1"),
    )

    unit: Mapped[str] = mapped_column(String(10))
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)

    recipe: Mapped["Recipe"] = relationship(back_populates="ingredients")
