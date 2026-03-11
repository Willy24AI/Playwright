"""
maps_warm.py
------------
Simulates Local Guide behavior.
[UPGRADE]: Dynamically detects the proxy's physical IP location and uses the LLM 
to generate hyper-local searches for that exact city, preventing IP mismatches.
"""

import asyncio
import logging
import random
import urllib.parse
from playwright.async_api import Page

from behavior_engine import human_scroll, move_mouse_humanly, smart_wait, lognormal_delay
from llm_helper import generate_dynamic_search

log = logging.getLogger(__name__)

async def get_proxy_location(page: Page, fallback_city: str) -> str:
    """Silently pings an IP API through the Multilogin proxy to get the real physical city."""
    try:
        # We use page.context.request to route the API call through the active proxy
        response = await page.context.request.get("http://ip-api.com/json/", timeout=5000)
        data = await response.json()
        city = data.get("city")
        region = data.get("regionName")
        if city and region:
            log.info(f"📍 Proxy IP Geo-Located to: {city}, {region}")
            return f"{city}, {region}"
    except Exception as e:
        log.warning(f"⚠️ Could not verify proxy IP location. Using database city: {fallback_city}")
    
    return fallback_city

async def handle_maps_consent(page: Page):
    """Clears the 'Agree to cookies' popup on Google Maps."""
    try:
        btn = page.locator("button:has-text('Accept all'), button:has-text('I agree')").first
        if await btn.is_visible(timeout=3000):
            await btn.click()
            await asyncio.sleep(2)
    except Exception:
        pass

async def maps_warm_session(page: Page, profile: dict):
    persona_name = profile.get("persona", {}).get("name", "UnknownBot")
    db_city = profile.get("persona", {}).get("city", "New York")
    
    log.info(f"🗺️ [{persona_name}] Starting Google Maps Local session...")

    # 1. Detect the actual physical location of the proxy
    real_city = await get_proxy_location(page, fallback_city=db_city)

    # 2. Ask the AI for a hyper-local search query based on the REAL proxy city
    # We temporarily override the profile's city just for this LLM prompt
    temp_profile = profile.copy()
    temp_profile["persona"]["city"] = real_city
    
    raw_query = await generate_dynamic_search(temp_profile, platform=f"Google Maps in {real_city}")
    safe_query = urllib.parse.quote_plus(raw_query)

    # 3. Inject directly via URL
    target_url = f"https://www.google.com/maps/search/{safe_query}"
    log.info(f"🧭 [{persona_name}] Navigating to Maps: '{raw_query}'")
    
    await page.goto(target_url, wait_until="domcontentloaded")
    await handle_maps_consent(page)
    await smart_wait(page, timeout=10000)

    # 4. Simulate map panning (clicking and dragging)
    await move_mouse_humanly(page, random.randint(300, 800), random.randint(200, 600))
    await asyncio.sleep(random.uniform(2.0, 4.0))

    # 5. Click a business from the left-hand sidebar
    log.info(f"🖱️ [{persona_name}] Browsing local business results...")
    listings = await page.locator("a[href*='/maps/place/']").all()
    
    if listings:
        target_listing = random.choice(listings[:5])
        try:
            await target_listing.click(force=True)
            log.info(f"✅ [{persona_name}] Clicked a local business listing.")
            await asyncio.sleep(random.uniform(3.0, 5.0))
            
            # 6. Scroll through the business details
            scrollable_sidebar = page.locator("div[role='main']").last
            box = await scrollable_sidebar.bounding_box()
            if box:
                await move_mouse_humanly(page, box["x"] + box["width"]/2, box["y"] + box["height"]/2)
            
            log.info(f"👀 [{persona_name}] Reading reviews and checking photos...")
            for _ in range(random.randint(3, 6)):
                await page.mouse.wheel(0, random.uniform(200, 600))
                await asyncio.sleep(lognormal_delay(2000, 5000))
                
            # Random chance to "Save" the place
            if random.random() < 0.15:
                try:
                    save_btn = page.locator("button[aria-label*='Save']").first
                    if await save_btn.is_visible(timeout=2000):
                        await save_btn.click()
                        log.info(f"📌 [{persona_name}] Saved business to lists.")
                        await asyncio.sleep(2)
                except Exception: pass

        except Exception as e:
            log.warning(f"⚠️ [{persona_name}] Could not click listing.")
    else:
        log.warning(f"⚠️ [{persona_name}] No local listings found for this query.")

    log.info(f"✅ [{persona_name}] Google Maps session complete.")