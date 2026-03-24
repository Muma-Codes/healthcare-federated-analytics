"""
Predictive Healthcare Analytics — FastAPI Application

Entry point. Registers all routers, configures CORS and middleware,
initialises the database and seeds default users on first run.

Run locally:
    uvicorn main:app --reload --port 8000
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from auth.routes import router as auth_router
from config import settings
from database.base import init_db
from database.seed import seed_database
from federated.routes import router as fl_router
from middleware.audit_routes import admin_router, training_router

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


# Lifespan (replaces deprecated @app.on_event)
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s v%s…", settings.APP_NAME, settings.APP_VERSION)
    await init_db()
    await seed_database()
    logger.info("Database ready.")
    yield
    logger.info("Shutting down.")


# App
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Distributed predictive healthcare model using Federated Learning "
        "to detect early signs of chronic diseases while preserving patient data privacy."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception on %s: %s", request.url, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred. Please contact the administrator."},
    )


# Routers
app.include_router(auth_router)
app.include_router(fl_router)
app.include_router(admin_router)
app.include_router(training_router)


# Health check
@app.get("/health", tags=["System"])
async def health():
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


@app.get("/", tags=["System"])
async def root():
    return {
        "message": f"Welcome to {settings.APP_NAME} API.",
        "docs": "/docs",
        "health": "/health",
    }