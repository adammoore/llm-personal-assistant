import os
import logging
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/calendar.readonly', 'https://www.googleapis.com/auth/calendar.events']
CLIENT_SECRETS_FILE = "client_secret.json"
TOKEN_FILE = "token.json"

def get_calendar_service():
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
    except Exception as e:
        logger.error(f"Error retrieving calendar events: {str(e)}")
        raise

async def handle_oauth2_callback(request: Request):
    try:
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE, 
            scopes=SCOPES, 
            state=request.query_params.get('state')
        )
        flow.redirect_uri = "http://localhost:8000/oauth2callback"

        authorization_response = str(request.url)
        flow.fetch_token(authorization_response=authorization_response)

        credentials = flow.credentials
        with open(TOKEN_FILE, 'w') as token:
            token.write(credentials.to_json())

        logger.info("Successfully authenticated with Google Calendar")
        return RedirectResponse(url="http://localhost:3000")
    except Exception as e:
        logger.error(f"Error in OAuth2 callback: {str(e)}")
        raise HTTPException(status_code=500, detail=f"OAuth2 callback failed: {str(e)}")

async def create_event(event_data):
    try:
        service = get_calendar_service()
        event = service.events().insert(calendarId='primary', body=event_data).execute()
        logger.info(f"Event created: {event.get('htmlLink')}")
        return event
    except Exception as e:
        logger.error(f"Error creating calendar event: {str(e)}")
        raise