from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ---------- Categories ----------
class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class CategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


# ---------- Products ----------
class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    price: float = Field(gt=0)
    category_id: int
    initial_quantity: int = Field(default=0, ge=0)


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    price: float
    category_id: int
    created_at: datetime


class ProductWithStock(ProductRead):
    quantity: int


# ---------- Users ----------
class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    email: str
    created_at: datetime


# ---------- Orders ----------
class OrderItemCreate(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)


class OrderCreate(BaseModel):
    user_id: int
    items: list[OrderItemCreate] = Field(min_length=1)


class OrderItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    product_id: int
    quantity: int
    unit_price: float


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    status: str
    created_at: datetime
    items: list[OrderItemRead]
