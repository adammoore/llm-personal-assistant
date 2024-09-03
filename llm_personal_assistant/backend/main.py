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
from integrations.google_calendar import (
    get_upcoming_events,
    handle_oauth2_callback,
    get_calendar_service,
)
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
        events = await get_upcoming_events(days)
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
        result = await handle_oauth2_callback(request)
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