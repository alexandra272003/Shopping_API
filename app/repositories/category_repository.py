from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category


class DuplicateCategoryError(Exception):
    pass


async def create_category(session: AsyncSession, name: str) -> Category:
    category = Category(name=name)
    session.add(category)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise DuplicateCategoryError(f"Category '{name}' already exists")
    await session.refresh(category)
    return category


async def get_category(session: AsyncSession, category_id: int) -> Category | None:
    return await session.get(Category, category_id)


async def list_categories(session: AsyncSession) -> list[Category]:
    result = await session.execute(select(Category).order_by(Category.name))
    return list(result.scalars().all())
