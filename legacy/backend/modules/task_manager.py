"""
Task management module for the LLM-powered personal assistant.

This module handles the creation, retrieval, updating, and deletion of tasks.
"""

from sqlalchemy.orm import Session
from sqlalchemy.future import select
from database import Task
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    due_date: Optional[datetime] = None

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    completed: Optional[bool] = None

async def create_task(db: Session, task: TaskCreate):
    db_task = Task(**task.dict())
    db.add(db_task)
    await db.commit()
    await db.refresh(db_task)
    return db_task

async def get_tasks(db: Session, skip: int = 0, limit: int = 100):
    query = select(Task).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

async def update_task(db: Session, task_id: int, task: TaskUpdate):
    query = select(Task).filter(Task.id == task_id)
    result = await db.execute(query)
    db_task = result.scalar_one_or_none()
    if db_task:
        update_data = task.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_task, key, value)
        await db.commit()
        await db.refresh(db_task)
    return db_task

async def delete_task(db: Session, task_id: int):
    query = select(Task).filter(Task.id == task_id)
    result = await db.execute(query)
    db_task = result.scalar_one_or_none()
    if db_task:
        await db.delete(db_task)
        await db.commit()
        return True
    return False