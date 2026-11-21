from datetime import datetime
from sqlalchemy import String, Float, Boolean, DateTime, ForeignKey, func, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    normalized_name: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    name_en: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)  # legacy display/category field
    category_id: Mapped[int | None] = mapped_column(ForeignKey("product_categories.id", ondelete="SET NULL"), nullable=True, index=True)
    category_ref = relationship("ProductCategory", lazy="joined")

    # Поля для группировки
    base_name: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    variation: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Кулинарно значимые характеристики (вид обработки, жирность, сорт и т. п.)
    attributes: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False, index=True)

    # КБЖУ на 100 г
    calories: Mapped[float | None] = mapped_column(Float, nullable=True)
    proteins: Mapped[float | None] = mapped_column(Float, nullable=True)
    fats: Mapped[float | None] = mapped_column(Float, nullable=True)
    carbs: Mapped[float | None] = mapped_column(Float, nullable=True)

    # full | partial | missing
    kbju_status: Mapped[str] = mapped_column(String(10), default="missing", index=True)

    source: Mapped[str] = mapped_column(String(50), default="manual")  # manual | vkusvill | ...
    source_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    @property
    def category_name(self) -> str | None:
        return self.category_ref.name if self.category_ref else self.category
