from app.connectors.mock_product_spec import find_product, load_products


def test_mock_products_are_available():
    products = load_products()
    assert len(products) >= 10
    assert all(product.price > 0 for product in products)


def test_find_product_by_alias():
    product = find_product("小米14")
    assert product is not None
    assert product.id == "xiaomi_14"
