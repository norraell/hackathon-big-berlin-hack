"""Database connection and session management."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool

from app.config import settings

logger = logging.getLogger(__name__)


# Create async engine for PostgreSQL
def get_async_engine():
    """Create async SQLAlchemy engine.
    
    Returns:
        Async engine instance
    """
    # Convert postgresql:// to postgresql+asyncpg://
    async_url = settings.database_url.replace("postgresql://", "postgresql+asyncpg://")
    
    engine = create_async_engine(
        async_url,
        echo=settings.log_level == "DEBUG",
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        pool_recycle=3600,
    )
    
    return engine


# Create sync engine for migrations and scripts
def get_sync_engine():
    """Create sync SQLAlchemy engine.
    
    Returns:
        Sync engine instance
    """
    engine = create_engine(
        settings.database_url,
        echo=settings.log_level == "DEBUG",
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        pool_recycle=3600,
    )
    
    return engine


# Global engine instances
async_engine = get_async_engine()
sync_engine = get_sync_engine()

# Session factories
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

SyncSessionLocal = sessionmaker(
    sync_engine,
    class_=Session,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Get async database session.
    
    Yields:
        Async database session
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}", exc_info=True)
            raise
        finally:
            await session.close()


def get_sync_session() -> Session:
    """Get sync database session.
    
    Returns:
        Sync database session
    """
    return SyncSessionLocal()


async def init_db():
    """Initialize database tables.
    
    This should be called during application startup.
    """
    from app.claims.models import Base as ClaimsBase
    from app.claims.insurant_models import Base as InsurantBase
    
    logger.info("Initializing database tables...")
    
    try:
        # Create all tables
        async with async_engine.begin() as conn:
            # Import all models to ensure they're registered
            await conn.run_sync(ClaimsBase.metadata.create_all)
            await conn.run_sync(InsurantBase.metadata.create_all)
        
        logger.info("Database tables initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}", exc_info=True)
        raise


async def close_db():
    """Close database connections.
    
    This should be called during application shutdown.
    """
    logger.info("Closing database connections...")
    
    try:
        await async_engine.dispose()
        sync_engine.dispose()
        logger.info("Database connections closed successfully")
    except Exception as e:
        logger.error(f"Error closing database connections: {e}", exc_info=True)


# Dependency for FastAPI endpoints
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database sessions.
    
    Yields:
        Database session
    """
    async with get_async_session() as session:
        yield session