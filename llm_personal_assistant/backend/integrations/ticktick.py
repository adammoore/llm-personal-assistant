"""
TickTick integration module for the LLM-powered personal assistant.

This module handles the interaction with the TickTick API for task management.
"""

import requests
import os
from datetime import datetime, timedelta
from typing import Optional
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# TickTick API configuration
TICKTICK_API_URL = "https://api.ticktick.com/open/v1"
TICKTICK_AUTH_URL = "https://ticktick.com/oauth/authorize"
TICKTICK_TOKEN_URL = "https://ticktick.com/oauth/token"
TICKTICK_CLIENT_ID = os.environ.get("TICKTICK_CLIENT_ID")
TICKTICK_CLIENT_SECRET = os.environ.get("TICKTICK_CLIENT_SECRET")
TICKTICK_REDIRECT_URI = os.environ.get("TICKTICK_REDIRECT_URI")

class TickTickAuth:
    def __init__(self):
        self.access_token = None
        self.refresh_token = None
        self.expires_at = None

    def get_auth_url(self):
        """Generate the TickTick authorization URL."""
        params = {
            "client_id": TICKTICK_CLIENT_ID,
            "scope": "tasks:read tasks:write",
            "response_type": "code",
            "redirect_uri": TICKTICK_REDIRECT_URI,
        }
        return f"{TICKTICK_AUTH_URL}?{'&'.join(f'{k}={v}' for k, v in params.items())}"

    def get_tokens(self, code):
        """Exchange authorization code for access and refresh tokens."""
        data = {
            "client_id": TICKTICK_CLIENT_ID,
            "client_secret": TICKTICK_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": TICKTICK_REDIRECT_URI,
        }
        response = requests.post(TICKTICK_TOKEN_URL, data=data)
        response.raise_for_status()
        token_data = response.json()
        self.access_token = token_data["access_token"]
        self.refresh_token = token_data["refresh_token"]
        self.expires_at = datetime.now() + timedelta(seconds=token_data["expires_in"])
        return token_data

    def refresh_tokens(self):
        """Refresh the access token using the refresh token."""
        data = {
            "client_id": TICKTICK_CLIENT_ID,
            "client_secret": TICKTICK_CLIENT_SECRET,
            "refresh_token": self.refresh_token,
            "grant_type": "refresh_token",
        }
        response = requests.post(TICKTICK_TOKEN_URL, data=data)
        response.raise_for_status()
        token_data = response.json()
        self.access_token = token_data["access_token"]
        self.refresh_token = token_data["refresh_token"]
        self.expires_at = datetime.now() + timedelta(seconds=token_data["expires_in"])
        return token_data

    def get_headers(self):
        """Get the headers for TickTick API requests, refreshing the token if necessary."""
        if not self.access_token or datetime.now() >= self.expires_at:
            self.refresh_tokens()
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

ticktick_auth = TickTickAuth()

def api_request(method, endpoint, data=None):
    """
    Make an API request to TickTick with automatic token refresh.

    Args:
        method (str): HTTP method (e.g., 'GET', 'POST', 'PUT', 'DELETE').
        endpoint (str): API endpoint.
        data (dict, optional): Request data for POST or PUT requests.

    Returns:
        dict: JSON response from the API.

    Raises:
        Exception: If the API request fails after token refresh.
    """
    try:
        response = requests.request(method, f"{TICKTICK_API_URL}{endpoint}", headers=ticktick_auth.get_headers(), json=data)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error occurred: {e}")
        if e.response.status_code == 401:
            logger.info("Attempting to refresh token...")
            ticktick_auth.refresh_tokens()
            response = requests.request(method, f"{TICKTICK_API_URL}{endpoint}", headers=ticktick_auth.get_headers(), json=data)
            response.raise_for_status()
            return response.json()
        raise
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        raise

def get_tasks():
    """
    Retrieve tasks from TickTick.

    Returns:
        list: A list of tasks.
    """
    return api_request("GET", "/task")

def create_task(title: str, description: Optional[str] = None, due_date: Optional[datetime] = None):
    """
    Create a new task in TickTick.

    Args:
        title (str): The title of the task.
        description (str, optional): The description of the task.
        due_date (datetime, optional): The due date of the task.

    Returns:
        dict: The created task.
    """
    data = {
        "title": title,
        "content": description,
        "dueDate": due_date.isoformat() if due_date else None
    }
    return api_request("POST", "/task", data)

def update_task(task_id: str, title: Optional[str] = None, description: Optional[str] = None,
                due_date: Optional[datetime] = None, completed: Optional[bool] = None):
    """
    Update an existing task in TickTick.

    Args:
        task_id (str): The ID of the task to update.
        title (str, optional): The updated title of the task.
        description (str, optional): The updated description of the task.
        due_date (datetime, optional): The updated due date of the task.
        completed (bool, optional): The updated completion status of the task.

    Returns:
        dict: The updated task.
    """
    data = {}
    if title is not None:
        data["title"] = title
    if description is not None:
        data["content"] = description
    if due_date is not None:
        data["dueDate"] = due_date.isoformat()
    if completed is not None:
        data["status"] = 2 if completed else 0

    return api_request("POST", f"/task/{task_id}", data)

def delete_task(task_id: str):
    """
    Delete a task from TickTick.

    Args:
        task_id (str): The ID of the task to delete.

    Returns:
        bool: True if the task was successfully deleted, False otherwise.
    """
    try:
        api_request("DELETE", f"/task/{task_id}")
        return True
    except requests.exceptions.HTTPError:
        return False