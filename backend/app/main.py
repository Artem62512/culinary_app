import sys
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.api import products, recipes, shopping_lists
from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.core.security import require_auth
from app.models import User

app = FastAPI(
    title="Culinary App API",
    version="0.2.0",
    description="Расчёт ингредиентов, КБЖУ и стоимости блюд",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
)

app.include_router(products.router)
app.include_router(recipes.router)
app.include_router(shopping_lists.router)


def _frontend_dist() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "frontend" / "dist"
    return Path(__file__).resolve().parents[2] / "frontend" / "dist"


frontend_dist = _frontend_dist()
if frontend_dist.is_dir():
    assets_dir = frontend_dist / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend-assets")

    @app.get("/", include_in_schema=False)
    def frontend_index():
        return FileResponse(frontend_dist / "index.html")

    @app.get("/favicon.svg", include_in_schema=False)
    def frontend_favicon():
        return FileResponse(frontend_dist / "favicon.svg")


@app.on_event("startup")
def initialize_database_and_owner():
    Base.metadata.create_all(bind=engine)
    from app.models import Product
    from scripts.seed_catalog import seed

    with SessionLocal() as db:
        if db.query(Product).count() == 0:
            seed(db)

    if not settings.app_username or not settings.app_password:
        return
    db = SessionLocal()
    try:
        owner = db.query(User).filter_by(id=1).first()
        if owner is None:
            db.add(User(id=1, email=settings.app_username, hashed_password="managed-by-http-basic"))
            db.commit()
    finally:
        db.close()

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/auth/check")
def auth_check(username: str = Depends(require_auth)):
    return {"authenticated": True, "username": username}
