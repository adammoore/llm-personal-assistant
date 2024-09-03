"""
Prompt system for the LLM-powered personal assistant.

This module defines the structure for prompts and provides functionality
to retrieve and manage prompts for different time periods.
"""

from sqlalchemy import Column, Integer, String, Enum, ForeignKey, DateTime, select
from sqlalchemy.orm import relationship
from sqlalchemy.ext.asyncio import AsyncSession
from database import Base
import enum
from datetime import datetime
from typing import List

class TimeperiodEnum(enum.Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"

class Prompt(Base):
    __tablename__ = "prompts"

    id = Column(Integer, primary_key=True, index=True)
    question = Column(String, nullable=False)
    timeperiod = Column(Enum(TimeperiodEnum), nullable=False)

    responses = relationship("PromptResponse", back_populates="prompt")

class PromptResponse(Base):
    __tablename__ = "prompt_responses"

    id = Column(Integer, primary_key=True, index=True)
    prompt_id = Column(Integer, ForeignKey("prompts.id"))
    response = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    prompt = relationship("Prompt", back_populates="responses")

# Sample prompts
SAMPLE_PROMPTS = [
    {"question": "What are your main goals for today?", "timeperiod": TimeperiodEnum.DAILY},
    {"question": "Are there any important deadlines coming up this week?", "timeperiod": TimeperiodEnum.WEEKLY},
    {"question": "What long-term projects do you need to make progress on this month?", "timeperiod": TimeperiodEnum.MONTHLY},
    {"question": "Are there any tasks you've been procrastinating on?", "timeperiod": TimeperiodEnum.WEEKLY},
    {"question": "Do you have any appointments or meetings to schedule?", "timeperiod": TimeperiodEnum.DAILY},
    {"question": "What self-care activities do you want to prioritize this week?", "timeperiod": TimeperiodEnum.WEEKLY},
    {"question": "Are there any skills you want to work on improving this month?", "timeperiod": TimeperiodEnum.MONTHLY},
    {"question": "Do you need to follow up on any communications today?", "timeperiod": TimeperiodEnum.DAILY},
    {"question": "What tasks depend on other tasks or people?", "timeperiod": TimeperiodEnum.WEEKLY},
    {"question": "What do you want to achieve in your free time this month?", "timeperiod": TimeperiodEnum.MONTHLY},
]

async def initialize_prompts(db: AsyncSession):
    """Initialize the database with sample prompts if it's empty."""
    result = await db.execute(select(Prompt))
    existing_prompts = result.scalars().all()

    if not existing_prompts:
        for prompt_data in SAMPLE_PROMPTS:
            prompt = Prompt(**prompt_data)
            db.add(prompt)
        await db.commit()

async def get_prompts_for_timeperiod(db: AsyncSession, timeperiod: TimeperiodEnum) -> List[Prompt]:
    """Retrieve prompts for a specific time period."""
    result = await db.execute(select(Prompt).filter(Prompt.timeperiod == timeperiod))
    return result.scalars().all()

async def save_prompt_response(db: AsyncSession, prompt_id: int, response: str):
    """Save a user's response to a prompt."""
    prompt_response = PromptResponse(prompt_id=prompt_id, response=response)
    db.add(prompt_response)
    await db.commit()
    await db.refresh(prompt_response)
    return prompt_response

async def get_prompt_by_id(db: AsyncSession, prompt_id: int):
    """Retrieve a prompt by its ID."""
    result = await db.execute(select(Prompt).filter(Prompt.id == prompt_id))
    return result.scalar_one_or_none()

async def get_daily_prompt(db: AsyncSession):
    """Retrieve the daily prompt."""
    result = await db.execute(select(Prompt).filter(Prompt.timeperiod == TimeperiodEnum.DAILY))
    return result.scalar_one_or_none()
