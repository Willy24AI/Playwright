"""
drive_warm.py
-------------
Generates Storage Telemetry. Navigates to Google Drive, organizes files, 
and uses the LLM to create mathematically unique, human-like folder names.
Features action variance (sometimes it just browses, sometimes it creates).
"""

import asyncio
import logging
import random
from playwright.async_api import Page
from behavior_engine import move_mouse_humanly, smart_wait, lognormal_delay, human_scroll, idle_reading
from llm_helper import generate_dynamic_search

log = logging.getLogger(__name__)

async def drive_warm_session(page: Page, profile: dict):
    persona_name = profile.get("persona", {}).get("name", "UnknownBot")
    behavior = profile.get("behavior", {})
    
    log.info(f"💾 [{persona_name}] Starting Google Drive asset warming...")

    # 1. Navigate to Drive
    await page.goto("https://drive.google.com/drive/my-drive", wait_until="domcontentloaded")
    await smart_wait(page, timeout=15000)

    try:
        # 2. Idle Browsing (Look at existing files before deciding what to do)
        log.info(f"👀 [{persona_name}] Reviewing Drive dashboard...")
        await idle_reading(page, {**behavior, "read_pause_range": (2, 5)})
        
        # Scroll the Drive interface slightly (Drive uses internal divs for scrolling, 
        # but general mouse wheel events usually work)
        await human_scroll(page, behavior)
        await asyncio.sleep(random.uniform(1.5, 3.5))

        # 3. Action Variance: 60% chance to create a folder, 40% chance to just browse
        if random.random() < 0.60:
            # --- CREATE FOLDER FLOW ---
            
            # Generate a hyper-realistic folder name using the LLM
            folder_name = await generate_dynamic_search(profile, platform="Drive Folder")
            log.info(f"🖱️ [{persona_name}] Organizing... Creating folder: '{folder_name}'")

            # Click "New" Button
            new_btn = page.locator("button:has-text('New'), button[aria-label='New']").first
            await new_btn.click()
            await asyncio.sleep(random.uniform(1.0, 2.5))

            # Click "New folder"
            folder_option = page.locator("div[role='menuitem']:has-text('New folder'), div[aria-label='New folder']").first
            await folder_option.click()
            await smart_wait(page, timeout=5000)

            # Wait for the modal dialog to appear and type the name
            # Google Drive's folder creation modal usually autofocuses the input
            await page.keyboard.type(folder_name, delay=random.randint(80, 200)) # Human typing speed
            await asyncio.sleep(random.uniform(0.5, 1.2))
            
            # Click "Create" or press Enter
            await page.keyboard.press("Enter")
            
            log.info(f"✅ [{persona_name}] Successfully created folder: '{folder_name}'")
            await asyncio.sleep(lognormal_delay(2000, 4000))
            
        else:
            # --- BROWSE ONLY FLOW ---
            log.info(f"🤷 [{persona_name}] Decided not to create anything today. Just browsing.")
            
            # Randomly click into an existing folder or file if visible, 
            # otherwise just wiggle the mouse
            files = await page.locator("div[role='row'], div[data-target='item']").all()
            if files and len(files) > 1:
                target = random.choice(files[1:5]) # Skip the first one, usually a header
                box = await target.bounding_box()
                if box:
                    await move_mouse_humanly(page, box["x"] + box["width"]/2, box["y"] + box["height"]/2)
                    await asyncio.sleep(random.uniform(0.5, 1.5))
            
            await asyncio.sleep(random.uniform(2.0, 5.0))
            log.info(f"✅ [{persona_name}] Drive browse session complete.")

    except Exception as e:
        log.error(f"❌ [{persona_name}] Drive warming failed: {e}")