from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.schemas.product import ProductSpec

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "mock_products.json"


@lru_cache(maxsize=1)
def load_products() -> list[ProductSpec]:
    raw = json.loads(DATA_PATH.read_text(encoding="utf-8-sig"))
    return [ProductSpec.model_validate(item) for item in raw]


def _normalize(value: str) -> str:
    return "".join(value.lower().split())


def find_product(name: str) -> ProductSpec | None:
    query = _normalize(name)
    for product in load_products():
        names = [product.name, product.id, *product.aliases]
        if any(query == _normalize(item) for item in names):
            return product
    for product in load_products():
        names = [product.name, product.id, *product.aliases]
        if any(query in _normalize(item) or _normalize(item) in query for item in names):
            return product
    return None


def find_products(names: list[str]) -> tuple[list[ProductSpec], list[str]]:
    products: list[ProductSpec] = []
    missing: list[str] = []
    seen: set[str] = set()
    for name in names:
        product = find_product(name)
        if product is None:
            missing.append(name)
            continue
        if product.id not in seen:
            products.append(product)
            seen.add(product.id)
    return products, missing

