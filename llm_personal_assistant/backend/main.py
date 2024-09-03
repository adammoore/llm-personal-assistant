"""
Main application module for the LLM-powered personal assistant.

This module sets up the FastAPI application and includes the main router.
It also initializes the database connection and other necessary components.
"""

import uvicorn
from fastapi import FastAPI, Depends, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from config import settings
from database import init_db, get_db, engine
from modules import task_manager, prompt_system, llm_integration
from integrations import google_calendar, ticktick
from scheduler import start_scheduler
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv
load_dotenv()

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
    async with AsyncSession(engine) as session:
        await prompt_system.initialize_prompts(session)
    start_scheduler()


@app.get("/")
async def root():
    """Root endpoint for testing purposes."""
    return {"message": "Welcome to the LLM Personal Assistant"}


@app.get("/prompts/daily")
async def get_daily_prompt(db: AsyncSession = Depends(get_db)):
    """Retrieve the daily prompt."""
    prompt = await prompt_system.get_daily_prompt(db)
    return {"prompt": prompt.question if prompt else "No daily prompt available."}


@app.get("/tasks/")
async def get_tasks(source: Optional[str] = Query(None), db: AsyncSession = Depends(get_db)):
    """
    Retrieve a list of tasks from either local storage or TickTick.

    Args:
        source (str, optional): The source of tasks ('ticktick' or None for local).
        db (AsyncSession): The database session.

    Returns:
        list: A list of tasks.
    """
    if source == 'ticktick':
        return ticktick.get_tasks()
    else:
        return await task_manager.get_tasks(db)


@app.post("/tasks/")
async def create_task(
        task: task_manager.TaskCreate,
        source: Optional[str] = Query(None),
        db: AsyncSession = Depends(get_db)
):
    """
    Create a new task in either local storage or TickTick.

    Args:
        task (TaskCreate): The task to create.
        source (str, optional): The source to create the task in ('ticktick' or None for local).
        db (AsyncSession): The database session.

    Returns:
        dict: The created task.
    """
    if source == 'ticktick':
        return ticktick.create_task(task.title, task.description, task.due_date)
    else:
        return await task_manager.create_task(db, task)


@app.put("/tasks/{task_id}")
async def update_task(
        task_id: str,
        task: task_manager.TaskUpdate,
        source: Optional[str] = Query(None),
        db: AsyncSession = Depends(get_db)
):
    """
    Update an existing task in either local storage or TickTick.

    Args:
        task_id (str): The ID of the task to update.
        task (TaskUpdate): The updated task data.
        source (str, optional): The source to update the task in ('ticktick' or None for local).
        db (AsyncSession): The database session.

    Returns:
        dict: The updated task.
    """
    if source == 'ticktick':
        return ticktick.update_task(task_id, task.title, task.description, task.due_date, task.completed)
    else:
        return await task_manager.update_task(db, task_id, task)


@app.delete("/tasks/{task_id}")
async def delete_task(
        task_id: str,
        source: Optional[str] = Query(None),
        db: AsyncSession = Depends(get_db)
):
    """
    Delete a task from either local storage or TickTick.

    Args:
        task_id (str): The ID of the task to delete.
        source (str, optional): The source to delete the task from ('ticktick' or None for local).
        db (AsyncSession): The database session.

    Returns:
        dict: A message indicating success or failure.
    """
    if source == 'ticktick':
        success = ticktick.delete_task(task_id)
    else:
        success = await task_manager.delete_task(db, task_id)

    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"message": "Task deleted successfully"}


@app.get("/calendar/events")
async def get_calendar_events(days: int = 7):
    """
    Retrieve upcoming events from Google Calendar.

    Args:
        days (int): Number of days to look ahead for events. Defaults to 7.

    Returns:
        dict: A dictionary containing events or error messages.

    Raises:
        HTTPException: If there's an error retrieving events.
    """
    try:
        events = await google_calendar.get_upcoming_events(days)
        return {"events": events}
    except FileNotFoundError:
        return {
            "events": [],
            "message": "Google Calendar integration not set up. Please add client_secret.json to the backend directory.",
        }
    except HTTPException as e:
        if e.status_code == 302:
            return RedirectResponse(e.headers["Location"])
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/oauth2callback")
async def oauth2_callback(request: Request):
    """
    Handle the OAuth2 callback from Google.

    Args:
        request (Request): The incoming request object.

    Returns:
        RedirectResponse: Redirects to the frontend after successful authentication.

    Raises:
        HTTPException: If there's an error during the OAuth2 callback process.
    """
    try:
        result = await google_calendar.handle_oauth2_callback(request)
        return RedirectResponse(url="http://localhost:3000")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/refresh_calendar_auth")
async def refresh_calendar_auth():
    """
    Endpoint to manually trigger calendar re-authentication.

    Returns:
        dict: A message indicating successful authentication refresh.

    Raises:
        HTTPException: If there's an error during the re-authentication process.
    """
    try:
        google_calendar.get_calendar_service()  # This will trigger re-authentication if needed
        return {"message": "Calendar authentication refreshed successfully"}
    except HTTPException as e:
        if e.status_code == 302:
            return RedirectResponse(e.headers["Location"])
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/ai-autonomy")
async def get_ai_autonomy():
    """Get the current AI autonomy setting."""
    return {"autonomous": llm_integration.get_ai_autonomy()}


@app.post("/ai-autonomy")
async def set_ai_autonomy(autonomous: bool):
    """Set the AI autonomy setting."""
    llm_integration.set_ai_autonomy(autonomous)
    return {"message": "AI autonomy setting updated", "autonomous": autonomous}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
