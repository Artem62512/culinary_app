import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPBasicCredentials
from app.core import security
from app.services.calculator import Ingredient, calc_recipe_kbju, calc_recipe_cost

def test_api_fails_closed_when_credentials_are_not_configured(monkeypatch):
    monkeypatch.setattr(security.settings, "app_username", "")
    monkeypatch.setattr(security.settings, "app_password", "")
    with pytest.raises(HTTPException) as exc:
        security.require_auth(None)
    assert exc.value.status_code == 503

def test_api_rejects_missing_credentials(monkeypatch):
    monkeypatch.setattr(security.settings, "app_username", "owner")
    monkeypatch.setattr(security.settings, "app_password", "a-long-password")
    with pytest.raises(HTTPException) as exc:
        security.require_auth(None)
    assert exc.value.status_code == 401

def test_api_accepts_valid_credentials(monkeypatch):
    monkeypatch.setattr(security.settings, "app_username", "owner")
    monkeypatch.setattr(security.settings, "app_password", "a-long-password")
    credentials = HTTPBasicCredentials(username="owner", password="a-long-password")
    assert security.require_auth(credentials) == "owner"

def test_volume_kbju_is_not_assumed_equal_to_mass():
    ingredient = Ingredient(product_id=1, name="Молоко", amount=100, unit="ml",
                            calories=60, proteins=3, fats=3, carbs=5, kbju_status="full")
    result = calc_recipe_kbju([ingredient])
    assert result["calories"] is None
    assert result["known_calories"] == 0
    assert result["accuracy"] == "approximate"

def test_volume_price_is_not_calculated_without_density_or_price_per_litre():
    ingredient = Ingredient(product_id=1, name="Молоко", amount=500, unit="ml", price_per_kg=80)
    result = calc_recipe_cost([ingredient])
    assert result["total_cost"] is None
    assert result["missing_prices"] == ["Молоко"]
