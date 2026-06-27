from __future__ import annotations

from fastapi import APIRouter

from app.connectors.mock_product_spec import load_products
from app.schemas.product import ProductSpec

router = APIRouter(tags=["products"])


@router.get("/products", response_model=list[ProductSpec])
def list_products() -> list[ProductSpec]:
    return load_products()