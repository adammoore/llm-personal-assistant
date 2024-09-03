"""
Task management module for the LLM-powered personal assistant.

This module handles the creation, retrieval, updating, and deletion of tasks.
It also integrates with the LLM for task analysis and scheduling suggestions.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database import Task
from datetime import datetime

async def create_task(db: AsyncSession, title: str, description: str, due_date: datetime = None) -> Task:
    """Create a new task."""
    task = Task(title=title, description=description, due_date=due_date)
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task

async def get_tasks(db: AsyncSession, skip: int = 0, limit: int = 100):
    """Retrieve a list of tasks."""
    result = await db.execute(select(Task).offset(skip).limit(limit))
    return result.scalars().all()

async def update_task(db: AsyncSession, task_id: int, **kwargs):
    """Update an existing task."""
    result = await db.execute(select(Task).filter(Task.id == task_id))
    task = result.scalar_one_or_none()
    if task:
        for key, value in kwargs.items():
            setattr(task, key, value)
        await db.commit()
        await db.refresh(task)
    return task

async def delete_task(db: AsyncSession, task_id: int):
    """Delete a task."""
    result = await db.execute(select(Task).filter(Task.id == task_id))
    task = result.scalar_one_or_none()
    if task:
        await db.delete(task)
        await db.commit()
        return True
    return False