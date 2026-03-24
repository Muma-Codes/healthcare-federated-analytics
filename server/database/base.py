"""
SQLAlchemy engine, session factory and declarative Base.
All model files import Base from here.
"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from config import settings

# Engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    connect_args={"check_same_thread": False},
)

AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

Base = declarative_base()


# Session dependency

async def get_db():
    """FastAPI dependency - yields an async session, commits on success."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """
    Create all tables from all registered models.
    Must be called AFTER all model files have been imported
    so that their classes are registered on Base.metadata.
    Called once at application startup in main.py lifespan.
    """
    # Import every model so it registers itself on Base.metadata
    from database.models import user, audit_log, prediction_log, session_model, training_completion

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)