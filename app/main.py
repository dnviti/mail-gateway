from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.api.admin import router as admin_router
from app.api.webhooks import router as webhooks_router
from app.config import settings
from app.db.database import close_db, init_db
from app.middleware.rate_limiter import limiter


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_db()


app = FastAPI(
    title=settings.APP_NAME,
    lifespan=lifespan,
)


async def _rate_limit_handler(request, exc: RateLimitExceeded):
    """Return a generic 429 response without leaking internal rate limit details."""
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Please try again later."},
        headers={"Retry-After": exc.detail.split(" ")[-1] if exc.detail else "60"},
    )


# Register rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)

app.include_router(webhooks_router, prefix="/webhooks", tags=["webhooks"])
app.include_router(admin_router, prefix="/admin", tags=["admin"])


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": settings.APP_NAME}
