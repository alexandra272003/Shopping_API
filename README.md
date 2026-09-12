# Shopping API

A backend for a small e-commerce system — browse categories and products,
place orders, and never oversell stock even under concurrent load.

Built as Week 2 of a backend engineering sprint, following Week 1's
`ping-user-api` (FastAPI + MongoDB). This project deliberately switches to
PostgreSQL to practice relational schema design, migrations, and
transaction-level correctness — the things MongoDB's document model doesn't
force you to think about.

---

## What this project actually demonstrates

If you only read one section, read this one. Everything else is detail.

1. **Relational schema design** — 6 tables, correct normalization, and a
   junction table (`order_items`) used for the right reason, not by rote.
2. **Migrations as a discipline, not an afterthought** — every schema change
   goes through Alembic, including a real hotfix migration (see below).
3. **Concurrency-safe writes** — the core interview-relevant skill of this
   project: preventing two simultaneous orders from overselling the last
   unit of stock, proven with an actual concurrent-request test.
4. **A real bug, found and fixed against real infrastructure** — not a
   hypothetical "what if" but something that actually broke when this
   project ran against real PostgreSQL for the first time, explained in
   detail below.

---

## Tech stack

| Concern | Choice | Why |
|---|---|---|
| Web framework | FastAPI (async) | Same as Week 1, consistent pattern |
| ORM | SQLAlchemy 2.0 (async) | Industry-standard, explicit about SQL underneath |
| Migrations | Alembic | Versioned, reviewable schema history |
| Database (prod) | PostgreSQL 16 | Relational integrity, real transactions, `SELECT ... FOR` semantics |
| Database (tests) | SQLite (`aiosqlite`) | Fast, no container needed, same idea as `mongomock-motor` in Week 1 |
| Containerization | Docker Compose | Postgres + API, healthcheck-gated startup |

---

## Architecture: router → service → repository

Same layered pattern as Week 1's project, applied to a relational schema:

```
app/
  core/
    config.py       # env-driven settings (pydantic-settings)
    db.py           # async engine, session factory, get_session dependency
    errors.py       # structured {"error": {code, message, details}} contract
  models/
    models.py       # SQLAlchemy ORM table definitions (the schema, in Python)
  schemas.py        # Pydantic request/response shapes (never expose ORM objects directly)
  repositories/     # raw DB access — SQL-adjacent, no business rules
  services/         # business logic — talks in schemas, calls repositories
  routers/          # HTTP layer only — no DB or business logic here
alembic/
  versions/         # every schema change, in order, reviewable
tests/
  conftest.py       # per-test fresh SQLite DB, per-request session (see below)
  test_catalog.py   # categories + products
  test_orders.py    # orders, including the concurrency proof
```

**Why this separation matters in an interview context:** a router should
never contain a raw SQL query, and a repository should never know what an
HTTP status code is. Each layer can be tested, replaced, or reasoned about
independently. This is the same argument for layered architecture that
applied in Week 1 — it's not framework ceremony, it's what lets you swap
MongoDB for PostgreSQL (like this project did) without touching routers at
all.

---

## The data model

Full reasoning lives in `ER_DIAGRAM.md`. Short version:

```
users ──1:N──> orders ──1:N──> order_items <──N:1── products <──N:1── categories
                                                          │
                                                         1:1
                                                          │
                                                      inventory
```

**Why `order_items` exists at all:** an order can contain many products, and
a product can appear on many orders — a many-to-many relationship. Relational
databases can't express many-to-many with a single foreign key; you need a
junction table in between, one that carries its own identity and its own
attributes (`quantity`, `unit_price`) that belong to the *relationship*, not
to either side alone.

**Why `unit_price` is copied onto `order_items` instead of joined live from
`products.price`:** prices change over time. If a past order's total were
computed by joining to the current price, that order's total would silently
change every time the product's price changed. Snapshotting the price at
purchase time is a deliberate, documented denormalization — not a mistake.

**Why `inventory` is a separate table instead of a `quantity` column on
`products`:** stock changes constantly (every order touches it) while a
product's descriptive data (name, price, category) rarely does. Separating
them means stock updates can be locked and written independently, and it
leaves room for this to become one-to-many later (e.g. per-warehouse stock)
without altering `products` at all.

---

## The concurrency-safe inventory decrement (the centerpiece)

This is the part worth understanding cold for an interview.

### The naive approach, and why it's wrong

```
1. SELECT quantity FROM inventory WHERE product_id = ?
2. if quantity >= requested: proceed
3. UPDATE inventory SET quantity = quantity - requested
```

Between step 1 and step 3, another request can run the exact same three
steps. If stock is 1 and two requests both read "1 in stock" before either
writes, **both** think they succeeded. The result: stock goes to -1, or two
customers are charged for the same last unit. This is a classic race
condition, and it's invisible in any single-user manual test — it only
appears under real concurrent load, which is exactly why it's a favorite
interview topic.

### The actual implementation

`app/repositories/order_repository.py` does the check and the write as
**one atomic SQL statement**:

```sql
UPDATE inventory
SET quantity = quantity - :requested
WHERE product_id = :product_id AND quantity >= :requested
```

The `WHERE quantity >= :requested` clause means the row only updates if
there's enough stock left, and the database guarantees this check-and-write
happens as a single indivisible operation — no other transaction can see or
touch that row mid-update. If two requests race for the last unit, exactly
one `UPDATE` succeeds; the other's statement affects zero rows. The
repository checks `result.rowcount == 0` and raises `InsufficientStockError`
(mapped to `409 insufficient_stock`), rolling back that request's entire
order — no partial orders, no negative stock.

