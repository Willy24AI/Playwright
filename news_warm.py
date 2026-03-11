"""
news_warm.py
------------
Simulates direct publisher loyalty. 
Uses the LLM to pick a niche-relevant news domain, navigates to the homepage, 
uses a Universal Heuristic to find a readable article, and reads it.
"""

import asyncio
import logging
import random
from playwright.async_api import Page

from behavior_engine import human_scroll, idle_reading, smart_wait, move_mouse_humanly
from llm_helper import generate_dynamic_search

log = logging.getLogger(__name__)

async def handle_generic_consent(page: Page):
    """Attempts to clear generic cookie banners on third-party sites."""
    try:
        selectors = [
            "button:has-text('Accept')", "button:has-text('I Agree')", 
            "button:has-text('Allow All')", "#onetrust-accept-btn-handler"
        ]
        for sel in selectors:
            btn = page.locator(sel).first
            if await btn.is_visible(timeout=1000):
                await btn.click()
                await asyncio.sleep(1.5)
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
    log.info(f"🧭 [{persona_name}] Navigating directly to: {target_url}")

    try:
        await page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
        await handle_generic_consent(page)
        await smart_wait(page, timeout=10000)
        
        # Idle on the homepage like a normal human checking the headlines
        await idle_reading(page, {**behavior, "read_pause_range": (3, 8)})
        await human_scroll(page, behavior) # Scroll down a bit to load lazy images

        log.info(f"🔍 [{persona_name}] Scanning {domain} for an interesting article...")
        
        # 2. THE UNIVERSAL ARTICLE HEURISTIC
        # We grab all links on the page and filter them to find actual articles
        links = await page.locator("a").element_handles()
        valid_articles = []
        
        for link in links:
            try:
                href = await link.get_attribute("href") or ""
                text = await link.inner_text() or ""
                
                # Heuristic Rules:
                # 1. Text must be decently long (headlines are usually > 30 chars).
                # 2. Href must be decently long (article slugs are longer than just '/about').
                # 3. Must not be a functional button like 'login' or 'subscribe'.
                bad_words = ['login', 'cart', 'subscribe', 'account', 'newsletter']
                
                if len(text.strip()) > 30 and len(href) > 25 and not any(w in href.lower() for w in bad_words):
                    valid_articles.append(link)
            except Exception:
                continue

        if valid_articles:
            target_article = random.choice(valid_articles[:10]) # Pick from the top 10 articles found
            article_title = (await target_article.inner_text()).strip().replace('\n', ' ')[:40]
            
            log.info(f"🖱️ [{persona_name}] Found article: '{article_title}...'")
            
            # Move mouse to it and click
            box = await target_article.bounding_box()
            if box:
                await move_mouse_humanly(page, box["x"] + box["width"]/2, box["y"] + box["height"]/2)
                await asyncio.sleep(random.uniform(0.5, 1.5))
            
            await target_article.click(force=True)
            await page.wait_for_load_state("domcontentloaded")
            log.info(f"✅ [{persona_name}] Article loaded. Reading now...")

            # 3. Read the article deeply
            scroll_sessions = random.randint(*behavior["scroll_sessions"])
            for _ in range(scroll_sessions):
                await human_scroll(page, behavior)
                await idle_reading(page, behavior)

            log.info(f"✅ [{persona_name}] Finished reading publisher site.")
            
        else:
            log.warning(f"⚠️ [{persona_name}] Could not identify any clear articles on {domain}.")

    except Exception as e:
        log.warning(f"❌ [{persona_name}] Failed or blocked while browsing {domain}: {e}")