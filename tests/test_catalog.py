"""Tests for the /catalog endpoints."""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_get_categories(client: TestClient) -> None:
    response = client.get("/catalog/categories")
    assert response.status_code == 200
    categories = response.json()
    assert isinstance(categories, list)
    assert "sofa" in categories
    assert "chair" in categories


def test_get_sources(client: TestClient) -> None:
    response = client.get("/catalog/sources")
    assert response.status_code == 200
    sources = response.json()
    assert "ikea" in sources
    assert "alibaba" in sources


def test_get_all_products(client: TestClient) -> None:
    response = client.get("/catalog/products")
    assert response.status_code == 200
    products = response.json()
    assert isinstance(products, list)
    assert len(products) > 0
    # Validate product schema
    product = products[0]
    assert "item_id" in product
    assert "name" in product
    assert "category" in product
    assert "source" in product


def test_get_products_by_source_ikea(client: TestClient) -> None:
    response = client.get("/catalog/products?source=ikea")
    assert response.status_code == 200
    products = response.json()
    assert all(p["source"] == "ikea" for p in products)


def test_get_products_by_source_alibaba(client: TestClient) -> None:
    response = client.get("/catalog/products?source=alibaba")
    assert response.status_code == 200
    products = response.json()
    assert all(p["source"] == "alibaba" for p in products)


def test_get_products_filter_by_category(client: TestClient) -> None:
    response = client.get("/catalog/products?category=sofa")
    assert response.status_code == 200
    products = response.json()
    assert len(products) > 0
    assert all(p["category"] == "sofa" for p in products)


def test_get_products_filter_by_max_price(client: TestClient) -> None:
    response = client.get("/catalog/products?max_price=200")
    assert response.status_code == 200
    products = response.json()
    for p in products:
        if p["price"] is not None:
            assert p["price"] <= 200.0


def test_get_products_filter_by_style(client: TestClient) -> None:
    response = client.get("/catalog/products?style=modern")
    assert response.status_code == 200
    products = response.json()
    assert len(products) > 0


def test_get_products_sorted_by_rating(client: TestClient) -> None:
    response = client.get("/catalog/products")
    assert response.status_code == 200
    products = response.json()
    ratings = [p["rating"] for p in products if p.get("rating") is not None]
    # Products should be sorted by rating descending
    assert ratings == sorted(ratings, reverse=True)
