import asyncio

import pytest


async def _make_user_category_product(client, quantity=10, price=20.0):
    user = (await client.post("/users", json={"username": "alice", "email": "alice@test.com"})).json()
    cat = (await client.post("/categories", json={"name": "Gadgets"})).json()
    product = (
        await client.post(
            "/products",
            json={"name": "Gizmo", "price": price, "category_id": cat["id"], "initial_quantity": quantity},
        )
    ).json()
    return user, product


async def test_create_order_decrements_stock(client):
    user, product = await _make_user_category_product(client, quantity=10)

    resp = await client.post(
        "/orders",
        json={"user_id": user["id"], "items": [{"product_id": product["id"], "quantity": 3}]},
    )
    assert resp.status_code == 201
    order = resp.json()
    assert order["items"][0]["quantity"] == 3
    assert order["items"][0]["unit_price"] == 20.0

    # stock should now be 7
    resp = await client.get(f"/products/{product['id']}")
    assert resp.json()["quantity"] == 7


async def test_order_fails_when_insufficient_stock(client):
    user, product = await _make_user_category_product(client, quantity=2)

    resp = await client.post(
        "/orders",
        json={"user_id": user["id"], "items": [{"product_id": product["id"], "quantity": 5}]},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "insufficient_stock"

    # stock must be untouched — the whole order rolled back
    resp = await client.get(f"/products/{product['id']}")
    assert resp.json()["quantity"] == 2


async def test_order_with_multiple_items(client):
    user = (await client.post("/users", json={"username": "bob", "email": "bob@test.com"})).json()
    cat = (await client.post("/categories", json={"name": "Mixed"})).json()
    p1 = (
        await client.post(
            "/products",
            json={"name": "P1", "price": 5, "category_id": cat["id"], "initial_quantity": 10},
        )
    ).json()
    p2 = (
        await client.post(
            "/products",
            json={"name": "P2", "price": 15, "category_id": cat["id"], "initial_quantity": 10},
        )
    ).json()

    resp = await client.post(
        "/orders",
        json={
            "user_id": user["id"],
            "items": [
                {"product_id": p1["id"], "quantity": 2},
                {"product_id": p2["id"], "quantity": 1},
            ],
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert len(body["items"]) == 2


async def test_concurrent_orders_cannot_oversell_last_unit(client):
    """
    Proof of the atomic UPDATE...WHERE quantity >= :qty pattern:
    two orders race for the LAST unit of stock. Only one should succeed;
    the other must see insufficient_stock, and final stock must never go negative.
    """
    user, product = await _make_user_category_product(client, quantity=1)

    async def place_order():
        return await client.post(
            "/orders",
            json={"user_id": user["id"], "items": [{"product_id": product["id"], "quantity": 1}]},
        )

    results = await asyncio.gather(place_order(), place_order())
    statuses = sorted(r.status_code for r in results)

    # exactly one order succeeds (201), the other correctly fails (409)
    assert statuses == [201, 409]

    resp = await client.get(f"/products/{product['id']}")
    assert resp.json()["quantity"] == 0  # never went negative
