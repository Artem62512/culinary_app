import sys
import re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.core.database import SessionLocal
from app.models import Product

def parse_name(full_name: str):
    match = re.search(r'(\d+[,.]\d+%|\d+%)', full_name)
    if match:
        variation = match.group(1)
        base_name = full_name[:match.start()].strip()
        base_name = re.sub(r'\s+\d+[,.]?\d*$', '', base_name).strip()
        return base_name, variation
    return full_name.split(',')[0].strip(), None

db = SessionLocal()
products = db.query(Product).all()
for p in products:
    p.base_name, p.variation = parse_name(p.name)
db.commit()

print("Обновлено продуктов:", len(products))
print("\nПримеры:")
for p in db.query(Product).limit(10).all():
    print(f"  {p.name[:40]:<40} -> Base: {p.base_name:<15} Var: {p.variation}")
db.close()
