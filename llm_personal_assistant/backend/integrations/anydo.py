import requests
import os

ANYDO_API_URL = "https://sm-prod2.any.do/api/v2"
ANYDO_TOKEN = os.environ.get("ANYDO_TOKEN")

headers = {
    "X-Anydo-Auth": ANYDO_TOKEN,
    "Content-Type": "application/json"
}


def get_tasks():
    response = requests.get(f"{ANYDO_API_URL}/me/tasks", headers=headers)
    return response.json()


def create_task(title, description=None):
    data = {
        "title": title,
        "description": description
    }
    response = requests.post(f"{ANYDO_API_URL}/me/tasks", json=data, headers=headers)
    return response.json()


def update_task(task_id, title=None, description=None, completed=None):
    data = {}
    if title:
        data["title"] = title
    if description:
        data["description"] = description
    if completed is not None:
        data["status"] = "CHECKED" if completed else "UNCHECKED"

    response = requests.patch(f"{ANYDO_API_URL}/me/tasks/{task_id}", json=data, headers=headers)
    return response.json()


def delete_task(task_id):
    response = requests.delete(f"{ANYDO_API_URL}/me/tasks/{task_id}", headers=headers)
    return response.status_code == 204