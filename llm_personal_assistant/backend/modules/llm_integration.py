"""
LLM integration module for analyzing prompt responses and generating tasks and calendar events.
"""

from config import settings
import anthropic
from integrations import google_calendar
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from modules import task_manager
from modules.prompt_system import Prompt

client = anthropic.Client(api_key=settings.ANTHROPIC_API_KEY)

# Specify the Anthropic API version
ANTHROPIC_API_VERSION = "2023-06-01"  # Replace with the current version

async def analyze_prompt_response(prompt: str, response: str):
    """
    Analyze a user's response to a prompt and generate tasks and calendar events.
    """
    system_prompt = f"""You are an AI assistant helping to manage tasks and schedules for someone with ADHD. 
    Analyze the following prompt and response, then suggest tasks to be added to their to-do list 
    and events to be added to their calendar. Format your response as a JSON object with 'tasks' 
    and 'events' keys."""

    user_prompt = f"Prompt: {prompt}\nResponse: {response}"

    response = client.completion(
        prompt=f"{anthropic.HUMAN_PROMPT} {system_prompt}\n\n{user_prompt}{anthropic.AI_PROMPT}",
        model="claude-v1",
        max_tokens_to_sample=300,
        stop_sequences=[anthropic.HUMAN_PROMPT],
        anthropic_version=ANTHROPIC_API_VERSION  # Add this line
    )

    # Parse the JSON response and return it
    import json
    return json.loads(response.completion)

async def process_prompt_response(db: AsyncSession, prompt: Prompt, response: str):
    """
    Process a user's response to a prompt, analyze it with the LLM, and create tasks and calendar events.
    """
    analysis = await analyze_prompt_response(prompt.question, response)

    # Create tasks
    for task_data in analysis['tasks']:
        await task_manager.create_task(db, task_data['title'], task_data.get('description', ''), task_data.get('due_date'))

    # Create calendar events
    for event_data in analysis['events']:
        await create_calendar_event(db, event_data['title'], event_data['start_time'], event_data['end_time'])

    return analysis

async def create_calendar_event(db: AsyncSession, title: str, start_time: str, end_time: str):
    """
    Create a calendar event using the Google Calendar API.
    """
    # Convert string times to datetime objects
    start = datetime.fromisoformat(start_time)
    end = datetime.fromisoformat(end_time)

    event = {
        'summary': title,
        'start': {
            'dateTime': start.isoformat(),
            'timeZone': 'UTC',
        },
        'end': {
            'dateTime': end.isoformat(),
            'timeZone': 'UTC',
        },
    }

    try:
        created_event = await google_calendar.create_event(event)
        return created_event
    except Exception as e:
        print(f"Error creating calendar event: {e}")
        return None