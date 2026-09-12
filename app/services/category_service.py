from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.repositories import category_repository as repo
from app.repositories.category_repository import DuplicateCategoryError
from app.schemas import CategoryCreate, CategoryRead


async def create_category(session: AsyncSession, payload: CategoryCreate) -> CategoryRead:
    try:
        category = await repo.create_category(session, payload.name)
    except DuplicateCategoryError as e:
        raise ConflictError(str(e))
    return CategoryRead.model_validate(category)


async def get_category(session: AsyncSession, category_id: int) -> CategoryRead:
    category = await repo.get_category(session, category_id)
    if category is None:
        raise NotFoundError(f"Category {category_id} not found")
    return CategoryRead.model_validate(category)


async def list_categories(session: AsyncSession) -> list[CategoryRead]:
    categories = await repo.list_categories(session)
    return [CategoryRead.model_validate(c) for c in categories]
