"""
maps_warm.py
------------
Simulates Local Guide behavior.
Dynamically detects the proxy's physical IP location and uses the LLM 
to generate hyper-local searches, types them organically, pans the map,
and occasionally requests directions.
"""

import asyncio
import logging
import random
import urllib.parse
from playwright.async_api import Page

from behavior_engine import (
    human_scroll, 
    move_mouse_humanly, 
    smart_wait, 
    lognormal_delay,
    human_type,
    click_humanly
)
from llm_helper import generate_dynamic_search

log = logging.getLogger(__name__)

async def get_proxy_location(page: Page, fallback_city: str) -> str:
    """Silently pings an IP API through the active proxy to get the real physical city."""
    try:
        response = await page.context.request.get("http://ip-api.com/json/", timeout=5000)
        data = await response.json()
        city = data.get("city")
        region = data.get("regionName")
        if city and region:
            log.info(f"    📍 Proxy IP Geo-Located to: {city}, {region}")
            return f"{city}, {region}"
    except Exception:
        log.warning(f"    ⚠️ Could not verify proxy IP location. Using database city: {fallback_city}")
    return fallback_city

async def handle_maps_consent(page: Page):
    try:
        btn = page.locator("button:has-text('Accept all'), button:has-text('I agree')").first
        if await btn.is_visible(timeout=3000):
            await btn.click()
            await asyncio.sleep(2)
    except Exception:
        pass

async def simulate_map_panning(page: Page):
    """Physically clicks and drags the map canvas to simulate a human looking around."""
    log.info("    🗺️ Panning the map canvas...")
    try:
        # Start in the middle-ish of the screen
        start_x = random.randint(400, 800)
        start_y = random.randint(300, 600)
        await move_mouse_humanly(page, start_x, start_y)
        
        # Click and hold
        await page.mouse.down()
        await asyncio.sleep(random.uniform(0.1, 0.3))
        
        # Drag to a new location
        end_x = start_x + random.randint(-300, 300)
        end_y = start_y + random.randint(-200, 200)
        await move_mouse_humanly(page, end_x, end_y, speed_factor=0.6) # Slower movement while dragging
        
        # Release
        await asyncio.sleep(random.uniform(0.1, 0.4))
        await page.mouse.up()
        await smart_wait(page, timeout=5000)
    except Exception as e:
        log.debug(f"Map panning failed: {e}")

async def maps_warm_session(page: Page, profile: dict):
    persona_name = profile.get("persona", {}).get("name", "UnknownBot")
    db_city = profile.get("persona", {}).get("city", "New York")
    behavior = profile.get("behavior", {})
    
    log.info(f"🧭 [{persona_name}] Starting Google Maps Local session...")

    # 1. Detect physical location
    real_city = await get_proxy_location(page, fallback_city=db_city)

    # 2. Get LLM Query
    temp_profile = profile.copy()
    temp_profile["persona"]["city"] = real_city
    raw_query = await generate_dynamic_search(temp_profile, platform=f"Google Maps in {real_city}")

    # 3. ORGANIC NAVIGATION (No URL Injection)
    log.info(f"    🌐 [{persona_name}] Loading Google Maps homepage...")
    await page.goto("https://www.google.com/maps", wait_until="domcontentloaded")
    await handle_maps_consent(page)
    await smart_wait(page)

    # Type the search physically
    log.info(f"    ⌨️ [{persona_name}] Typing search: '{raw_query}'")
    search_box = "input#searchboxinput"
    await human_type(page, search_box, raw_query, behavior)
    await asyncio.sleep(lognormal_delay(300, 800))
    await page.keyboard.press("Enter")
    await smart_wait(page, timeout=10000)

    # 4. Map Panning (The Human Spatial Signal)
    await simulate_map_panning(page)

    # 5. Interact with local business results
    log.info(f"    🖱️ [{persona_name}] Browsing local business results...")
    listings = await page.locator("a[href*='/maps/place/']").all()
    
    if listings:
        target_listing = random.choice(listings[:5])
        try:
            # Replaced force=True with Fitts's Law click
            await click_humanly(page, target_listing, behavior)
            log.info(f"    ✅ [{persona_name}] Clicked a local business listing.")
            await smart_wait(page, timeout=8000)
            
            # 6. Scroll through the business details (Photos, Reviews)
            scrollable_sidebar = page.locator("div[role='main']").last
            box = await scrollable_sidebar.bounding_box()
            if box:
                # Hover randomly within the sidebar, not the geometric center
                hover_x = box["x"] + box["width"] * random.uniform(0.2, 0.8)
                hover_y = box["y"] + box["height"] * random.uniform(0.2, 0.8)
                await move_mouse_humanly(page, hover_x, hover_y)
            
            log.info(f"    👀 [{persona_name}] Reading reviews and checking photos...")
            for _ in range(random.randint(3, 6)):
                await human_scroll(page, behavior)
                await asyncio.sleep(lognormal_delay(2000, 5000))
                
            # 7. MACRO-ENTROPY: 20% Chance to Request Directions
            if random.random() < 0.20:
                dir_btn = page.locator("button[data-value='Directions']").first
                if await dir_btn.is_visible(timeout=2000):
                    await click_humanly(page, dir_btn, behavior)
                    log.info(f"    🚗 [{persona_name}] Requested directions to the location.")
                    await smart_wait(page, timeout=5000)
                    # Ponder the route for a few seconds before leaving
                    await asyncio.sleep(random.uniform(5.0, 12.0))
                    
            # 8. MACRO-ENTROPY: 10% Chance to Save the Place
            elif random.random() < 0.10:
                save_btn = page.locator("button[data-value='Save']").first
                if await save_btn.is_visible(timeout=2000):
                    await click_humanly(page, save_btn, behavior)
                    log.info(f"    📌 [{persona_name}] Saved business to lists.")
                    await asyncio.sleep(random.uniform(2.0, 4.0))

        except Exception as e:
            log.warning(f"    ⚠️ [{persona_name}] Could not interact with listing: {e}")
    else:
        log.warning(f"    ⚠️ [{persona_name}] No local listings found for this query.")

    log.info(f"🏁 [{persona_name}] Google Maps session complete.")