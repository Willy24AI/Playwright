"""
calendar_warm.py
----------------
Generates "Circadian Telemetry" by adding a realistic, LLM-generated 
event to the bot's personal Google Calendar.
"""

import asyncio
import logging
import random
from playwright.async_api import Page

from behavior_engine import human_type, smart_wait, lognormal_delay
from llm_helper import generate_dynamic_search

log = logging.getLogger(__name__)

async def calendar_warm_session(page: Page, profile: dict):
    persona_name = profile.get("persona", {}).get("name", "UnknownBot")
    behavior = profile.get("behavior", {})
    
    log.info(f"📅 [{persona_name}] Starting Google Calendar session...")

    # 1. Ask the AI to write a realistic event title
    event_title = await generate_dynamic_search(profile, platform="Google Calendar Event")
    
    # 2. Navigate directly to the "Create Event" endpoint (Bypasses complex UI clicking)
    log.info(f"🚀 [{persona_name}] Opening new calendar event page...")
    await page.goto("https://calendar.google.com/calendar/u/0/r/eventedit", wait_until="domcontentloaded")
    await smart_wait(page, timeout=12000)

    try:
        log.info(f"⌨️ [{persona_name}] Scheduling event: '{event_title}'")
        
        # 3. Type the event title into the main input box
        # Google uses aria-labels heavily for accessibility, which is great for Playwright
        await human_type(page, "input[aria-label='Title'], input[placeholder='Add title']", event_title, behavior)
        await asyncio.sleep(random.uniform(1.5, 3.0))

        # 4. Save the event (High Trust Signal)
        save_btn = page.locator("button:has-text('Save'), div[role='button']:has-text('Save')").first
        if await save_btn.is_visible(timeout=3000):
            await save_btn.click()
            log.info(f"✅ [{persona_name}] Event saved to calendar successfully.")
            await asyncio.sleep(lognormal_delay(2000, 4000))
        else:
            log.warning(f"⚠️ [{persona_name}] Could not find the Save button.")

    except Exception as e:
        log.error(f"❌ [{persona_name}] Failed to interact with Google Calendar: {e}")