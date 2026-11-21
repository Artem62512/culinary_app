from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models import Product, ProductAlias, ProductCategory
from app.api.products import (
    add_product_alias, create_catalog_category, create_product,
    list_catalog_categories, list_groups, list_products, catalog_quality_report, update_product,
)
from app.schemas.product import ProductAliasCreate, ProductCategoryCreate, ProductCreate, ProductUpdate


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


def test_catalog_categories_and_product_assignment(db_session):
    category = create_catalog_category(ProductCategoryCreate(name="Молочные продукты", slug="dairy"), db_session)
    product = create_product(ProductCreate(name="Кефир 2,5%", category_id=category.id), db_session)
    assert product.category_id == category.id
    assert product.category == "Молочные продукты"
    assert [item.name for item in list_catalog_categories(db_session)] == ["Молочные продукты"]


def test_category_duplicate_is_rejected(db_session):
    create_catalog_category(ProductCategoryCreate(name="Овощи", slug="vegetables"), db_session)
    with pytest.raises(HTTPException) as exc:
        create_catalog_category(ProductCategoryCreate(name="Овощи", slug="veg"), db_session)
    assert exc.value.status_code == 409


def test_alias_search_is_case_and_yo_insensitive(db_session):
    product = Product(name="Творог", base_name="Творог", category="Молочные продукты")
    db_session.add(product)
    db_session.commit()
    add_product_alias(product.id, ProductAliasCreate(alias="творожок"), db_session)

    result = list_products(q="ТВОРОЖОК", category_id=None, limit=100, offset=0, db=db_session)
    assert [item.id for item in result] == [product.id]


def test_exact_match_supports_alias_and_rejects_ambiguous_name(db_session):
    from app.api.products import match_universal_product
    from app.models import ProductAlias

    product = Product(name="Творог", base_name="Творог", status="active")
    db_session.add(product)
    db_session.flush()
    db_session.add(ProductAlias(
        product_id=product.id,
        alias="творожок",
        normalized_alias="творожок",
    ))
    db_session.commit()

    assert match_universal_product("ТВОРОЖОК", db_session).id == product.id
    assert match_universal_product("творог", db_session).id == product.id

    db_session.add_all([
        Product(name="Молоко 2,5%", base_name="Молоко", status="active"),
        Product(name="Молоко 3,2%", base_name="Молоко", status="active"),
    ])
    db_session.commit()
    assert match_universal_product("Молоко", db_session) is None


def test_alias_cannot_be_duplicated_or_conflict_with_product_name(db_session):
    first = Product(name="Кефир")
    second = Product(name="Ряженка")
    db_session.add_all([first, second])
    db_session.commit()
    add_product_alias(first.id, ProductAliasCreate(alias="простокваша"), db_session)

    with pytest.raises(HTTPException) as duplicate:
        add_product_alias(second.id, ProductAliasCreate(alias="ПРОСТОКВАША"), db_session)
    assert duplicate.value.status_code == 409

    with pytest.raises(HTTPException) as conflict:
        add_product_alias(first.id, ProductAliasCreate(alias="Ряженка"), db_session)
    assert conflict.value.status_code == 409


def test_product_duplicate_name_is_rejected(db_session):
    db_session.add(Product(name="Молоко 3,2%"))
    db_session.commit()
    with pytest.raises(HTTPException) as exc:
        create_product(ProductCreate(name="  МОЛОКО 3,2%  "), db_session)
    assert exc.value.status_code == 409


def test_group_filter_uses_normalized_category_relation(db_session):
    category = ProductCategory(name="Хлеб и выпечка", slug="bakery")
    db_session.add(category)
    db_session.flush()
    db_session.add(Product(name="Хлеб цельнозерновой", base_name="Хлеб", category_id=category.id))
    db_session.commit()
    result = list_groups(category="Хлеб и выпечка", q=None, db=db_session)
    assert result == [{"base_name": "Хлеб", "aliases": []}]


