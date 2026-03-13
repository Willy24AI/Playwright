"""
news_warm.py
------------
Simulates direct publisher loyalty. 
Upgraded with a high-speed Headline Selector Matrix, Fitts's Law clicking, 
Popup/Paywall resilience, and "Rabbit Hole" macro-entropy.
"""

import asyncio
import logging
import random
from playwright.async_api import Page

from behavior_engine import (
    human_scroll, 
    idle_reading, 
    smart_wait, 
    click_humanly,
    lognormal_delay
)
from llm_helper import generate_dynamic_search

log = logging.getLogger(__name__)

async def handle_publisher_popups(page: Page, behavior: dict):
    """Attempts to clear cookie banners and annoying 'Subscribe to our Newsletter' popups."""
    try:
        selectors = [
            "button:has-text('Accept' i)", "button:has-text('I Agree' i)", 
            "button:has-text('Allow All' i)", "#onetrust-accept-btn-handler",
            "button[aria-label='Close' i]", "button.close", ".modal-close",
            "button:has-text('No thanks' i)", "button:has-text('Maybe later' i)"
        ]
        for sel in selectors:
            btn = page.locator(sel).first
            if await btn.is_visible(timeout=1000):
                await click_humanly(page, btn, behavior)
                await asyncio.sleep(lognormal_delay(1000, 2500))
                return
    except Exception:
        pass

async def news_warm_session(page: Page, profile: dict):
    persona_name = profile.get("persona", {}).get("name", "UnknownBot")
    behavior = profile.get("behavior", {})
    
    log.info(f"📰 [{persona_name}] Starting Direct Publisher session...")

    # 1. Ask the AI for a specific, interest-based news domain
    raw_domain = await generate_dynamic_search(profile, platform="Direct News Domain")
    domain = raw_domain.strip().lower().replace("https://", "").replace("www.", "").split("/")[0]
    
    target_url = f"https://www.{domain}"
    log.info(f"    🧭 [{persona_name}] Navigating directly to: {target_url}")

    try:
        await page.goto(target_url, wait_until="domcontentloaded", timeout=45000)
        await handle_publisher_popups(page, behavior)
        await smart_wait(page, timeout=10000)
        
        # Idle on the homepage like a normal human checking the headlines
        log.info(f"    👀 [{persona_name}] Scanning homepage headlines...")
        await idle_reading(page, {**behavior, "read_pause_range": (3, 8)})
        await human_scroll(page, behavior)

        # 2. HIGH-SPEED HEADLINE SELECTOR MATRIX
        # Instead of grabbing all <a> tags, we only grab links inside heading tags.
        # This reduces the nodes to check from ~300 down to ~20, drastically speeding up the script.
        headline_selectors = "h1 a, h2 a, h3 a, a:has(h2), a:has(h3), article a.headline, a[class*='title' i]"
        links = await page.locator(headline_selectors).all()
        valid_articles = []
        
        for link in links:
            try:
                if not await link.is_visible():
                    continue
                    
                href = await link.get_attribute("href") or ""
                text = await link.inner_text() or ""
                
                # Heuristics: Long text, long href, no functional buttons
                bad_words = ['login', 'cart', 'subscribe', 'account', 'newsletter', 'author', 'category']
                if len(text.strip()) > 25 and len(href) > 20 and not any(w in href.lower() for w in bad_words):
                    valid_articles.append(link)
            except Exception:
                continue

        if valid_articles:
            # Pick from the top 6 most prominent articles
            n = min(len(valid_articles), 6)
            target_article = random.choice(valid_articles[:n])
            
            try:
                article_title = (await target_article.inner_text()).strip().replace('\n', ' ')[:40]
                log.info(f"    🖱️ [{persona_name}] Found article: '{article_title}...'")
            except Exception:
                log.info(f"    🖱️ [{persona_name}] Found an article. Clicking...")

            # Scroll into view and click using Fitts's Law
            await target_article.scroll_into_view_if_needed()
            await asyncio.sleep(random.uniform(1.0, 2.5))
            await click_humanly(page, target_article, behavior)
            
            await smart_wait(page)
            await handle_publisher_popups(page, behavior) # Popups often fire on article load
            log.info(f"    ✅ [{persona_name}] Article loaded. Reading deeply...")

            # 3. Read the article deeply
            scroll_sessions = random.randint(*behavior.get("scroll_sessions", [4, 8]))
            for _ in range(scroll_sessions):
                await human_scroll(page, behavior)
                await idle_reading(page, behavior)
                
                # 10% chance per scroll block to encounter an un-closable paywall and bounce
                if random.random() < 0.10:
                    paywall_indicators = page.locator("text='Subscribe to continue reading', text='You have reached your article limit' i").first
                    if await paywall_indicators.is_visible(timeout=1000):
                        log.info(f"    🧱 [{persona_name}] Hit a hard paywall. Bouncing back to homepage...")
                        await page.go_back()
                        await asyncio.sleep(random.uniform(2.0, 5.0))
                        break # End the reading loop early

            # 4. MACRO-ENTROPY: THE RABBIT HOLE (25% Chance)
            # Humans often click a "Related Article" at the bottom of the page
            if random.random() < 0.25:
                log.info(f"    🕳️ [{persona_name}] Down the rabbit hole: Looking for a related article...")
                related_links = await page.locator("aside a, .related-articles a, .read-next a").all()
                if related_links:
                    next_article = random.choice(related_links[:3])
                    if await next_article.is_visible():
                        await click_humanly(page, next_article, behavior)
                        await smart_wait(page)
                        log.info(f"    📖 [{persona_name}] Skimming related article...")
                        await human_scroll(page, behavior)
                        await idle_reading(page, behavior)

            log.info(f"    🏁 [{persona_name}] Finished reading publisher site.")
            
        else:
            log.warning(f"    ⚠️ [{persona_name}] Could not identify any clear articles on {domain}.")

    except Exception as e:
        log.warning(f"    ❌ [{persona_name}] Failed or blocked while browsing {domain}: {e}")