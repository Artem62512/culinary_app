import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import SessionLocal
from app.models import Product, ProductPrice

db = SessionLocal()
products = db.query(Product).limit(10).all()

# Простые тестовые цены: цена упаковки ~ вес * (100..300 руб/кг)
for p in products:
    existing = db.query(ProductPrice).filter_by(product_id=p.id, source="manual").first()
    if existing:
        continue
    pkg_g = 900.0
    price = round(pkg_g / 1000 * 150, 2)  # 150 руб/кг условно
    db.add(ProductPrice(
        product_id=p.id, user_id=None,
        price=price, package_weight_g=pkg_g, price_per_kg=round(price / (pkg_g / 1000), 2),
        source="manual",
    ))
db.commit()
print("Prices added for", db.query(ProductPrice).count(), "products")
db.close()