def test_search_matches_alias_using_partial_query(db_session):
    product = Product(name="Йогурт натуральный", base_name="Йогурт")
    db_session.add(product)
    db_session.commit()
    add_product_alias(product.id, ProductAliasCreate(alias="простокваша"), db_session)
    result = list_products(q="просток", category_id=None, limit=100, offset=0, db=db_session)
    assert [item.id for item in result] == [product.id]


def test_catalog_http_endpoints_serialize_normalized_category_and_alias(db_session):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api.products import router as products_router
    from app.core.database import get_db
    from app.core.security import require_auth

    category = ProductCategory(name="Молочные продукты", slug="dairy")
    db_session.add(category)
    db_session.flush()
    product = Product(name="Кефир 2,5%", category="молоко", category_id=category.id, base_name="Кефир")
    db_session.add(product)
    db_session.commit()
    add_product_alias(product.id, ProductAliasCreate(alias="кисломолочный напиток"), db_session)

    app = FastAPI()
    app.include_router(products_router)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[require_auth] = lambda: "owner"
    client = TestClient(app)

    categories_response = client.get("/products/catalog/categories")
    assert categories_response.status_code == 200
    assert categories_response.json()[0]["slug"] == "dairy"

    products_response = client.get("/products?q=КИСЛОМОЛОЧНЫЙ")
    assert products_response.status_code == 200
    assert products_response.json()[0]["category_name"] == "Молочные продукты"
    assert products_response.json()[0]["id"] == product.id


def test_catalog_quality_report_detects_duplicates_and_partial_kbju(db_session):
    category = ProductCategory(name="Бакалея", slug="grocery")
    db_session.add(category)
    db_session.flush()
    db_session.add_all([
        Product(name="Мука пшеничная", category_id=category.id, calories=340, proteins=10,
                fats=1, carbs=70, kbju_status="full", verified=True),
        Product(name="МУКА ПШЕНИЧНАЯ", category_id=category.id, calories=340, proteins=10,
                fats=1, carbs=70, kbju_status="full", verified=True),
        Product(name="Сахар тростниковый", category_id=category.id, calories=399,
                proteins=None, fats=None, carbs=99, kbju_status="partial", verified=False),
    ])
    db_session.commit()

    report = catalog_quality_report(db_session)
    assert report["summary"]["products_total"] == 3
    assert report["summary"]["duplicate_name_groups"] == 1
    assert report["summary"]["exact_duplicate_clusters"] == 1
    assert report["summary"]["kbju_partial"] == 1
    assert report["summary"]["unverified"] == 1
    assert report["exact_duplicate_groups"][0]["clusters"] == [[1, 2]]


def test_normalized_name_search_is_case_insensitive_and_partial(db_session):
    product = Product(name="КАРТОФЕЛЬ МОЛОДОЙ", normalized_name="картофель молодой", status="active")
    db_session.add(product)
    db_session.commit()
    result = list_products(q="Картоф", category_id=None, limit=100, offset=0, db=db_session)
    assert [item.id for item in result] == [product.id]


def test_store_product_is_separate_and_linked_to_universal_product(db_session):
    from app.api.products import create_store_product, add_store_product_price, list_store_product_prices
    from app.models import StoreProduct
    from app.schemas.product import StoreProductCreate, StoreProductPriceCreate

    universal = Product(name="Молоко 3,2%", normalized_name="молоко 3 2", status="active")
    db_session.add(universal)
    db_session.commit()

    store_item = create_store_product(StoreProductCreate(
        universal_product_id=universal.id,
        name="Молоко Простоквашино 3,2%, 930 мл",
        manufacturer="Данон",
        brand="Простоквашино",
        store_name="Пятёрочка",
        package_amount=930,
        package_unit="мл",
        barcode="4600000000000",
        region="Москва",
    ), db_session)
    assert store_item.universal_product_id == universal.id
    assert store_item.brand == "Простоквашино"
    assert db_session.query(Product).count() == 1

    created_price = add_store_product_price(
        store_item.id,
        StoreProductPriceCreate(price=119, currency="RUB", region="Москва", source="manual"),
        db_session,
    )
    history = list_store_product_prices(store_item.id, db_session)
    assert created_price.price == 119
    assert len(history) == 1
    assert history[0].store_product_id == store_item.id


