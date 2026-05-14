"""
shopping_warm.py
----------------
Generates Commercial Intent. Bypasses e-commerce anti-bot telemetry by 
physically typing searches, browsing image carousels, reading reviews, 
and simulating "Add to Cart" abandonment (Massive Commercial Value Signal).

[v2 PATCH - resilient site selection]:
- Replaced hardcoded "60% Amazon, 40% Google Shopping" with a SAFE_SHOPPING_SITES pool
  that prefers sites that actually work through proxies (Etsy, eBay, Walmart, Target).
- Tries up to 3 different shopping sites if the first ones fail with proxy errors.
- Drops Google Shopping entirely (Google ASN-blocked).
- Still uses LLM-suggested domain when available, but with validation.
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


# ---------------------------------------------------------------------------
# SAFE SHOPPING SITES POOL
# Curated list of e-commerce sites that historically accept proxy traffic.
# Each entry: (homepage_url, display_name, search_box_selectors)
# ---------------------------------------------------------------------------
SAFE_SHOPPING_SITES = [
    ("https://www.etsy.com",     "Etsy"),
    ("https://www.ebay.com",     "eBay"),
    ("https://www.walmart.com",  "Walmart"),
    ("https://www.target.com",   "Target"),
    ("https://www.wayfair.com",  "Wayfair"),
    ("https://www.newegg.com",   "Newegg"),
    ("https://www.overstock.com", "Overstock"),
    ("https://www.thriftbooks.com", "ThriftBooks"),
    # Amazon kept but lower weight - works for some proxies, fails for others
    ("https://www.amazon.com",   "Amazon"),
]

# Errors that indicate "this site rejects our proxy" - try a different site
PROXY_BLOCK_ERRORS = (
    "ERR_INVALID_AUTH_CREDENTIALS",
    "ERR_HTTP_RESPONSE_CODE_FAILURE",
    "ERR_TUNNEL_CONNECTION_FAILED",
    "ERR_CONNECTION_RESET",
    "ERR_CONNECTION_REFUSED",
    "ERR_EMPTY_RESPONSE",
    "ERR_TIMED_OUT",
)


def _is_proxy_block(error_msg: str) -> bool:
    return any(sig in error_msg for sig in PROXY_BLOCK_ERRORS)


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

    # Broad selectors to catch search bars on Etsy, eBay, Amazon, Walmart, Target, etc.
    search_selectors = "input[type='search'], input[name='q'], input[name='field-keywords'], input[placeholder*='Search' i], input[aria-label*='Search' i]"
    search_box = page.locator(search_selectors).first
    
    if await search_box.is_visible(timeout=5000):
        log.info(f"    ⌨️ [{persona_name}] Typing product query: '{query}'")
        await human_type(page, search_selectors, query, behavior)
        await asyncio.sleep(lognormal_delay(300, 800))
        await page.keyboard.press("Enter")
        await smart_wait(page, timeout=10000)
    else:
        log.warning(f"    ⚠️ [{persona_name}] Could not locate search bar on {target_url}.")
        raise Exception("Search bar not found.")


async def interact_with_image_carousel(page: Page, behavior: dict, persona_name: str):
    """Simulates a user clicking through product thumbnail images."""
    try:
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
        add_btn = page.locator("button:has-text('Add to Cart'), input[value='Add to Cart'], button:has-text('Add to bag' i)").first
        if await add_btn.is_visible(timeout=3000):
            log.info(f"    🛒 [{persona_name}] High Commercial Intent: Adding item to cart...")
            await click_humanly(page, add_btn, behavior)
            await smart_wait(page, timeout=5000)
            
            cart_icon = page.locator("a[href*='cart'], a#nav-cart").first
            if await cart_icon.is_visible():
                box = await cart_icon.bounding_box()
                if box:
                    await move_mouse_humanly(page, box["x"] + box["width"]/2, box["y"] + box["height"]/2)
                    await asyncio.sleep(random.uniform(2.0, 5.0))
            log.info(f"    🏃‍♂️ [{persona_name}] Cart abandonment complete.")
    except Exception:
        pass


async def _try_shopping_site(page: Page, base_url: str, domain_name: str, query: str,
                              behavior: dict, persona_name: str) -> bool:
    """
    Try to perform a shopping flow on a single site.
    Returns True if the search succeeded (we have a results page to browse),
    False if the site failed at navigation/search level (proxy block, etc.).
    Raises on unexpected errors.
    """
    try:
        await organic_search(page, base_url, query, behavior, persona_name)
        return True
    except Exception as e:
        err = str(e)
        if _is_proxy_block(err):
            log.info(f"    ⏭️ [{persona_name}] {domain_name} blocked through proxy, trying next site...")
            return False
        if "Search bar not found" in err:
            log.info(f"    ⏭️ [{persona_name}] {domain_name} loaded but search bar missing, trying next site...")
            return False
        # Any other error - let caller handle
        raise


async def shopping_warm_session(page: Page, profile: dict):
    persona_name = profile.get("persona", {}).get("name", "UnknownBot")
    behavior = profile.get("behavior", {})
    
    log.info(f"🛍️ [{persona_name}] Starting Advanced E-Commerce browsing...")

    # 1. Decide on the query
    query = await generate_dynamic_search(profile, platform="Shopping Query")
    
    # 2. Build candidate site list - shuffled, up to 3 attempts
    candidates = list(SAFE_SHOPPING_SITES)
    random.shuffle(candidates)
    candidates = candidates[:3]  # Try max 3 sites before giving up
    
    # 3. Try each candidate until one works
    chosen_site = None
    chosen_domain = None
    
    for base_url, domain_name in candidates:
        success = await _try_shopping_site(page, base_url, domain_name, query, behavior, persona_name)
        if success:
            chosen_site = base_url
            chosen_domain = domain_name
            log.info(f"    ✅ [{persona_name}] Successfully searching on {domain_name}.")
            break
    
    if not chosen_site:
        log.warning(f"    ⚠️ [{persona_name}] All {len(candidates)} shopping sites blocked. Abandoning shopping task.")
        return
    
    # 4. Browse Listings on the successful site
    try:
        await idle_reading(page, {**behavior, "read_pause_range": (3, 7)})
        await human_scroll(page, behavior)
        
        # Heuristic: Look for product listing selectors (covers Amazon, eBay, Etsy, Walmart, etc.)
        listings = await page.locator(
            "a h2, a h3, "
            "div[data-component-type='s-search-result'] a.a-link-normal, "
            "a.s-item__link, "  # eBay
            "a.gh-cardLink, "   # Etsy variations
            "a[data-test-id*='product' i], "  # Target variations
            "li[data-item-id] a"  # generic
        ).all()
        
        if not listings:
            log.warning(f"    ⚠️ [{persona_name}] No clear listings found on {chosen_domain}.")
            return
        
        # Weighted choice: mostly top 3, sometimes deeper
        weights = [0.4, 0.3, 0.15, 0.1, 0.05]
        n = min(len(listings), len(weights))
        target_product = random.choices(listings[:n], weights=weights[:n], k=1)[0]
        
        log.info(f"    🖱️ [{persona_name}] Found interesting listing on {chosen_domain}. Clicking...")
        await target_product.scroll_into_view_if_needed()
        await asyncio.sleep(lognormal_delay(800, 2000))
        await click_humanly(page, target_product, behavior)
        await smart_wait(page, timeout=10000)
        
        # 5. Deep Product Consideration Phase
        log.info(f"    👀 [{persona_name}] Analyzing product details...")
        await interact_with_image_carousel(page, behavior, persona_name)

        # Read Description and Reviews
        scroll_sessions = random.randint(4, 8)
        for i in range(scroll_sessions):
            await human_scroll(page, behavior)
            if i > 2:
                await idle_reading(page, {**behavior, "read_pause_range": (5, 12)})
            else:
                await idle_reading(page, behavior)
                
        # 6. MACRO-ENTROPY: 15% Chance to Abandon Cart
        if random.random() < 0.15:
            await simulate_cart_abandonment(page, behavior, persona_name)
            
        log.info(f"🏁 [{persona_name}] Shopping session complete on {chosen_domain}.")
        
    except Exception as e:
        log.warning(f"    ❌ [{persona_name}] Shopping flow interrupted on {chosen_domain}: {str(e)[:120]}")