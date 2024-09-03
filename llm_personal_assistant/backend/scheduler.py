"""
Scheduler module for triggering prompts at appropriate intervals.
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from modules import prompt_system
from database import AsyncSessionLocal
from config import settings

scheduler = AsyncIOScheduler()

async def trigger_daily_prompts():
    async with AsyncSessionLocal() as session:
        prompts = await prompt_system.get_prompts_for_timeperiod(session, prompt_system.TimeperiodEnum.DAILY)
        # Here you would typically send a notification or email to the user
        # For now, we'll just print the prompts
        print("Daily prompts:", [p.question for p in prompts])

async def trigger_weekly_prompts():
    async with AsyncSessionLocal() as session:
        prompts = await prompt_system.get_prompts_for_timeperiod(session, prompt_system.TimeperiodEnum.WEEKLY)
        print("Weekly prompts:", [p.question for p in prompts])

async def trigger_monthly_prompts():
    async with AsyncSessionLocal() as session:
        prompts = await prompt_system.get_prompts_for_timeperiod(session, prompt_system.TimeperiodEnum.MONTHLY)
        print("Monthly prompts:", [p.question for p in prompts])

def start_scheduler():
    scheduler.add_job(trigger_daily_prompts, CronTrigger(hour=9))  # Run daily at 9 AM
    scheduler.add_job(trigger_weekly_prompts, CronTrigger(day_of_week='mon', hour=9))  # Run weekly on Mondays at 9 AM
    scheduler.add_job(trigger_monthly_prompts, CronTrigger(day=1, hour=9))  # Run monthly on the 1st at 9 AM
    scheduler.start()