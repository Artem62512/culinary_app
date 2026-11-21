import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.core.database import SessionLocal
from app.models import Product

db = SessionLocal()
# \u043c\u043e\u043b\u043e\u043a\u043e = "молоко"
milk = db.query(Product).filter(Product.name.ilike('%\u043c\u043e\u043b\u043e\u043a\u043e%')).limit(10).all()
print(f"{'Base name':<20} | {'Variation':<10} | {'Full name'}")
print("-" * 70)
for p in milk:
    print(f"{(p.base_name or '-'):<20} | {(p.variation or '-'):<10} | {p.name}")
db.close()
