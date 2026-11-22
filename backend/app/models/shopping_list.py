from datetime import datetime
from sqlalchemy import String, Float, Boolean, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base

class ShoppingList(Base):
    __tablename__ = "shopping_lists"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

class ShoppingListItem(Base):
    __tablename__ = "shopping_list_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    shopping_list_id: Mapped[int] = mapped_column(ForeignKey("shopping_lists.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)

    amount: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(10))
    bought: Mapped[bool] = mapped_column(Boolean, default=False)
    price_override: Mapped[float | None] = mapped_column(Float, nullable=True)
    package_price_override: Mapped[float | None] = mapped_column(Float, nullable=True)
    package_amount_override: Mapped[float | None] = mapped_column(Float, nullable=True)
    package_unit_override: Mapped[str | None] = mapped_column(String(20), nullable=True)
    price_mode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    selected_store_product_id: Mapped[int | None] = mapped_column(
        ForeignKey("store_products.id", ondelete="SET NULL"), nullable=True
    )