### How this is actually proven, not just claimed

`tests/test_orders.py::test_concurrent_orders_cannot_oversell_last_unit`
sets a product's stock to exactly 1, then fires **two real concurrent**
order requests at it via `asyncio.gather`. It asserts:

- exactly one request returns `201` and the other returns `409`
- final stock is exactly `0`, never negative

Making this test meaningful required a fix to the test setup itself: the
first version shared **one database session** across both concurrent
requests, which SQLAlchemy doesn't support (a session can't run two flushes
at once) — the test failed for the wrong reason. The fix was to give each
simulated request its own session, opened fresh per call, exactly like
production's `get_session` dependency does per real HTTP request (see
`tests/conftest.py`). That's not just a test-plumbing detail — it's the
same "one session per request" principle that makes the whole concurrency
guarantee possible in production too.

---

## Case study: a real bug found against real Postgres

This project's test suite runs against SQLite for speed (10/10 passing,
sub-second). But the **first time** this code ran against actual PostgreSQL
via Docker Compose, creating a product failed with:

```
TypeError: can't subtract offset-naive and offset-aware datetimes
```

**What happened:** `created_at` columns were defined without timezone
awareness (plain `DateTime`), but the default value generator
(`datetime.now(timezone.utc)`) produces a timezone-*aware* Python datetime.
Postgres, via `asyncpg`, rejected the mismatch outright rather than
silently guessing.

**Why SQLite never caught this:** SQLite doesn't actually enforce or even
represent timezone-awareness on datetime columns — it just stores whatever
string or number you give it. The bug was invisible in every test run, and
only surfaced against a real Postgres server. This is the single best
argument for actually running your project in Docker against the real
database before considering it done, rather than trusting a green test
suite alone.

**The fix:** two parts.
1. Made all three `created_at` columns explicitly `DateTime(timezone=True)`
   in the SQLAlchemy models.
2. Wrote a second Alembic migration
   (`8a6822d42a4b_make_created_at_columns_timezone_aware.py`) to alter the
   already-created columns on Postgres. This one had to be **hand-written**,
   not autogenerated — `alembic revision --autogenerate` diffs against
   SQLite in this project's dev workflow, and SQLite can't detect a
   timezone-awareness change it doesn't model in the first place. The
   migration uses `postgresql_using` to tell Postgres how to reinterpret
   the existing naive values (`AT TIME ZONE 'UTC'`) during the conversion.

This is a genuinely good story to tell in an interview: not just "I built
a feature" but "I hit a subtle infrastructure bug, correctly diagnosed
*why* my tests hadn't caught it, and fixed it at the right layer."

---

## Running it for real

```bash
docker compose up --build
```

This pulls Postgres 16, builds the API image, waits for Postgres's
healthcheck to pass, then automatically runs `alembic upgrade head`
(applying both migrations) before starting Uvicorn.

```bash
curl http://127.0.0.1:8000/ping
# {"status":"ok","message":"pong"}
```

Then open **http://127.0.0.1:8000/docs** — FastAPI's auto-generated
interactive page. Every endpoint below can be tried directly from there,
with a "Try it out" button and a real request/response shown live. No
separate frontend is needed or built for this project (same as Week 1
before `notes.html` was added).

To inspect the actual tables inside the running container:

```bash
docker compose exec postgres psql -U shop_user -d shopping -c "\dt"
```

---

## Running tests (no Docker required)

```bash
pip install -r requirements.txt
pytest -v
```

10 tests, all passing, against a temporary file-based SQLite database created
fresh per test — no live Postgres needed for the suite, same philosophy as
`mongomock-motor` in Week 1's Notes API.

---

## API surface

| Method & path | Purpose |
|---|---|
| `GET /ping` | Health check |
| `POST /users` | Create a user |
| `GET /users/{id}` | Fetch a user |
| `POST /categories` | Create a category |
| `GET /categories` | List categories |
| `GET /categories/{id}` | Fetch a category |
| `POST /products` | Create a product (also creates its inventory row) |
| `GET /products` | List products, optional `?category_id=` filter, includes live stock |
| `GET /products/{id}` | Fetch one product with its current stock |
| `POST /orders` | Place an order (one or more line items); atomically decrements stock per item |
| `GET /orders/{id}` | Fetch an order with its line items |

---

## Generating a new migration after changing models

```bash
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```

Always review the autogenerated file before trusting it — as this project's
own timezone migration shows, autogenerate diffs against whatever database
your dev environment points at, and it can miss changes that database
doesn't model (see the case study above).

---

## What's deliberately not done yet

Stated honestly, not hidden:

- **No auth/authz** on any endpoint — same gap as Week 1, not yet in scope.
- **No order status transitions.** Every order is created as `status:
  "pending"` and stays there — there's no `PATCH /orders/{id}` to move it to
  `paid` or `cancelled`. A `cancelled` transition would also need to
  *restore* the decremented stock, which hasn't been built.
- **No pagination** on `GET /products` or `GET /categories` — fine for now,
  would matter at real scale.
- **No warehouse/multi-location inventory** — `inventory` is 1:1 with
  `products` today; the schema was deliberately designed so this could
  become 1:N later without touching `products` at all.