def test_multi_product_selection_preserves_order_and_deduplicates(db_session):
    from app.api.products import validate_product_selection
    first = Product(name="Картофель", status="active")
    second = Product(name="Морковь", status="active")
    db_session.add_all([first, second])
    db_session.commit()
    result = validate_product_selection([second.id, first.id, second.id], db_session)
    assert [item.id for item in result] == [second.id, first.id]


def test_catalog_seed_is_idempotent(db_session):
    from scripts.seed_catalog import seed
    first = seed(db_session)
    second = seed(db_session)
    assert first["products_added"] > 500
    assert first["aliases_added"] > 50
    assert second["products_added"] == 0
    assert second["aliases_added"] == 0
    assert second["categories_total"] == 13


def test_store_product_price_is_available_to_universal_product_cost_calculation(db_session):
    from app.models import StoreProduct, StoreProductPrice
    from app.services.pricing import get_latest_price_per_kg
    universal = Product(name="Рис басмати", status="active")
    db_session.add(universal)
    db_session.flush()
    sku = StoreProduct(
        universal_product_id=universal.id,
        name="Рис басмати 900 г",
        store_name="Магазин",
        package_amount=900,
        package_unit="г",
        status="active",
    )
    db_session.add(sku)
    db_session.flush()
    db_session.add(StoreProductPrice(store_product_id=sku.id, price=180, currency="RUB", source="manual"))
    db_session.commit()
    assert get_latest_price_per_kg(db_session, universal.id) == 200


def test_store_offer_priority_and_volume_piece_normalization(db_session):
    from app.models import StoreProduct, StoreProductPrice
    from app.services.pricing import get_latest_price_quote

    milk = Product(name="Молоко", status="active")
    egg = Product(name="Яйцо", status="active")
    db_session.add_all([milk, egg])
    db_session.flush()
    db_session.add_all([
        StoreProduct(id=1, universal_product_id=milk.id, name="Молоко, 1 л",
                     store_name="Пятёрочка", package_amount=1, package_unit="л"),
        StoreProduct(id=2, universal_product_id=milk.id, name="Молоко, 1 л",
                     store_name="ВкусВилл", package_amount=1, package_unit="л"),
        StoreProduct(id=3, universal_product_id=egg.id, name="Яйцо, 10 шт",
                     store_name="Пятёрочка", package_amount=10, package_unit="шт"),
    ])
    db_session.flush()
    db_session.add_all([
        StoreProductPrice(store_product_id=1, price=90, currency="RUB", source="manual"),
        StoreProductPrice(store_product_id=2, price=140, currency="RUB", source="vkusvill"),
        StoreProductPrice(store_product_id=3, price=50, currency="RUB", source="manual"),
    ])
    db_session.commit()

    milk_quote = get_latest_price_quote(db_session, milk.id)
    egg_quote = get_latest_price_quote(db_session, egg.id)
    assert milk_quote["store_name"] == "ВкусВилл"
    assert milk_quote["price_per_liter"] == 140
    assert egg_quote["price_per_piece"] == 5


def test_vkusvill_importer_reads_piece_package_size():
    from scripts.import_vkusvill import extract_package

    assert extract_package("Яйца куриные, 10 шт.") == (10, "шт")


def test_store_product_http_endpoints_and_multi_selection(db_session):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api.products import router as products_router
    from app.core.database import get_db
    from app.core.security import require_auth

    universal = Product(name="Молоко 3,2%", normalized_name="молоко 3 2", status="active")
    db_session.add(universal)
    db_session.commit()
    app = FastAPI()
    app.include_router(products_router)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[require_auth] = lambda: "owner"
    client = TestClient(app)

    created = client.post("/products/store-products", json={
        "universal_product_id": universal.id,
        "name": "Молоко бренд 3,2%, 1 л",
        "store_name": "Супермаркет",
        "package_amount": 1,
        "package_unit": "л",
        "attributes": {"fat_percent": 3.2},
    })
    assert created.status_code == 201
    assert created.json()["universal_product_id"] == universal.id
    assert created.json()["attributes"]["fat_percent"] == 3.2

    listed = client.get(f"/products/store-products?universal_product_id={universal.id}")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    selected = client.post("/products/catalog/selection", json=[universal.id, universal.id])
    assert selected.status_code == 200
    assert [row["id"] for row in selected.json()] == [universal.id]


