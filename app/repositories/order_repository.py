from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InsufficientStockError, NotFoundError
from app.models import Inventory, Order, OrderItem, Product


async def create_order(session: AsyncSession, user_id: int, items: list[dict]) -> Order:
    """
    Creates an order and atomically decrements stock for every line item.

    Concurrency safety: instead of "SELECT quantity, check in Python, then
    UPDATE" (which has a race window between the read and the write), we do
    a single atomic UPDATE that both checks and decrements in one statement:

        UPDATE inventory SET quantity = quantity - :qty
        WHERE product_id = :pid AND quantity >= :qty

    The WHERE quantity >= :qty clause means the row only updates if there's
    enough stock. If two requests race for the last unit, the database
    guarantees only one UPDATE can succeed — the second sees rowcount == 0
    and we raise InsufficientStockError, rolling back the whole order.
    This is what "SELECT then check then UPDATE" cannot guarantee under
    concurrent load.
    """
    order = Order(user_id=user_id, status="pending")
    session.add(order)
    await session.flush()  # get order.id

    for item in items:
        product = await session.get(Product, item["product_id"])
        if product is None:
            await session.rollback()
            raise NotFoundError(f"Product {item['product_id']} not found")

        result = await session.execute(
            update(Inventory)
            .where(
                Inventory.product_id == item["product_id"],
                Inventory.quantity >= item["quantity"],
            )
            .values(quantity=Inventory.quantity - item["quantity"])
        )

        if result.rowcount == 0:
            await session.rollback()
            raise InsufficientStockError(
                f"Not enough stock for product {item['product_id']}",
                details={"product_id": item["product_id"], "requested": item["quantity"]},
            )

        order_item = OrderItem(
            order_id=order.id,
            product_id=item["product_id"],
            quantity=item["quantity"],
            unit_price=product.price,
        )
        session.add(order_item)

    await session.commit()
    await session.refresh(order, attribute_names=["items"])
    return order


async def get_order(session: AsyncSession, order_id: int) -> Order | None:
    result = await session.execute(
        select(Order).where(Order.id == order_id)
    )
    order = result.scalar_one_or_none()
    if order is not None:
        await session.refresh(order, attribute_names=["items"])
    return order
