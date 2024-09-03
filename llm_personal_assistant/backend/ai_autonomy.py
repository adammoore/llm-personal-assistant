import os

AI_AUTONOMY_FILE = "ai_autonomy.txt"

def get_ai_autonomy():
    if os.path.exists(AI_AUTONOMY_FILE):
        with open(AI_AUTONOMY_FILE, 'r') as f:
            return f.read().strip().lower() == 'true'
    return False

def set_ai_autonomy(autonomy: bool):
    with open(AI_AUTONOMY_FILE, 'w') as f:
        f.write(str(autonomy).lower())

def check_ai_autonomy(func):
    def wrapper(*args, **kwargs):
        if get_ai_autonomy():
            return func(*args, **kwargs)
        else:
            # Here, you would implement logic to ask for user confirmation
            # For now, we'll just return a message
            return {"message": "AI action requires user confirmation", "action": func.__name__}
    return wrapper

# Example usage:
@check_ai_autonomy
def ai_create_task(title, description):
    # Logic to create a task
    pass

@check_ai_autonomy
def ai_schedule_event(title, start_time, end_time):
    # Logic to schedule an event
    pass