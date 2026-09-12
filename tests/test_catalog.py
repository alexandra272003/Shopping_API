import pytest


async def test_ping(client):
    resp = await client.get("/ping")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "message": "pong"}


async def test_create_and_get_category(client):
    resp = await client.post("/categories", json={"name": "Electronics"})
    assert resp.status_code == 201
    cat_id = resp.json()["id"]

    resp = await client.get(f"/categories/{cat_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Electronics"


async def test_duplicate_category_conflicts(client):
    await client.post("/categories", json={"name": "Books"})
    resp = await client.post("/categories", json={"name": "Books"})
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "conflict"


async def test_create_product_creates_inventory_row(client):
    cat_resp = await client.post("/categories", json={"name": "Toys"})
    cat_id = cat_resp.json()["id"]

    resp = await client.post(
        "/products",
        json={"name": "Lego Set", "price": 49.99, "category_id": cat_id, "initial_quantity": 10},
    )
    assert resp.status_code == 201
    product_id = resp.json()["id"]

    resp = await client.get(f"/products/{product_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["quantity"] == 10
    assert body["name"] == "Lego Set"


async def test_list_products_filtered_by_category(client):
    cat1 = (await client.post("/categories", json={"name": "Cat1"})).json()["id"]
    cat2 = (await client.post("/categories", json={"name": "Cat2"})).json()["id"]

    await client.post(
        "/products", json={"name": "A", "price": 1, "category_id": cat1, "initial_quantity": 5}
    )
    await client.post(
        "/products", json={"name": "B", "price": 2, "category_id": cat2, "initial_quantity": 5}
    )

    resp = await client.get(f"/products?category_id={cat1}")
    assert resp.status_code == 200
    names = [p["name"] for p in resp.json()]
    assert names == ["A"]


async def test_get_missing_product_404(client):
    resp = await client.get("/products/9999")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"
