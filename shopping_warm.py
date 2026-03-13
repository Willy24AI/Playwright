"""
shopping_warm.py
----------------
Generates Commercial Intent. Bypasses e-commerce anti-bot telemetry by 
physically typing searches, browsing image carousels, reading reviews, 
and simulating "Add to Cart" abandonment (Massive Commercial Value Signal).
"""

import asyncio
import logging
import random
from playwright.async_api import Page

from behavior_engine import (
    human_scroll, 
    click_humanly, 
    idle_reading, 
    smart_wait, 
    move_mouse_humanly,
    human_type,
    lognormal_delay
)
from llm_helper import generate_dynamic_search

log = logging.getLogger(__name__)

async def handle_consent_banners(page: Page):
    """Generic handler for cookie/consent banners on e-commerce sites."""
    try:
        selectors = [
            "button:has-text('Accept all')", "button:has-text('I agree')", 
            "input[name='accept']", "button#sp-cc-accept" # sp-cc-accept is Amazon
        ]
        for sel in selectors:
            btn = page.locator(sel).first
            if await btn.is_visible(timeout=1500):
                await click_humanly(page, btn, {})
                await asyncio.sleep(1)
                return
    except Exception:
        pass

async def organic_search(page: Page, target_url: str, query: str, behavior: dict, persona_name: str):
    """Navigates to the homepage and physically types the search to bypass URL-injection detection."""
    log.info(f"    🌐 [{persona_name}] Navigating to {target_url}...")
    await page.goto(target_url, wait_until="domcontentloaded")
    await handle_consent_banners(page)
    await smart_wait(page, timeout=8000)

    # Broad selectors to catch search bars on Google, Amazon, Walmart, Target, etc.
    search_selectors = "input[type='search'], input[name='q'], input[name='field-keywords'], input[placeholder*='Search' i]"
    search_box = page.locator(search_selectors).first
    
    if await search_box.is_visible(timeout=5000):
        log.info(f"    ⌨️ [{persona_name}] Typing product query: '{query}'")
        await human_type(page, search_selectors, query, behavior)
        await asyncio.sleep(lognormal_delay(300, 800))
        await page.keyboard.press("Enter")
        await smart_wait(page, timeout=10000)
    else:
        log.warning(f"    ⚠️ [{persona_name}] Could not locate search bar. Aborting search flow.")
        raise Exception("Search bar not found.")

async def interact_with_image_carousel(page: Page, behavior: dict, persona_name: str):
    """Simulates a user clicking through product thumbnail images."""
    try:
        # Look for common thumbnail image classes/roles
        thumbnails = await page.locator("li.imageThumbnail, img[alt*='thumbnail' i], button img").all()
        if thumbnails and len(thumbnails) > 1:
            log.info(f"    🖼️ [{persona_name}] Browsing product image carousel...")
            clicks = random.randint(1, min(4, len(thumbnails) - 1))
            for thumb in thumbnails[1:clicks+1]:
                if await thumb.is_visible():
                    await click_humanly(page, thumb, behavior)
                    await asyncio.sleep(lognormal_delay(1500, 3500))
    except Exception:
        pass

async def simulate_cart_abandonment(page: Page, behavior: dict, persona_name: str):
    """Massive Trust Signal: Adds an item to the cart, hovers over the cart, and leaves."""
    try:
        add_btn = page.locator("button:has-text('Add to Cart'), input[value='Add to Cart'], button:has-text('Add to bag') i").first
        if await add_btn.is_visible(timeout=3000):
            log.info(f"    🛒 [{persona_name}] High Commercial Intent: Adding item to cart...")
            await click_humanly(page, add_btn, behavior)
            await smart_wait(page, timeout=5000)
            
            # Hover over the cart icon to 'check' it
            cart_icon = page.locator("a[href*='cart'], a#nav-cart").first
            if await cart_icon.is_visible():
                box = await cart_icon.bounding_box()
                if box:
                    await move_mouse_humanly(page, box["x"] + box["width"]/2, box["y"] + box["height"]/2)
                    await asyncio.sleep(random.uniform(2.0, 5.0))
            log.info(f"    🏃‍♂️ [{persona_name}] Cart abandonment complete.")
    except Exception:
        pass

async def shopping_warm_session(page: Page, profile: dict):
    persona_name = profile.get("persona", {}).get("name", "UnknownBot")
    behavior = profile.get("behavior", {})
    
    log.info(f"🛍️ [{persona_name}] Starting Advanced E-Commerce browsing...")

    # 1. Decide on the query (LLM integration remains intact)
    query = await generate_dynamic_search(profile, platform="Shopping Query")
    
    # 2. Logic: 60% Amazon, 40% Google Shopping (Ensures high selector reliability)
    if random.random() < 0.60:
        base_url = "https://www.amazon.com"
        domain_name = "Amazon"
    else:
        base_url = "https://shopping.google.com"
        domain_name = "Google Shopping"

    try:
        # 3. Organic Search Navigation
        await organic_search(page, base_url, query, behavior, persona_name)
        
        # 4. Browse Listings with Weighted Randomness
        await idle_reading(page, {**behavior, "read_pause_range": (3, 7)})
        await human_scroll(page, behavior)
        
        # Heuristic: Look for product listing selectors
        listings = await page.locator("a h2, a h3, div[data-component-type='s-search-result'] a.a-link-normal").all()
        
        if listings:
            # Weighted choice: mostly pick top 3, sometimes go deeper
            weights = [0.4, 0.3, 0.15, 0.1, 0.05]
            n = min(len(listings), len(weights))
            target_product = random.choices(listings[:n], weights=weights[:n], k=1)[0]
            
            log.info(f"    🖱️ [{persona_name}] Found interesting listing on {domain_name}. Clicking...")
            await target_product.scroll_into_view_if_needed()
            await asyncio.sleep(lognormal_delay(800, 2000))
            await click_humanly(page, target_product, behavior)
            await smart_wait(page, timeout=10000)
            
            # 5. Deep Product Consideration Phase
            log.info(f"    👀 [{persona_name}] Analyzing product details...")
            
            # Look at pictures
            await interact_with_image_carousel(page, behavior, persona_name)

            # Read Description and Reviews
            scroll_sessions = random.randint(4, 8)
            for i in range(scroll_sessions):
                await human_scroll(page, behavior)
                
                # Pause longer if we scrolled deep (simulating reading reviews)
                if i > 2:
                    await idle_reading(page, {**behavior, "read_pause_range": (5, 12)})
                else:
                    await idle_reading(page, behavior)
                    
            # 6. MACRO-ENTROPY: 15% Chance to Abandon Cart
            if random.random() < 0.15:
                await simulate_cart_abandonment(page, behavior, persona_name)
                
            log.info(f"🏁 [{persona_name}] Shopping session complete.")
        else:
            log.warning(f"    ⚠️ [{persona_name}] No clear listings found on {domain_name}.")

    except Exception as e:
        log.warning(f"    ❌ [{persona_name}] Shopping flow interrupted on {domain_name}: {e}")