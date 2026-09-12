# Shopping System — ER Diagram (Day 7 design)

## Entities and relationships

```
users
  id (PK)
  username (unique)
  email (unique)
  created_at

categories
  id (PK)
  name (unique)

products
  id (PK)
  name
  price
  category_id (FK -> categories.id)
  created_at

inventory
  id (PK)
  product_id (FK -> products.id, UNIQUE)   -- 1:1 with products
  quantity

orders
  id (PK)
  user_id (FK -> users.id)
  status (pending / paid / cancelled)
  created_at

order_items
  id (PK)
  order_id (FK -> orders.id)
  product_id (FK -> products.id)
  quantity
  unit_price     -- snapshot of price at purchase time, NOT a live FK to products.price
```

## Cardinality

- users -> orders: **1:N** (one user has many orders)
- categories -> products: **1:N** (one category has many products)
- products -> inventory: **1:1** (each product has exactly one stock row)
- orders -> order_items: **1:N** (one order has many line items)
- products -> order_items: **1:N** (one product appears in many order line items,
  across many different orders) — this is the classic **many-to-many between
  orders and products**, resolved through the order_items junction table.

## Why order_items exists (junction table reasoning)

An order can contain many products, and a product can appear in many orders.
That's a many-to-many relationship, and relational databases can't express
many-to-many directly with just a foreign key — you need a junction
(association) table in between. order_items is that table: it carries its
own primary key, two foreign keys (order_id, product_id), plus attributes
that belong to the *relationship itself* (quantity, unit_price) rather than
to either order or product alone.

## Why unit_price is duplicated on order_items instead of joining to products.price

Product prices change over time. If order_items only stored product_id and
we looked up the price via JOIN at read time, a past order's total would
silently change every time the product's price changed. Snapshotting
unit_price at the moment of purchase is what keeps historical orders
accurate — this is a deliberate denormalization, not an oversight.

## Why inventory is a separate table instead of a quantity column on products

Keeping stock as its own table with its own row means stock updates
(decrementing on purchase) can be locked and updated independently of the
product's descriptive data (name, price, category). It also leaves room
for this to become 1:N later (e.g. per-warehouse stock) without touching
the products table at all.

## Normalization check (3NF)

- 1NF: every column holds a single atomic value — yes across all tables.
- 2NF: no partial dependency on a composite key — all tables use a single
  surrogate integer PK, so this is automatically satisfied.
- 3NF: no transitive dependency (a non-key column depending on another
  non-key column). The one deliberate exception is order_items.unit_price,
  which is a documented denormalization for historical accuracy (see above),
  not an accident.
