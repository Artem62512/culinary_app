import re
import unicodedata
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_auth
from app.core.config import OWNER_ID
from app.models import (
    Product, ProductAlias, ProductCategory, ProductPrice,
    RecipeIngredient, ShoppingListItem, StoreProduct, StoreProductPrice,
)
from app.schemas.product import (
    ProductCreate, ProductUpdate, ProductOut, ProductCategoryCreate, ProductCategoryOut,
    ProductAliasCreate, ProductAliasOut, StoreProductCreate, StoreProductOut,
    StoreProductPriceCreate, StoreProductPriceOut, ProductStatusUpdate,
    ProductUnitPriceUpdate, ProductUnitPricesOut,
)

router = APIRouter(dependencies=[Depends(require_auth)], prefix="/products", tags=["products"])


@router.get("/match")
def match_universal_product(q: str = Query(..., min_length=1, max_length=255), db: Session = Depends(get_db)):
    """Return only an exact, verified catalog match. Never guess fuzzy matches."""
    raw = q.strip()
    normalized = normalize_product_name(raw)
    if not normalized:
        return None

    aliases = (
        db.query(ProductAlias)
        .filter(ProductAlias.normalized_alias == normalized)
        .all()
    )
    if len(aliases) == 1:
        product = db.get(Product, aliases[0].product_id)
        return product if product and product.status == "active" else None

    candidates = (
        db.query(Product)
        .filter(Product.status == "active")
        .all()
    )
    exact_names = [
        product for product in candidates
        if normalize_product_name(product.name) == normalized
    ]
    if len(exact_names) == 1:
        return exact_names[0]
    if exact_names:
        return None

    base_matches = [
        product for product in candidates
        if product.base_name
        and normalize_product_name(product.base_name) == normalized
    ]
    if len(base_matches) == 1:
        return base_matches[0]
    return None


def normalize_product_name(value: str) -> str:
    """Normalize spelling for matching, without removing meaningful words/numbers."""
    value = unicodedata.normalize("NFKC", value).casefold().replace("ё", "е")
    value = re.sub(r"[^\w]+", " ", value, flags=re.UNICODE)
    return " ".join(value.split())


def _kbju_status(product) -> str:
    vals = [product.calories, product.proteins, product.fats, product.carbs]
    if all(v is not None for v in vals):
        return "full"
    if any(v is not None for v in vals):
        return "partial"
    return "missing"


def _get_ru_category(name: str) -> str:
    name = name.lower()
    if any(x in name for x in ['молоко', 'кефир', 'сыр', 'творог', 'масло сливочное', 'сливки', 'сметана', 'йогурт']):
        return 'Молочные продукты'
    if any(x in name for x in ['хлеб', 'батон', 'булка', 'изделие х/б', 'лаваш']):
        return 'Хлеб и выпечка'
    if any(x in name for x in ['яйцо', 'яйца']):
        return 'Яйца'
    if any(x in name for x in ['мука', 'сахар', 'соль', 'специи', 'перец', 'корица']):
        return 'Бакалея'
    if any(x in name for x in ['курица', 'говядина', 'свинина', 'фарш', 'грудка', 'бедро']):
        return 'Мясо и птица'
    if any(x in name for x in ['масло растительное', 'масло оливковое', 'масло топленое']):
        return 'Масла'
    return 'Прочее'


@router.get("", response_model=list[ProductOut])
def list_products(
    q: str | None = Query(default=None, max_length=100),
    category_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    status: str = "active",
    db: Session = Depends(get_db),
):
    if status not in {"active", "inactive", "archived", "all"}:
        raise HTTPException(status_code=422, detail="Недопустимый статус продукта")
    query = db.query(Product)
    if status != "all":
        query = query.filter(Product.status == status)
    if category_id is not None:
        query = query.filter(Product.category_id == category_id)
    if q and q.strip():
        raw = q.strip()
        normalized = normalize_product_name(raw)
        conditions = [Product.name.ilike(f"%{raw}%")]
        if normalized:
            conditions.extend([Product.normalized_name.contains(normalized), ProductAlias.normalized_alias.contains(normalized)])
        query = query.outerjoin(ProductAlias, ProductAlias.product_id == Product.id).filter(or_(*conditions)).distinct()
    return query.order_by(Product.name).offset(offset).limit(limit).all()


