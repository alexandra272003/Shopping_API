from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.repositories import product_repository as repo
from app.schemas import ProductCreate, ProductRead, ProductWithStock


async def create_product(session: AsyncSession, payload: ProductCreate) -> ProductRead:
    product = await repo.create_product(
        session,
        name=payload.name,
        price=payload.price,
        category_id=payload.category_id,
        initial_quantity=payload.initial_quantity,
    )
    return ProductRead.model_validate(product)


async def get_product(session: AsyncSession, product_id: int) -> ProductWithStock:
    row = await repo.get_product_with_stock(session, product_id)
    if row is None:
        raise NotFoundError(f"Product {product_id} not found")
    product, quantity = row
    return ProductWithStock(**ProductRead.model_validate(product).model_dump(), quantity=quantity)


async def list_products(
    session: AsyncSession, category_id: int | None = None
) -> list[ProductWithStock]:
    rows = await repo.list_products(session, category_id)
    return [
        ProductWithStock(**ProductRead.model_validate(p).model_dump(), quantity=q)
        for p, q in rows
    ]