def test_product_update_saves_manual_kbju_and_recalculates_status(db_session):
    product = Product(name="Новый продукт", kbju_status="missing")
    db_session.add(product)
    db_session.commit()

    updated = update_product(
        product.id,
        ProductUpdate(calories=120, proteins=3.5, fats=2.0, carbs=18.0, verified=True),
        db_session,
    )

    assert updated.calories == 120
    assert updated.proteins == 3.5
    assert updated.fats == 2.0
    assert updated.carbs == 18.0
    assert updated.kbju_status == "full"
    assert updated.verified is True


def test_product_update_allows_unknown_kbju_values(db_session):
    product = Product(name="Продукт без данных", calories=100, proteins=2,
                       fats=1, carbs=10, kbju_status="full")
    db_session.add(product)
    db_session.commit()

    updated = update_product(product.id, ProductUpdate(calories=None, carbs=None), db_session)

    assert updated.calories is None
    assert updated.proteins == 2
    assert updated.fats == 1
    assert updated.carbs is None
    assert updated.kbju_status == "partial"


def test_kbju_parser_handles_mojibake_property_text():
    from scripts.import_vkusvill import parse_kbju

    kbju = parse_kbju("����� 3 �, ���� 3.2 �, �������� 4.7 �; 60 ����")

    assert kbju["proteins"] == 3
    assert kbju["fats"] == 3.2
    assert kbju["carbs"] == 4.7
    assert kbju["calories"] is None


def test_universal_product_unit_prices_can_be_saved_and_read(db_session):
    from app.api.products import get_product_unit_prices, update_product_unit_prices
    from app.schemas.product import ProductUnitPriceUpdate

    product = Product(name="Молоко 3,2%", status="active")
    db_session.add(product)
    db_session.commit()

    updated = update_product_unit_prices(
        product.id,
        ProductUnitPriceUpdate(price_per_kg=180, price_per_liter=120, price_per_piece=30),
        db_session,
    )
    assert updated.price_per_kg == 180
    assert updated.price_per_liter == 120
    assert updated.price_per_piece == 30
    assert get_product_unit_prices(product.id, db_session).price_per_liter == 120

    cleared = update_product_unit_prices(
        product.id,
        ProductUnitPriceUpdate(price_per_liter=None),
        db_session,
    )
    assert cleared.price_per_liter is None


def test_unlinked_product_can_be_deleted_but_linked_product_is_protected(db_session):
    from app.api.products import delete_product
    from app.models import Recipe, RecipeIngredient, User

    unlinked = Product(name="Удаляемый продукт", status="active")
    linked = Product(name="Связанный продукт", status="active")
    owner = User(email="catalog-owner@example.test", hashed_password="unused")
    db_session.add_all([unlinked, linked, owner])
    db_session.flush()
    recipe = Recipe(user_id=owner.id, title="Тестовый рецепт", base_servings=1)
    db_session.add(recipe)
    db_session.flush()
    db_session.add(RecipeIngredient(
        recipe_id=recipe.id,
        product_id=linked.id,
        amount=100,
        unit="g",
    ))
    db_session.commit()

    delete_product(unlinked.id, db_session)
    assert db_session.get(Product, unlinked.id) is None

    with pytest.raises(HTTPException) as exc:
        delete_product(linked.id, db_session)
    assert exc.value.status_code == 409


def test_pyaterochka_import_parses_package_and_promo_price():
    from scripts.import_pyaterochka import extract_package, extract_current_price

    assert extract_package("930 мл") == (930, "мл")
    assert extract_package("1.4 л") == (1.4, "л")
    assert extract_current_price({
        "prices": {
            "regular": "99.99",
            "discount": None,
            "cpd_promo_price": "91.57",
        }
    }) == 91.57