@router.get("/catalog/quality")
def catalog_quality_report(db: Session = Depends(get_db)):
    """Read-only quality report; suspicious records are never merged or deleted automatically."""
    products = db.query(Product).order_by(Product.name, Product.id).all()
    aliases_count = db.query(ProductAlias).count()
    categories = db.query(ProductCategory).order_by(ProductCategory.name).all()

    by_name = {}
    for product in products:
        by_name.setdefault(normalize_product_name(product.name), []).append(product)

    duplicate_groups = []
    exact_duplicate_groups = []
    for normalized_name, items in by_name.items():
        if not normalized_name or len(items) < 2:
            continue
        signatures = {}
        for item in items:
            signature = (
                item.category_id, item.calories, item.proteins,
                item.fats, item.carbs, item.base_name, item.variation,
            )
            signatures.setdefault(signature, []).append(item)
        group = {
            "name": items[0].name,
            "products": [{"id": item.id, "name": item.name, "category_name": item.category_name,
                          "calories": item.calories, "proteins": item.proteins,
                          "fats": item.fats, "carbs": item.carbs,
                          "verified": item.verified} for item in items],
            "same_nutrition": len({(x.calories, x.proteins, x.fats, x.carbs) for x in items}) == 1,
            "same_category": len({x.category_id for x in items}) == 1,
        }
        duplicate_groups.append(group)
        exact = [cluster for cluster in signatures.values() if len(cluster) > 1]
        if exact:
            exact_duplicate_groups.append({
                "name": items[0].name,
                "clusters": [[item.id for item in sorted(cluster, key=lambda value: value.id)] for cluster in exact],
            })

    partial = [p for p in products if p.kbju_status == "partial"]
    missing = [p for p in products if p.kbju_status == "missing"]
    unverified = [p for p in products if not p.verified]
    uncategorized = [p for p in products if p.category_id is None]
    empty_categories = [c.name for c in categories if not any(p.category_id == c.id for p in products)]

    return {
        "summary": {
            "products_total": len(products),
            "kbju_full": sum(p.kbju_status == "full" for p in products),
            "kbju_partial": len(partial),
            "kbju_missing": len(missing),
            "unverified": len(unverified),
            "without_category": len(uncategorized),
            "aliases_total": aliases_count,
            "duplicate_name_groups": len(duplicate_groups),
            "exact_duplicate_clusters": sum(len(x["clusters"]) for x in exact_duplicate_groups),
        },
        "duplicate_groups": duplicate_groups,
        "exact_duplicate_groups": exact_duplicate_groups,
        "partial_kbju": [{"id": p.id, "name": p.name} for p in partial],
        "missing_kbju": [{"id": p.id, "name": p.name} for p in missing],
        "unverified_products": [{"id": p.id, "name": p.name} for p in unverified],
        "uncategorized_products": [{"id": p.id, "name": p.name} for p in uncategorized],
        "empty_categories": empty_categories,
    }


@router.get("/categories", response_model=list[str])
def list_categories(db: Session = Depends(get_db)):
    categories = db.query(ProductCategory).order_by(ProductCategory.name).all()
    if categories:
        return [category.name for category in categories]
    products = db.query(Product).filter(Product.base_name.isnot(None)).all()
    return sorted({_get_ru_category(p.name) for p in products})


@router.get("/catalog/categories", response_model=list[ProductCategoryOut])
def list_catalog_categories(db: Session = Depends(get_db)):
    return db.query(ProductCategory).order_by(ProductCategory.name).all()


