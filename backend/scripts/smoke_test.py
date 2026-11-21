"""Manual smoke check for the local database.

This file is intentionally safe to import: it performs no writes unless run
as a script with ``python scripts/smoke_test.py``.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> None:
    from app.core.database import SessionLocal
    from app.models import Product

    db = SessionLocal()
    try:
        product = db.query(Product).filter_by(name="Мука пшеничная в/с").first()
        if product is None:
            raise SystemExit("Smoke check failed: expected product is absent")
        print(
            f"Database OK: product id={product.id}, name={product.name}, "
            f"kbju_status={product.kbju_status}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
