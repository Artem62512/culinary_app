from datetime import datetime
from sqlalchemy import String, Float, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base

class ProductPrice(Base):
    __tablename__ = "product_prices"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)

    price: Mapped[float | None] = mapped_column(Float, nullable=True)           # legacy: цена упаковки
    package_weight_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_per_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_per_liter: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_per_piece: Mapped[float | None] = mapped_column(Float, nullable=True)

    source: Mapped[str] = mapped_column(String(50), default="manual")  # manual | vkusvill | lavka | pyaterochka
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
