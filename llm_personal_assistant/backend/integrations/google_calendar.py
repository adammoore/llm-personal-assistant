"""
Google Calendar integration module for the LLM-powered personal assistant.

This module handles the authentication and interaction with the Google Calendar API.
"""

import os
import pickle
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']


def get_calendar_service():
    """
    Authenticate and return a Google Calendar service object.
    """
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = Flow.from_client_secrets_file(
                'client_secret.json', SCOPES)
            creds = flow.run_local_server(port=0)

        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    return build('calendar', 'v3', credentials=creds)


async def get_upcoming_events(days=7):
    """
    Retrieve upcoming events from the user's Google Calendar.

    Args:
        days (int): Number of days to look ahead for events.

    Returns:
        list: A list of upcoming events.
    """
    service = get_calendar_service()
    now = datetime.utcnow().isoformat() + 'Z'
    time_max = (datetime.utcnow() + timedelta(days=days)).isoformat() + 'Z'

    events_result = service.events().list(calendarId='primary', timeMin=now,
                                          timeMax=time_max, singleEvents=True,
                                          orderBy='startTime').execute()
    events = events_result.get('items', [])

    return events

# Add more functions as needed for calendar operations