from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Inventory, Product


async def create_product(
    session: AsyncSession, name: str, price: float, category_id: int, initial_quantity: int
) -> Product:
    product = Product(name=name, price=price, category_id=category_id)
    session.add(product)
    await session.flush()  # get product.id before creating inventory row

    inventory = Inventory(product_id=product.id, quantity=initial_quantity)
    session.add(inventory)

    await session.commit()
    await session.refresh(product)
    return product


async def get_product(session: AsyncSession, product_id: int) -> Product | None:
    return await session.get(Product, product_id)


async def get_product_with_stock(session: AsyncSession, product_id: int):
    result = await session.execute(
        select(Product, Inventory.quantity)
        .join(Inventory, Inventory.product_id == Product.id)
        .where(Product.id == product_id)
    )
    row = result.first()
    if row is None:
        return None
    product, quantity = row
    return product, quantity


async def list_products(session: AsyncSession, category_id: int | None = None):
    stmt = select(Product, Inventory.quantity).join(
        Inventory, Inventory.product_id == Product.id
    )
    if category_id is not None:
        stmt = stmt.where(Product.category_id == category_id)
    stmt = stmt.order_by(Product.id)
    result = await session.execute(stmt)
    return result.all()
