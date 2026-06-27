from __future__ import annotations

from app.connectors.mock_product_spec import find_products
from app.schemas.product import ProductSpec


class ProductTool:
    name = "product_spec_tool"

    def get_products(self, product_ids_or_names: list[str]) -> tuple[list[ProductSpec], list[str]]:
        return find_products(product_ids_or_names)