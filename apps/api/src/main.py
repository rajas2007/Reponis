from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.config import settings
from src.core.logging import setup_logging
from src.modules.auth.router import router as auth_router
from src.modules.repositories.router import router as repositories_router

setup_logging()

app = FastAPI(
    title="Reponis API",
    description="Backend API for Reponis engineering intelligence platform",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(repositories_router, prefix="/api/v1")


@app.get("/health", tags=["System"])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
