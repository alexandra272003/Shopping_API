from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.repositories import order_repository as repo
from app.schemas import OrderCreate, OrderRead


async def create_order(session: AsyncSession, payload: OrderCreate) -> OrderRead:
    items = [item.model_dump() for item in payload.items]
    order = await repo.create_order(session, user_id=payload.user_id, items=items)
    return OrderRead.model_validate(order)


async def get_order(session: AsyncSession, order_id: int) -> OrderRead:
    order = await repo.get_order(session, order_id)
    if order is None:
        raise NotFoundError(f"Order {order_id} not found")
    return OrderRead.model_validate(order)
