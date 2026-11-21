import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.core.database import SessionLocal
from app.models import Product

db = SessionLocal()
count = db.query(Product).count()
print("Total products in DB:", count)

if count > 0:
    for p in db.query(Product).limit(5).all():
        print(f"ID: {p.id} | Name: {p.name} | Base: {p.base_name} | Var: {p.variation}")
else:
    print("База пуста! Импорт не сохранил данные.")
db.close()