@router.post("/catalog/categories", response_model=ProductCategoryOut, status_code=201)
def create_catalog_category(payload: ProductCategoryCreate, db: Session = Depends(get_db)):
    existing = db.query(ProductCategory).filter(
        or_(ProductCategory.slug == payload.slug, ProductCategory.name.ilike(payload.name))
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Категория с таким названием или идентификатором уже существует")
    category = ProductCategory(name=payload.name, slug=payload.slug)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@router.get("/groups")
def list_groups(
    category: str | None = Query(None),
    q: str | None = Query(default=None, max_length=100),
    db: Session = Depends(get_db),
):
    query = db.query(Product).filter(Product.base_name.isnot(None), Product.status == "active")
    if category:
        query = query.outerjoin(ProductCategory, Product.category_id == ProductCategory.id).filter(
            or_(ProductCategory.name == category, Product.category == category)
        )
    if q and q.strip():
        raw = q.strip()
        normalized = normalize_product_name(raw)
        conditions = [Product.name.ilike(f"%{raw}%"), Product.base_name.ilike(f"%{raw}%")]
        if normalized:
            conditions.extend([Product.normalized_name.contains(normalized), ProductAlias.normalized_alias.contains(normalized)])
        query = query.outerjoin(ProductAlias, ProductAlias.product_id == Product.id).filter(or_(*conditions))
    products = query.distinct().all()
    groups = {}
    for product in products:
        if not product.base_name:
            continue
        entry = groups.setdefault(product.base_name, set())
        for alias in db.query(ProductAlias.alias).filter(ProductAlias.product_id == product.id).all():
            entry.add(alias[0])
    return [{"base_name": name, "aliases": sorted(groups[name])} for name in sorted(groups)]


@router.get("/groups/variations", response_model=list[ProductOut])
def list_variations(base_name: str, db: Session = Depends(get_db)):
    return db.query(Product).filter(Product.base_name == base_name, Product.status == "active").order_by(Product.variation, Product.name).all()


@router.post("", response_model=ProductOut, status_code=201)
def create_product(payload: ProductCreate, db: Session = Depends(get_db)):
    normalized_name = normalize_product_name(payload.name)
    duplicate = db.query(Product).all()
    if any(normalize_product_name(item.name) == normalized_name for item in duplicate):
        raise HTTPException(status_code=409, detail="Продукт с таким названием уже существует")
    if db.query(ProductAlias).filter_by(normalized_alias=normalized_name).first():
        raise HTTPException(status_code=409, detail="Это название уже используется как синоним другого продукта")

    category_name = payload.category
    category_id = payload.category_id
    if category_id is not None:
        category = db.get(ProductCategory, category_id)
        if not category:
            raise HTTPException(status_code=404, detail="Категория не найдена")
        category_name = category.name
    elif category_name:
        category = db.query(ProductCategory).filter(ProductCategory.name.ilike(category_name.strip())).first()
        if category:
            category_id = category.id
            category_name = category.name
    else:
        category = db.query(ProductCategory).filter_by(slug="other").first()
        if category:
            category_id = category.id
            category_name = category.name

    product = Product(
        name=payload.name,
        normalized_name=normalized_name,
        attributes=payload.attributes,
        category=category_name,
        category_id=category_id,
        base_name=payload.base_name,
        variation=payload.variation,
        calories=payload.calories,
        proteins=payload.proteins,
        fats=payload.fats,
        carbs=payload.carbs,
        source=payload.source,
        verified=False,
    )
    product.kbju_status = _kbju_status(product)
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.post("/catalog/selection", response_model=list[ProductOut])
def validate_product_selection(product_ids: list[int], db: Session = Depends(get_db)):
    """Return selected active universal products in the caller-provided order."""
    unique_ids = list(dict.fromkeys(product_ids))
    if not unique_ids:
        return []
    if len(unique_ids) > 200:
        raise HTTPException(status_code=422, detail="За один запрос можно выбрать не более 200 продуктов")
    products = db.query(Product).filter(Product.id.in_(unique_ids), Product.status == "active").all()
    by_id = {product.id: product for product in products}
    missing = [product_id for product_id in unique_ids if product_id not in by_id]
    if missing:
        raise HTTPException(status_code=404, detail={"message": "Некоторые продукты не найдены или неактивны", "product_ids": missing})
    return [by_id[product_id] for product_id in unique_ids]


@router.get("/store-products", response_model=list[StoreProductOut])
def list_store_products(
    universal_product_id: int | None = Query(default=None, gt=0),
    store_name: str | None = Query(default=None, max_length=120),
    q: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(StoreProduct).filter(StoreProduct.status == "active")
    if universal_product_id is not None:
        query = query.filter(StoreProduct.universal_product_id == universal_product_id)
    if store_name:
        query = query.filter(StoreProduct.store_name.ilike(f"%{store_name.strip()}%"))
    if q and q.strip():
        query = query.filter(StoreProduct.name.ilike(f"%{q.strip()}%"))
    return query.order_by(StoreProduct.name).offset(offset).limit(limit).all()


@router.post("/store-products", response_model=StoreProductOut, status_code=201)
def create_store_product(payload: StoreProductCreate, db: Session = Depends(get_db)):
    universal = db.get(Product, payload.universal_product_id)
    if not universal or universal.status != "active":
        raise HTTPException(status_code=404, detail="Активный универсальный продукт не найден")
    if payload.barcode and db.query(StoreProduct).filter_by(barcode=payload.barcode).first():
        raise HTTPException(status_code=409, detail="Товар с таким штрихкодом уже существует")
    if payload.source_id and db.query(StoreProduct).filter_by(source=payload.source, source_id=payload.source_id).first():
        raise HTTPException(status_code=409, detail="Товар с таким идентификатором источника уже существует")
    store_product = StoreProduct(**payload.model_dump())
    db.add(store_product)
    db.commit()
    db.refresh(store_product)
    return store_product


@router.get("/store-products/{store_product_id}/prices", response_model=list[StoreProductPriceOut])
def list_store_product_prices(store_product_id: int, db: Session = Depends(get_db)):
    if not db.get(StoreProduct, store_product_id):
        raise HTTPException(status_code=404, detail="Магазинный товар не найден")
    return db.query(StoreProductPrice).filter_by(store_product_id=store_product_id).order_by(StoreProductPrice.observed_at.desc()).all()


@router.post("/store-products/{store_product_id}/prices", response_model=StoreProductPriceOut, status_code=201)
def add_store_product_price(store_product_id: int, payload: StoreProductPriceCreate, db: Session = Depends(get_db)):
    if not db.get(StoreProduct, store_product_id):
        raise HTTPException(status_code=404, detail="Магазинный товар не найден")
    price = StoreProductPrice(store_product_id=store_product_id, **payload.model_dump())
    db.add(price)
    db.commit()
    db.refresh(price)
    return price


@router.get("/{product_id}/aliases", response_model=list[ProductAliasOut])
def list_product_aliases(product_id: int, db: Session = Depends(get_db)):
    if not db.get(Product, product_id):
        raise HTTPException(status_code=404, detail="Product not found")
    return db.query(ProductAlias).filter_by(product_id=product_id).order_by(ProductAlias.alias).all()


@router.post("/{product_id}/aliases", response_model=ProductAliasOut, status_code=201)
def add_product_alias(product_id: int, payload: ProductAliasCreate, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    normalized = normalize_product_name(payload.alias)
    if normalized == normalize_product_name(product.name):
        raise HTTPException(status_code=409, detail="Синоним совпадает с основным названием продукта")
    if db.query(ProductAlias).filter_by(normalized_alias=normalized).first():
        raise HTTPException(status_code=409, detail="Такой синоним уже закреплён за продуктом")
    if any(normalize_product_name(p.name) == normalized for p in db.query(Product).all()):
        raise HTTPException(status_code=409, detail="Такое название уже является названием другого продукта")
    alias = ProductAlias(product_id=product_id, alias=payload.alias, normalized_alias=normalized)
    db.add(alias)
    db.commit()
    db.refresh(alias)
    return alias


@router.delete("/{product_id}/aliases/{alias_id}", status_code=204)
def delete_product_alias(product_id: int, alias_id: int, db: Session = Depends(get_db)):
    alias = db.query(ProductAlias).filter_by(id=alias_id, product_id=product_id).first()
    if not alias:
        raise HTTPException(status_code=404, detail="Синоним не найден")
    db.delete(alias)
    db.commit()


@router.patch("/{product_id}", response_model=ProductOut)
def update_product(product_id: int, payload: ProductUpdate, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Продукт не найден")

    changes = payload.model_dump(exclude_unset=True)
    if "name" in changes:
        normalized = normalize_product_name(changes["name"])
        duplicates = db.query(Product).filter(Product.id != product_id).all()
        if any(normalize_product_name(item.name) == normalized for item in duplicates):
            raise HTTPException(status_code=409, detail="Продукт с таким названием уже существует")
        alias_conflict = db.query(ProductAlias).filter_by(normalized_alias=normalized).first()
        if alias_conflict:
            raise HTTPException(status_code=409, detail="Это название используется как синоним другого продукта")
        product.name = changes["name"]
        product.normalized_name = normalized

    if "category_id" in changes:
        category_id = changes["category_id"]
        category = db.get(ProductCategory, category_id) if category_id is not None else None
        if category_id is not None and category is None:
            raise HTTPException(status_code=404, detail="Категория не найдена")
        product.category_id = category_id
        product.category = category.name if category else None

    for field in ("base_name", "variation", "calories", "proteins", "fats", "carbs", "attributes", "verified"):
        if field in changes:
            value = changes[field]
            if field == "attributes" and value is None:
                value = {}
            setattr(product, field, value)

    product.kbju_status = _kbju_status(product)
    db.commit()
    db.refresh(product)
    return product


@router.patch("/{product_id}/status", response_model=ProductOut)
def update_product_status(product_id: int, payload: ProductStatusUpdate, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Продукт не найден")
    product.status = payload.status
    db.commit()
    db.refresh(product)
    return product


@router.post("/{product_id}/refresh-prices/pyaterochka")
async def refresh_pyaterochka_product_prices(product_id: int, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Продукт не найден")

    from scripts.import_pyaterochka import import_one_product

    try:
        return await import_one_product(product_id)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Не удалось обновить цены Пятёрочки: {exc}",
        )


@router.post("/{product_id}/refresh-kbju")
async def refresh_product_kbju(product_id: int, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Продукт не найден")

    from scripts.import_kbju import refresh_one_product

    try:
        return await __import__("asyncio").to_thread(refresh_one_product, product_id)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Не удалось обновить КБЖУ: {exc}",
        )


@router.post("/catalog/refresh-kbju/missing")
async def refresh_missing_kbju(limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    products = (
        db.query(Product)
        .filter(Product.status == "active", Product.kbju_status != "full")
        .order_by(Product.kbju_status.asc(), Product.id.asc())
        .limit(limit)
        .all()
    )
    product_ids = [product.id for product in products]
    db.close()

    from scripts.import_kbju import refresh_one_product

    results = []
    for product_id in product_ids:
        try:
            results.append({"product_id": product_id, **await __import__("asyncio").to_thread(refresh_one_product, product_id)})
        except Exception as exc:
            results.append({"product_id": product_id, "error": str(exc)})
    return {"processed": len(results), "results": results}


@router.get("/{product_id}/prices", response_model=ProductUnitPricesOut)
def get_product_unit_prices(product_id: int, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Продукт не найден")

    rows = (
        db.query(ProductPrice)
        .filter_by(product_id=product_id)
        .order_by(ProductPrice.updated_at.desc(), ProductPrice.id.desc())
        .all()
    )
    result = {"product_id": product_id, "price_per_kg": None, "price_per_liter": None, "price_per_piece": None, "updated_at": None}
    observed = []
    seen_fields = set()
    for row in rows:
        if row.updated_at:
            observed.append(row.updated_at)
        for field in ("price_per_kg", "price_per_liter", "price_per_piece"):
            value = getattr(row, field, None)
            if field in seen_fields:
                continue
            if value is not None:
                seen_fields.add(field)
                if value > 0:
                    result[field] = float(value)
    if observed:
        result["updated_at"] = max(observed)
    return ProductUnitPricesOut(**result)


@router.put("/{product_id}/prices", response_model=ProductUnitPricesOut)
def update_product_unit_prices(product_id: int, payload: ProductUnitPriceUpdate, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Продукт не найден")

    values = payload.model_dump(exclude_unset=True)
    if not values:
        raise HTTPException(status_code=422, detail="Укажите хотя бы одну цену")
    for field in ("price_per_kg", "price_per_liter", "price_per_piece"):
        if field in values:
            values[field] = float(values[field]) if values[field] is not None else 0.0

    row = ProductPrice(
        product_id=product_id,
        user_id=OWNER_ID,
        price=None,
        package_weight_g=None,
        price_per_kg=values.get("price_per_kg"),
        price_per_liter=values.get("price_per_liter"),
        price_per_piece=values.get("price_per_piece"),
        source="manual",
    )
    db.add(row)
    db.commit()
    return get_product_unit_prices(product_id, db)


@router.delete("/{product_id}", status_code=204)
def delete_product(product_id: int, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Продукт не найден")

    recipe_links = db.query(RecipeIngredient).filter_by(product_id=product_id).count()
    cart_links = db.query(ShoppingListItem).filter_by(product_id=product_id).count()
    store_links = db.query(StoreProduct).filter_by(universal_product_id=product_id).count()
    if recipe_links or cart_links or store_links:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Продукт нельзя удалить, пока на него есть ссылки",
                "recipe_ingredients": recipe_links,
                "shopping_list_items": cart_links,
                "store_products": store_links,
            },
        )

    db.delete(product)
    db.commit()


@router.patch("/store-products/{store_product_id}/status", response_model=StoreProductOut)
def update_store_product_status(store_product_id: int, payload: ProductStatusUpdate, db: Session = Depends(get_db)):
    product = db.get(StoreProduct, store_product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Магазинный товар не найден")
    product.status = payload.status
    db.commit()
    db.refresh(product)
    return product


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product
