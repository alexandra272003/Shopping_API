import tempfile
import os

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.core.db import Base, get_session
from app.main import app


@pytest_asyncio.fixture
async def engine():
    """
    A temp-file-backed SQLite db (not :memory:) so multiple connections/
    sessions can all see the same schema and data -- this matters for the
    concurrency test, which needs two independent sessions racing against
    the same row, just like two real concurrent requests would in production.
    """
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    url = f"sqlite+aiosqlite:///{path}?timeout=5"

    eng = create_async_engine(url, future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield eng

    await eng.dispose()
    os.remove(path)


@pytest_asyncio.fixture
async def client(engine):
    """
    Overrides get_session to open a FRESH session per call, exactly like
    production's one-session-per-request pattern. This is what makes the
    concurrent-order test meaningful -- each concurrent request gets its
    own session/connection, so the atomic UPDATE...WHERE in the repository
    is what enforces correctness, not test scaffolding.
    """
    SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)

    async def override_get_session():
        async with SessionLocal() as s:
            yield s

    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
