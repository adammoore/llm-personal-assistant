"""
Main application module for the LLM-powered personal assistant.

This module sets up the FastAPI application and includes the main router.
It also initializes the database connection and other necessary components.
"""

import uvicorn
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import init_db, get_db, engine
from modules import task_manager, prompt_system, llm_integration
from integrations.google_calendar import get_upcoming_events, handle_oauth2_callback, get_calendar_service
from scheduler import start_scheduler
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
    async with AsyncSession(engine) as session:
        await prompt_system.initialize_prompts(session)
    start_scheduler()

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

@app.get("/prompts/{timeperiod}")
async def get_prompts(timeperiod: prompt_system.TimeperiodEnum, db: AsyncSession = Depends(get_db)):
    """Retrieve prompts for a specific time period."""
    prompts = await prompt_system.get_prompts_for_timeperiod(db, timeperiod)
    return prompts

class PromptResponse(BaseModel):
    prompt_id: int
    response: str

@app.post("/prompts/respond")
async def respond_to_prompt(prompt_response: PromptResponse, db: AsyncSession = Depends(get_db)):
    """Save a user's response to a prompt and process it with LLM."""
    response = await prompt_system.save_prompt_response(db, prompt_response.prompt_id, prompt_response.response)
    prompt = await prompt_system.get_prompt_by_id(db, prompt_response.prompt_id)
    analysis = await llm_integration.process_prompt_response(db, prompt, prompt_response.response)
    return {"response": response, "analysis": analysis}

@app.get("/calendar/events")
async def get_calendar_events(days: int = 7):
    """Retrieve upcoming events from Google Calendar."""
    try:
        events = await get_upcoming_events(days)
        return {"events": events}
    except FileNotFoundError:
        return {"events": [], "message": "Google Calendar integration not set up. Please add client_secret.json to the backend directory."}
    except HTTPException as e:
        if e.status_code == 302:
            return RedirectResponse(e.headers["Location"])
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/oauth2callback")
async def oauth2_callback(request: Request):
    """Handle the OAuth2 callback from Google."""
    try:
        result = await handle_oauth2_callback(request)
        return RedirectResponse(url="http://localhost:3000")  # Redirect to frontend after successful authentication
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/refresh_calendar_auth")
async def refresh_calendar_auth():
    """Endpoint to manually trigger calendar re-authentication."""
    try:
        get_calendar_service()  # This will trigger re-authentication if needed
        return {"message": "Calendar authentication refreshed successfully"}
    except HTTPException as e:
        if e.status_code == 302:
            return RedirectResponse(e.headers["Location"])
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)