"""
drive_warm.py
-------------
Generates Storage Telemetry. Navigates to Google Drive, organizes files, 
uses Fitts's Law clicking, organic typing for folder creation, and 
simulates UI fidgeting (toggling layouts) to bypass SPA telemetry.
"""

import asyncio
import logging
import random
from playwright.async_api import Page
from behavior_engine import (
    move_mouse_humanly, 
    smart_wait, 
    lognormal_delay, 
    human_scroll, 
    idle_reading,
    click_humanly,
    human_type
)
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
        # 2. Idle Browsing & UI Fidgeting
        log.info(f"    👀 [{persona_name}] Reviewing Drive dashboard...")
        await idle_reading(page, {**behavior, "read_pause_range": (2, 5)})
        await human_scroll(page, behavior)
        
        # MACRO-ENTROPY: 25% chance to toggle the layout view (List vs Grid)
        if random.random() < 0.25:
            layout_btn = page.locator("button[aria-label*='layout' i]").first
            if await layout_btn.is_visible(timeout=2000):
                log.info(f"    🔄 [{persona_name}] Toggling Drive layout view...")
                await click_humanly(page, layout_btn, behavior)
                await asyncio.sleep(random.uniform(2.0, 4.0))

        # 3. Action Variance: 60% chance to create a folder, 40% chance to just browse
        if random.random() < 0.60:
            # --- CREATE FOLDER FLOW ---
            folder_name = await generate_dynamic_search(profile, platform="Drive Folder")
            log.info(f"    🖱️ [{persona_name}] Organizing... Creating folder: '{folder_name}'")

            # Click "New" Button using Fitts's Law
            new_btn = page.locator("button:has-text('New'), button[aria-label='New'], span:has-text('New')").first
            if await new_btn.is_visible(timeout=5000):
                await click_humanly(page, new_btn, behavior)
                await asyncio.sleep(random.uniform(1.0, 2.5))

                # Click "New folder"
                folder_option = page.locator("div[role='menuitem']:has-text('New folder'), div[aria-label='New folder']").first
                if await folder_option.is_visible(timeout=3000):
                    await click_humanly(page, folder_option, behavior)
                    await smart_wait(page, timeout=5000)

                    # Wait for the modal dialog and type the name organically
                    log.info(f"    ⌨️ [{persona_name}] Typing folder name...")
                    
                    # Google Drive's modal input usually has type='text'.
                    # If it's already focused, human_type will clear it and type.
                    modal_input = "input[type='text']" 
                    if await page.locator(modal_input).is_visible(timeout=3000):
                        await human_type(page, modal_input, folder_name, behavior)
                    else:
                        # Fallback if selector fails but input is focused
                        for char in folder_name:
                            await page.keyboard.type(char, delay=random.uniform(70, 120))
                            await asyncio.sleep(lognormal_delay(50, 150))
                            
                    await asyncio.sleep(random.uniform(0.5, 1.2))
                    
                    # Press Enter to submit
                    await page.keyboard.press("Enter", delay=random.uniform(80, 150))
                    
                    log.info(f"    ✅ [{persona_name}] Successfully created folder: '{folder_name}'")
                    await asyncio.sleep(lognormal_delay(3000, 6000))
                else:
                    log.warning(f"    ⚠️ [{persona_name}] 'New Folder' menu item not found.")
            else:
                log.warning(f"    ⚠️ [{persona_name}] 'New' button not found.")
                
        else:
            # --- BROWSE ONLY FLOW ---
            log.info(f"    🤷 [{persona_name}] Decided not to create anything today. Just browsing.")
            
            # Hover over a random file/folder organically (No geometric centers)
            files = await page.locator("div[role='row'], div[data-target='item']").all()
            if files and len(files) > 1:
                target = random.choice(files[1:5]) # Skip the first one (often a header)
                box = await target.bounding_box()
                if box:
                    # Hover randomly within the item's bounds
                    hover_x = box["x"] + box["width"] * random.uniform(0.2, 0.8)
                    hover_y = box["y"] + box["height"] * random.uniform(0.2, 0.8)
                    await move_mouse_humanly(page, hover_x, hover_y)
                    await asyncio.sleep(random.uniform(1.0, 3.0))
            
            await asyncio.sleep(random.uniform(2.0, 5.0))
            log.info(f"    ✅ [{persona_name}] Drive browse session complete.")

    except Exception as e:
        log.error(f"    ❌ [{persona_name}] Drive warming failed: {e}")