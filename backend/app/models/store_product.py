from datetime import datetime
from sqlalchemy import String, Float, DateTime, ForeignKey, JSON, func, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class StoreProduct(Base):
    """A concrete sellable SKU linked to a universal recipe ingredient."""
    __tablename__ = "store_products"
    __table_args__ = (
        Index("ix_store_products_universal_product_id", "universal_product_id"),
        Index("ix_store_products_store_name", "store_name"),
        Index("ix_store_products_barcode", "barcode"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    universal_product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    manufacturer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    brand: Mapped[str | None] = mapped_column(String(255), nullable=True)
    store_name: Mapped[str] = mapped_column(String(120), nullable=False)
    package_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    package_unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    barcode: Mapped[str | None] = mapped_column(String(32), nullable=True)
    product_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    region: Mapped[str | None] = mapped_column(String(120), nullable=True)
    attributes: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="manual")
    source_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    universal_product = relationship("Product", lazy="joined")


class StoreProductPrice(Base):
    """Price observation for a concrete store SKU; history is append-only."""
    __tablename__ = "store_product_prices"

    id: Mapped[int] = mapped_column(primary_key=True)
    store_product_id: Mapped[int] = mapped_column(
        ForeignKey("store_products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    price: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="RUB")
    region: Mapped[str | None] = mapped_column(String(120), nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="manual")

    store_product = relationship("StoreProduct", backref="price_history")
