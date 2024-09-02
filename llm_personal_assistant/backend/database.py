"""
Database module for the LLM-powered personal assistant.

This module sets up the SQLAlchemy engine and session,
and provides a base class for database models.
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.pool import NullPool
from datetime import datetime

from config import settings

# Create async engine
engine = create_async_engine(settings.DATABASE_URL.replace("sqlite:///", "sqlite+aiosqlite:///"), poolclass=NullPool)

# Create async session
AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

Base = declarative_base()

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(String)
    due_date = Column(DateTime, nullable=True)
    completed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

async def init_db():
    """Initialize the database by creating all tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_db():
    """Dependency for database session."""
    async with AsyncSessionLocal() as session:
        yield session