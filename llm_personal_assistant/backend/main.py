"""
Main application module for the LLM-powered personal assistant.

This module sets up the FastAPI application and includes the main router.
It also initializes the database connection and other necessary components.
"""

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database import init_db

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

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)