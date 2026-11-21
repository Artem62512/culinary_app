from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models import Product, StoreProduct, StoreProductPrice
from app.api.shopping_lists import add_to_cart, save_cart_price_to_history, update_cart_item
from app.schemas.shopping_list import ShoppingCartItemUpdate


@pytest.fixture
def db_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_cart_override_is_independent_from_catalog_price(db_session):
    product = Product(name="Молоко 3,2%", status="active")
    db_session.add(product)
    db_session.flush()
    offer = StoreProduct(
        universal_product_id=product.id, name="Молоко бренда, 1 л",
        store_name="ВкусВилл", manufacturer="Производитель",
        package_amount=1, package_unit="л", status="active",
    )
    db_session.add(offer)
    db_session.flush()
    db_session.add(StoreProductPrice(
        store_product_id=offer.id, price=120, currency="RUB", source="vkusvill",
    ))
    db_session.commit()

    cart = add_to_cart(product.id, amount=250, unit="ml", db=db_session)
    item = cart.items[0]
    assert item.cost == 30
    assert item.store_name == "ВкусВилл"
    assert item.catalog_price_per_basis == 120

    updated = update_cart_item(
        item.id,
        ShoppingCartItemUpdate(price_override=200, selected_store_product_id=offer.id),
        db_session,
    )
    assert updated.items[0].cost == 50
    assert updated.items[0].price_source == "Изменена в корзине"
    assert db_session.query(StoreProductPrice).one().price == 120

    cleared = update_cart_item(
        item.id,
        ShoppingCartItemUpdate(price_override=None, selected_store_product_id=None),
        db_session,
    )
    assert cleared.items[0].cost == 30


def test_cart_keeps_distinct_incompatible_units_separate(db_session):
    product = Product(name="Продукт", status="active")
    db_session.add(product)
    db_session.commit()

    add_to_cart(product.id, amount=1, unit="cup", db=db_session)
    cart = add_to_cart(product.id, amount=2, unit="tbsp", db=db_session)

    assert [(item.amount, item.unit) for item in cart.items] == [(1, "cup"), (2, "tbsp")]
    assert cart.total_cost is None
    assert cart.missing_prices == ["Продукт", "Продукт"]


def test_cart_rejects_offer_from_another_universal_product(db_session):
    product = Product(name="Молоко")
    other = Product(name="Мука")
    db_session.add_all([product, other])
    db_session.flush()
    offer = StoreProduct(
        universal_product_id=other.id, name="Мука 1 кг",
        store_name="Магазин", package_amount=1, package_unit="кг",
    )
    db_session.add(offer)
    db_session.commit()

    cart = add_to_cart(product.id, amount=1, unit="l", db=db_session)
    with pytest.raises(HTTPException) as exc:
        update_cart_item(
            cart.items[0].id,
            ShoppingCartItemUpdate(selected_store_product_id=offer.id),
            db_session,
        )
    assert exc.value.status_code == 422


def test_saving_cart_price_appends_history_only_when_requested(db_session):
    product = Product(name="Молоко 3,2%", status="active")
    db_session.add(product)
    db_session.flush()
    offer = StoreProduct(
        universal_product_id=product.id, name="Молоко, 1 л",
        store_name="ВкусВилл", package_amount=1, package_unit="л",
    )
    db_session.add(offer)
    db_session.flush()
    original = StoreProductPrice(
        store_product_id=offer.id, price=120, currency="RUB", source="vkusvill",
    )
    db_session.add(original)
    db_session.commit()

    cart = add_to_cart(product.id, amount=500, unit="ml", db=db_session)
    item = cart.items[0]
    update_cart_item(item.id, ShoppingCartItemUpdate(price_override=200), db_session)
    assert db_session.query(StoreProductPrice).count() == 1

    save_cart_price_to_history(item.id, db_session)
    history = db_session.query(StoreProductPrice).order_by(StoreProductPrice.id).all()
    assert len(history) == 2
    assert history[1].price == 200
    assert history[1].source == "manual"
