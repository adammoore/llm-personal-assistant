"""
Google Calendar integration module for the LLM-powered personal assistant.

This module handles the authentication and interaction with the Google Calendar API.
"""

import os
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from fastapi import HTTPException
from googleapiclient.errors import HttpError

SCOPES = ['https://www.googleapis.com/auth/calendar']  # This scope allows read and write access
CLIENT_SECRETS_FILE = "client_secret.json"
TOKEN_FILE = "token.json"

# Allow OAuth2 insecure transport for local development
if os.environ.get('ENVIRONMENT') == "development":
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

def get_calendar_service():
    if not os.path.exists(CLIENT_SECRETS_FILE):
        raise FileNotFoundError(f"'{CLIENT_SECRETS_FILE}' not found. Please download it from Google Cloud Console.")

    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = Flow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
            flow.redirect_uri = "http://localhost:8000/oauth2callback"
            authorization_url, _ = flow.authorization_url(prompt='consent')
            raise HTTPException(status_code=302, headers={"Location": authorization_url})

        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())

    return build('calendar', 'v3', credentials=creds)

async def get_upcoming_events(days=7):
    try:
        service = get_calendar_service()
        now = datetime.utcnow().isoformat() + 'Z'
        time_max = (datetime.utcnow() + timedelta(days=days)).isoformat() + 'Z'

        events_result = service.events().list(calendarId='primary', timeMin=now,
                                              timeMax=time_max, singleEvents=True,
                                              orderBy='startTime').execute()
        events = events_result.get('items', [])

        return events
    except FileNotFoundError as e:
        print(f"Error: {str(e)}")
        return []
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error retrieving calendar events: {e}")
        return []

async def handle_oauth2_callback(request):
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES, state=request.query_params.get('state'))
    flow.redirect_uri = "http://localhost:8000/oauth2callback"

    authorization_response = str(request.url)
    flow.fetch_token(authorization_response=authorization_response)

    credentials = flow.credentials
    with open(TOKEN_FILE, 'w') as token:
        token.write(credentials.to_json())

    return {"message": "Successfully authenticated with Google Calendar"}

async def create_event(event_data):
    """
    Create a new event in Google Calendar.

    Args:
        event_data (dict): A dictionary containing event details.

    Returns:
        dict: The created event data returned by Google Calendar API.
    """
    try:
        service = get_calendar_service()
        event = service.events().insert(calendarId='primary', body=event_data).execute()
        print(f"Event created: {event.get('htmlLink')}")
        return event
    except HttpError as e:
        print(f"An error occurred: {e}")
        if e.resp.status == 403 and "insufficient authentication scopes" in str(e):
            # Token might be outdated, try to refresh
            os.remove(TOKEN_FILE)
            service = get_calendar_service()  # This will trigger re-authentication
            event = service.events().insert(calendarId='primary', body=event_data).execute()
            print(f"Event created after re-authentication: {event.get('htmlLink')}")
            return event
        else:
            raise
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        raise