"""
calendar_warm.py
----------------
Generates "Circadian Telemetry" by interacting with the Calendar grid, 
clicking the native 'Create' button, typing LLM-generated events, 
and occasionally adding locations or descriptions (High Trust Signals).
"""

import asyncio
import logging
import random
from playwright.async_api import Page

from behavior_engine import (
    human_type, 
    smart_wait, 
    lognormal_delay, 
    click_humanly, 
    move_mouse_humanly
)
from llm_helper import generate_dynamic_search

log = logging.getLogger(__name__)

async def add_event_entropy(page: Page, behavior: dict, persona_name: str):
    """Macro-Entropy: Simulates a user deciding to add a location or description."""
    try:
        # 30% Chance to add a generic location
        if random.random() < 0.30:
            loc_btn = page.locator("div[aria-label='Add location'], input[aria-label='Location']").first
            if await loc_btn.is_visible(timeout=2000):
                log.info(f"    📍 [{persona_name}] Adding a location to the event...")
                await click_humanly(page, loc_btn, behavior)
                await asyncio.sleep(random.uniform(0.5, 1.5))
                locations = ["Zoom", "Office", "Starbucks", "Downtown", "Phone Call", "Home"]
                await human_type(page, "input[aria-label='Location'], input[placeholder='Add location']", random.choice(locations), behavior)
                await asyncio.sleep(random.uniform(1.0, 2.0))
                await page.keyboard.press("Enter")

        # 20% Chance to add a brief description
        if random.random() < 0.20:
            desc_btn = page.locator("div[aria-label='Add description'], textarea[aria-label='Description']").first
            if await desc_btn.is_visible(timeout=2000):
                log.info(f"    📝 [{persona_name}] Adding an event description...")
                await click_humanly(page, desc_btn, behavior)
                await asyncio.sleep(random.uniform(0.5, 1.5))
                descriptions = ["Make sure to prepare notes.", "Catch up sync.", "Review action items.", "Monthly check-in."]
                await human_type(page, "textarea[aria-label='Description'], div[aria-label='Description']", random.choice(descriptions), behavior)
                await asyncio.sleep(random.uniform(1.0, 2.0))
    except Exception as e:
        log.debug(f"Event entropy skipped or interrupted: {e}")

async def calendar_warm_session(page: Page, profile: dict):
    persona_name = profile.get("persona", {}).get("name", "UnknownBot")
    behavior = profile.get("behavior", {})
    
    log.info(f"📅 [{persona_name}] Starting Google Calendar session...")

    # 1. Ask the AI to write a realistic event title
    event_title = await generate_dynamic_search(profile, platform="Google Calendar Event")
    
    # 2. ORGANIC NAVIGATION: Load the main calendar grid
    log.info(f"    🌐 [{persona_name}] Loading main calendar grid...")
    await page.goto("https://calendar.google.com/calendar/u/0/r", wait_until="domcontentloaded")
    await smart_wait(page, timeout=12000)

    try:
        # 3. Simulate looking at the calendar (Reviewing the week)
        log.info(f"    👀 [{persona_name}] Reviewing upcoming schedule...")
        await move_mouse_humanly(page, random.randint(300, 800), random.randint(200, 600))
        await asyncio.sleep(random.uniform(3.0, 7.0))

        # 4. Physically click the "Create" button
        log.info(f"    🖱️ [{persona_name}] Initiating event creation...")
        create_btn = page.locator("div[aria-label='Create'], button:has-text('Create')").first
        
        if await create_btn.is_visible(timeout=5000):
            await click_humanly(page, create_btn, behavior)
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
            # Click "Event" from the dropdown if it appears
            event_option = page.locator("div[role='menuitem']:has-text('Event'), span:has-text('Event')").first
            if await event_option.is_visible(timeout=3000):
                await click_humanly(page, event_option, behavior)
        else:
            log.warning(f"    ⚠️ [{persona_name}] Create button not found. Aborting calendar flow.")
            return

        await smart_wait(page, timeout=5000)

        # 5. Type the event title organically
        log.info(f"    ⌨️ [{persona_name}] Scheduling event: '{event_title}'")
        title_box = "input[aria-label='Title'], input[placeholder='Add title']"
        await human_type(page, title_box, event_title, behavior)
        await asyncio.sleep(random.uniform(1.0, 2.5))

        # 6. MACRO-ENTROPY: Add Location or Description
        await add_event_entropy(page, behavior, persona_name)

        # 7. Save the event using Fitts's Law click
        save_btn = page.locator("button:has-text('Save'), div[role='button']:has-text('Save')").first
        if await save_btn.is_visible(timeout=3000):
            await click_humanly(page, save_btn, behavior)
            log.info(f"    ✅ [{persona_name}] Event saved to calendar successfully.")
            await asyncio.sleep(lognormal_delay(3000, 6000))
        else:
            log.warning(f"    ⚠️ [{persona_name}] Could not find the Save button.")

    except Exception as e:
        log.error(f"    ❌ [{persona_name}] Failed to interact with Google Calendar: {e}")