"""
LLM integration module for analyzing prompt responses and generating tasks and calendar events.
"""

from config import settings
import requests
import json
from integrations import google_calendar
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from modules import task_manager
from modules.prompt_system import Prompt
import dateparser

import logging
logger = logging.getLogger(__name__)

# Anthropic API configuration
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/complete"
ANTHROPIC_API_KEY = settings.ANTHROPIC_API_KEY
ANTHROPIC_API_VERSION = "2023-06-01"

async def analyze_prompt_response(prompt: str, response: str):
    """
    Analyze a user's response to a prompt and generate tasks and calendar events.
    """
    system_prompt = f"""You are an AI assistant helping to manage tasks and schedules for someone with ADHD. 
    Analyze the following prompt and response, then suggest tasks to be added to their to-do list 
    and events to be added to their calendar. Format your response as a JSON object with 'tasks' 
    and 'events' keys. Each task should have 'title', 'description', and 'due_date' fields. 
    Each event should have 'title', 'start_time', and 'end_time' fields."""

    user_prompt = f"Prompt: {prompt}\nResponse: {response}"

    headers = {
        "Content-Type": "application/json",
        "X-API-Key": ANTHROPIC_API_KEY,
        "anthropic-version": ANTHROPIC_API_VERSION
    }

    data = {
        "prompt": f"Human: {system_prompt}\n\n{user_prompt}\n\nAssistant:",
        "model": "claude-v1",
        "max_tokens_to_sample": 300,
        "stop_sequences": ["Human:"]
    }

    try:
        response = requests.post(ANTHROPIC_API_URL, headers=headers, json=data)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"API request failed: {e}")
        raise

    result = response.json()
    logger.debug(f"API Response: {result}")

    # Extract the completion from the API response
    completion = result.get('completion', '')
    logger.debug(f"Completion: {completion}")

    # Find the start of the JSON object in the completion
    json_start = completion.find('{')
    json_end = completion.rfind('}') + 1
    if json_start == -1 or json_end == 0:
        logger.error("No JSON object found in the API response")
        raise ValueError("No JSON object found in the API response")

    # Extract and parse the JSON object
    try:
        json_str = completion[json_start:json_end]
        logger.debug(f"Extracted JSON string: {json_str}")
        parsed_result = json.loads(json_str)
        logger.debug(f"Parsed result: {parsed_result}")
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON from the API response: {e}")
        raise ValueError("Failed to parse JSON from the API response")

    return parsed_result


def parse_date(date_string):
    """
    Parse a date string into a datetime object.
    """
    if not date_string:
        return None

    parsed_date = dateparser.parse(date_string)
    if parsed_date:
        return parsed_date.date()
    else:
        logger.error(f"Unable to parse date: {date_string}")
        return None


def parse_time(time_string):
    """
    Parse a time string into a datetime object.
    """
    if not time_string:
        return None

    parsed_time = dateparser.parse(time_string)
    if parsed_time:
        return parsed_time.time()
    else:
        logger.error(f"Unable to parse time: {time_string}")
        return None


async def process_prompt_response(db: AsyncSession, prompt: Prompt, response: str):
    """
    Process a user's response to a prompt, analyze it with the LLM, and create tasks and calendar events.
    """
    analysis = await analyze_prompt_response(prompt.question, response)
    logger.debug(f"Analysis result: {analysis}")

    if not isinstance(analysis, dict):
        logger.error(f"Unexpected analysis type: {type(analysis)}")
        raise TypeError(f"Expected dict, got {type(analysis)}")

    # Create tasks
    for task_data in analysis.get('tasks', []):
        if not isinstance(task_data, dict):
            logger.error(f"Unexpected task_data type: {type(task_data)}")
            continue

        due_date = parse_date(task_data.get('due_date'))

        await task_manager.create_task(
            db,
            task_data.get('title', 'Untitled Task'),
            task_data.get('description', ''),
            due_date
        )


    # Create calendar events
    for event_data in analysis.get('events', []):
        if not isinstance(event_data, dict):
            logger.error(f"Unexpected event_data type: {type(event_data)}")
            continue

        start_date = parse_date(event_data.get('start_date', event_data.get('date')))
        end_date = parse_date(event_data.get('end_date', event_data.get('date')))
        start_time = parse_time(event_data.get('start_time'))
        end_time = parse_time(event_data.get('end_time'))

        # If no date is specified, use today's date
        if not start_date:
            start_date = datetime.now().date()
        if not end_date:
            end_date = start_date

        if start_time:
            start_datetime = datetime.combine(start_date, start_time)
        else:
            logger.error(f"Unable to determine start time for event: {event_data}")
            continue

        if end_time:
            end_datetime = datetime.combine(end_date, end_time)
        else:
            # If no end time is provided, assume the event is 1 hour long
            end_datetime = start_datetime + timedelta(hours=1)

        await create_calendar_event(
            db,
            event_data.get('title', 'Untitled Event'),
            start_datetime.isoformat(),
            end_datetime.isoformat()
        )

    return analysis


async def create_calendar_event(db: AsyncSession, title: str, start_time: str, end_time: str):
    """
    Create a calendar event using the Google Calendar API.
    """
    if not start_time or not end_time:
        logger.error(f"Error creating calendar event: Missing start_time or end_time for event '{title}'")
        return None

    event = {
        'summary': title,
        'start': {
            'dateTime': start_time,
            'timeZone': 'UTC',
        },
        'end': {
            'dateTime': end_time,
            'timeZone': 'UTC',
        },
    }

    try:
        created_event = await google_calendar.create_event(event)
        return created_event
    except Exception as e:
        logger.error(f"Error creating calendar event: {e}")
        return None
