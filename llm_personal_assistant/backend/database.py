"""
Database module for the LLM-powered personal assistant.

This module sets up the SQLAlchemy engine and session,
and provides a base class for database models.
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import NullPool

from config import settings

# Create async engine
engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)

# Create async session
AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

Base = declarative_base()

async def init_db():
    """Initialize the database by creating all tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_db():
    """Dependency for database session."""
    async with AsyncSessionLocal() as session:
        yield session