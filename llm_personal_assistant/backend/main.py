"""
Main application module for the LLM-powered personal assistant.

This module sets up the FastAPI application and includes the main router.
It also initializes the database connection and other necessary components.
"""

import uvicorn
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import init_db, get_db
from modules import task_manager
from integrations import google_calendar
from pydantic import BaseModel
from datetime import datetime

app = FastAPI(title="LLM Personal Assistant", version="0.1.0")

# Set up CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    """Initialize database and other startup tasks."""
    await init_db()

@app.get("/")
async def root():
    """Root endpoint for testing purposes."""
    return {"message": "Welcome to the LLM Personal Assistant"}
class TaskCreate(BaseModel):
    title: str
    description: str
    due_date: datetime = None

@app.post("/tasks/")
async def create_task(task: TaskCreate, db: AsyncSession = Depends(get_db)):
    """Create a new task."""
    return await task_manager.create_task(db, task.title, task.description, task.due_date)

@app.get("/tasks/")
async def read_tasks(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    """Retrieve a list of tasks."""
    return await task_manager.get_tasks(db, skip=skip, limit=limit)

@app.put("/tasks/{task_id}")
async def update_task(task_id: int, task: TaskCreate, db: AsyncSession = Depends(get_db)):
    """Update an existing task."""
    updated_task = await task_manager.update_task(db, task_id, **task.dict())
    if updated_task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return updated_task

@app.delete("/tasks/{task_id}")
async def delete_task(task_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a task."""
    success = await task_manager.delete_task(db, task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"message": "Task deleted successfully"}

@app.get("/calendar/events")
async def get_calendar_events(days: int = 7):
    """Retrieve upcoming events from Google Calendar."""
    try:
        events = await google_calendar.get_upcoming_events(days)
        return {"events": events}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)