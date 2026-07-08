"""
main.py

FastAPI application entry point. Wire up routers, middleware, and startup lifespan database initialization.
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.database import init_db
from api.routes import router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles startup database initialization and cleanup."""
    logger.info("Initializing database...")
    init_db()
    yield
    logger.info("Shutdown completed.")

app = FastAPI(
    title="UAV Design System API",
    description="REST API backend exposing aerodynamic core design and optimization orchestrators.",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS for Dashboard integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(router)

@app.get("/", summary="Health check endpoint")
def root():
    return {
        "status": "healthy",
        "service": "UAV Design Intelligence System API",
        "version": "1.0.0"
    }
