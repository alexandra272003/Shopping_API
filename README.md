# Shopping API — Week 2 (PostgreSQL Shopping System)

A layered FastAPI + PostgreSQL backend for a small e-commerce catalog and
ordering system, built to practice relational schema design, transactions,
and concurrency-safe inventory management.

## Stack

- FastAPI (async)
- SQLAlchemy 2.0 (async ORM, `asyncpg` driver in prod, `aiosqlite` in tests)
- Alembic (schema migrations)
- PostgreSQL 16 via Docker Compose
- pytest + pytest-asyncio + httpx (fast in-memory-adjacent tests, no real DB needed)

## Architecture

Same layered pattern as `ping-user-api`: **router → service → repository**.

```
app/
  core/        # config, db session, error contract
  models/      # SQLAlchemy ORM table definitions
  repositories/ # raw DB access, no business rules
  services/    # business logic, talks in schemas not ORM objects
  routers/     # HTTP layer only
  schemas.py   # Pydantic request/response models
alembic/       # migrations
tests/         # sqlite-backed, one fresh db per test
```

## Data model

See `ER_DIAGRAM.md` for the full entity-relationship design and reasoning
(why `order_items` exists as a junction table, why `unit_price` is
snapshotted rather than joined live, why `inventory` is its own table).

6 tables: `users`, `categories`, `products`, `inventory`, `orders`, `order_items`.

## The concurrency-safe inventory decrement

This is the centerpiece of the project. Placing an order does **not**:

```
1. SELECT quantity FROM inventory WHERE product_id = ?
2. check in Python if quantity >= requested
3. UPDATE inventory SET quantity = quantity - requested
```

That has a race window between steps 1 and 3 — two concurrent requests can
both read "5 in stock", both decide it's enough, and both succeed, selling
stock that doesn't exist.

Instead, `app/repositories/order_repository.py` does a single atomic
statement:

```sql
UPDATE inventory
SET quantity = quantity - :requested
WHERE product_id = :product_id AND quantity >= :requested
```

The check and the write happen as one indivisible database operation. If two
requests race for the last unit, the database's row-level locking guarantees
only one `UPDATE` can succeed; the other sees `rowcount == 0` and the order
is rolled back with a 409 `insufficient_stock` error.

This is proven in `tests/test_orders.py::test_concurrent_orders_cannot_oversell_last_unit`,
which fires two real concurrent order requests (via `asyncio.gather`, each
with its own DB session — mirroring two real simultaneous HTTP requests) at
a product with exactly 1 unit of stock. Exactly one succeeds, one fails, and
final stock is verified to never go negative.

## Running it for real (PostgreSQL via Docker)

```bash
docker compose up --build
```

This starts Postgres (with a healthcheck), waits for it to be ready, runs
`alembic upgrade head` to create all 6 tables, then starts the API on
`http://127.0.0.1:8000`.

Quick smoke test once it's up:

```bash
curl http://127.0.0.1:8000/ping
```

## Running tests (no Docker needed)

Tests run against a temporary file-based SQLite database — no Postgres
required for the test suite, same philosophy as `mongomock-motor` in
Week 1's Notes API.

```bash
pip install -r requirements.txt
pytest -v
```

10 tests, all passing, including the concurrency proof above.

## Generating a new migration after changing models

```bash
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```

## What's deliberately not done yet

- No auth/authz on any endpoint (same honest gap as Week 1 — noted, not hidden)
- No order cancellation / stock restoration flow
- No pagination on `/products` or `/categories` list endpoints yet
- Order status is set to `pending` and never transitions (no payment flow)
# Shopping_API
