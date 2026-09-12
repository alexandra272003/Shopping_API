from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.schemas import CategoryCreate, CategoryRead
from app.services import category_service

router = APIRouter(prefix="/categories", tags=["categories"])


@router.post("", response_model=CategoryRead, status_code=status.HTTP_201_CREATED)
async def create_category(payload: CategoryCreate, session: AsyncSession = Depends(get_session)):
    return await category_service.create_category(session, payload)


@router.get("", response_model=list[CategoryRead])
async def list_categories(session: AsyncSession = Depends(get_session)):
    return await category_service.list_categories(session)


@router.get("/{category_id}", response_model=CategoryRead)
async def get_category(category_id: int, session: AsyncSession = Depends(get_session)):
    return await category_service.get_category(session, category_id)
