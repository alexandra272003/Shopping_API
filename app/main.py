from fastapi import FastAPI

from app.core.errors import AppError, app_error_handler
from app.routers import categories, orders, products, users

app = FastAPI(title="Shopping API")

app.add_exception_handler(AppError, app_error_handler)

app.include_router(users.router)
app.include_router(categories.router)
app.include_router(products.router)
app.include_router(orders.router)


@app.get("/ping")
async def ping():
    return {"status": "ok", "message": "pong"}
