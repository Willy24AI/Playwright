"""
shopping_warm.py
----------------
Generates Commercial Intent. Uses LLM to decide WHERE to shop (Amazon, BestBuy, etc.) 
and WHAT to search for, then simulates a browsing/review-reading session.
"""

import asyncio
import logging
import random
import urllib.parse
from playwright.async_api import Page

from behavior_engine import human_scroll, click_humanly, idle_reading, smart_wait, move_mouse_humanly
from llm_helper import generate_dynamic_search

log = logging.getLogger(__name__)

async def shopping_warm_session(page: Page, profile: dict):
    persona_name = profile.get("persona", {}).get("name", "UnknownBot")
    behavior = profile.get("behavior", {})
    
    log.info(f"🛒 [{persona_name}] Starting dynamic shopping discovery...")

    # 1. Decide on the Destination and the Query
    domain = await generate_dynamic_search(profile, platform="Shopping Target")
    query = await generate_dynamic_search(profile, platform="Shopping Query")
    
    # 2. Logic: Should we use Google Shopping or go Direct?
    # 50/50 split ensures we build both internal Google data and external cookie data
    if random.random() < 0.5:
        target_url = f"https://www.google.com/search?tbm=shop&q={urllib.parse.quote_plus(query)}"
        log.info(f"🧭 [{persona_name}] Using Google Shopping for: '{query}'")
    else:
        target_url = f"https://www.{domain}/s?k={urllib.parse.quote_plus(query)}" if "amazon" in domain else f"https://www.{domain}/search?q={urllib.parse.quote_plus(query)}"
        log.info(f"🧭 [{persona_name}] Going Direct to {domain} for: '{query}'")

    try:
        await page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
        await smart_wait(page)
        
        # 3. Browse Listings
        await idle_reading(page, {**behavior, "read_pause_range": (3, 7)})
        await human_scroll(page, behavior)
        
        # Heuristic: Look for common product listing selectors (Links with long text or images)
        listings = await page.locator("a h2, a h3, div[data-component-type='s-search-result'] a").all()
        
        if listings:
            # Pick a random product from top results
            target_product = random.choice(listings[:5])
            log.info(f"🖱️ [{persona_name}] Found interesting listing. Clicking...")
            
            await target_product.scroll_into_view_if_needed()
            await click_humanly(page, target_product, behavior)
            await page.wait_for_load_state("domcontentloaded")
            
            # 4. Deep Review Session
            log.info(f"👀 [{persona_name}] Reading reviews and checking prices...")
            scroll_sessions = random.randint(4, 8)
            for _ in range(scroll_sessions):
                await human_scroll(page, behavior)
                # Randomly wiggle mouse over product images or "Add to Cart" buttons without clicking
                if random.random() < 0.3:
                    await move_mouse_humanly(page, random.randint(200, 800), random.randint(200, 800))
                await idle_reading(page, behavior)
                
            log.info(f"✅ [{persona_name}] Shopping session complete.")
        else:
            log.warning(f"⚠️ [{persona_name}] No clear listings found on {domain}.")

    except Exception as e:
        log.warning(f"❌ [{persona_name}] Shopping flow interrupted on {domain}: {e}")