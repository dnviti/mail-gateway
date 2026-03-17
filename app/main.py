import asyncio
import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from app.api.admin import router as admin_router
from app.api.webhooks import router as webhooks_router
from app.config import settings
from app.db.database import close_db, init_db
from app.services.retention_service import retention_loop

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    app.state.httpx_client = httpx.AsyncClient(timeout=30.0)

    # Start background retention/TTL cleanup task
    retention_task = asyncio.create_task(retention_loop())
    logger.info("Retention background task started")

    yield

    # Gracefully cancel the retention task on shutdown
    retention_task.cancel()
    try:
        await retention_task
    except asyncio.CancelledError:
        logger.info("Retention background task stopped")

    await app.state.httpx_client.aclose()
    await close_db()


app = FastAPI(
    title=settings.APP_NAME,
    lifespan=lifespan,
)

app.include_router(webhooks_router, prefix="/webhooks", tags=["webhooks"])
app.include_router(admin_router, prefix="/admin", tags=["admin"])


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": settings.APP_NAME}
