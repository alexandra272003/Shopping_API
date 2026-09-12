from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.schemas import ProductCreate, ProductRead, ProductWithStock
from app.services import product_service

router = APIRouter(prefix="/products", tags=["products"])


@router.post("", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
async def create_product(payload: ProductCreate, session: AsyncSession = Depends(get_session)):
    return await product_service.create_product(session, payload)


@router.get("", response_model=list[ProductWithStock])
async def list_products(
    category_id: int | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
):
    return await product_service.list_products(session, category_id)


@router.get("/{product_id}", response_model=ProductWithStock)
async def get_product(product_id: int, session: AsyncSession = Depends(get_session)):
    return await product_service.get_product(session, product_id)
