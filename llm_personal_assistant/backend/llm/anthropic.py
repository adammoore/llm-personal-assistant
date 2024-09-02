"""
Anthropic LLM integration module for the personal assistant.

This module provides functions to interact with the Anthropic API
for natural language processing tasks.
"""

import anthropic
from config import settings

client = anthropic.Client(api_key=settings.ANTHROPIC_API_KEY)

async def generate_response(prompt: str, max_tokens: int = 1000) -> str:
    """
    Generate a response using the Anthropic LLM.

    Args:
        prompt (str): The input prompt for the LLM.
        max_tokens (int): Maximum number of tokens in the response.

    Returns:
        str: The generated response from the LLM.
    """
    try:
        response = client.completion(
            prompt=f"{anthropic.HUMAN_PROMPT} {prompt}{anthropic.AI_PROMPT}",
            model="claude-2.0",
            max_tokens_to_sample=max_tokens,
            stop_sequences=[anthropic.HUMAN_PROMPT],
        )
        return response.completion.strip()
    except Exception as e:
        print(f"Error in generate_response: {e}")
        return "I apologize, but I encountered an error while processing your request."

async def analyze_task(task_description: str) -> dict:
    """
    Analyze a task description and extract key information.

    Args:
        task_description (str): The description of the task.

    Returns:
        dict: A dictionary containing analyzed task information.
    """
    prompt = f"""
    Analyze the following task description and extract key information:
    Task: {task_description}

    Please provide the following information:
    1. Estimated time to complete
    2. Priority level (High, Medium, Low)
    3. Main steps or subtasks
    4. Any potential blockers or dependencies

    Format the response as a JSON object.
    """
    response = await generate_response(prompt)
    # Note: In a production environment, you'd want to add error handling
    # and validation for the JSON parsing.
    import json
    return json.loads(response)

# Add more functions as needed for different LLM interactions