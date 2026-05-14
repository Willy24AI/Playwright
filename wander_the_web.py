"""
wander_the_web.py
-----------------
Builds elite third-party cookie profiles by wandering the web.
[UPGRADED]: Introduces 'Mode C: External Referrer Strike' to generate 
massive off-platform algorithmic authority for YouTube videos.

[v2 PATCH - proxy-resilient wandering]:
- Mode A: 75% of time picks from TIER_1_SEARCH_ENGINES (proven to accept proxies),
  25% from full SEARCH_DIRECTORIES list (variety preserved).
- Mode B: prioritizes proven sites in SAFE_HIGH_TRUST_SITES (drops BBC/CNN/Reddit/BestBuy
  which consistently fail through proxies).
- Both modes now retry up to 3 times on proxy errors before giving up.
"""

import os
import asyncio
import logging
import random
import urllib.parse
from pathlib import Path
from playwright.async_api import Page

from behavior_engine import (
    human_scroll, 
    click_humanly, 
    idle_reading, 
    smart_wait, 
    lognormal_delay
)
from llm_helper import generate_dynamic_search

log = logging.getLogger(__name__)


# ==========================================
# 🔗 EXTERNAL REFERRER LINKS (YOUTUBE STRIKE)
# ==========================================
EXTERNAL_REFERRER_LINKS = [
    # "https://www.reddit.com/r/YourSubreddit/comments/xyz/your_post/",
]

def load_referrers():
    """Loads external referrers from referrers.txt if it exists."""
    referrers = list(EXTERNAL_REFERRER_LINKS)
    try:
        ref_file = Path(__file__).parent / "referrers.txt"
        if ref_file.exists():
            with open(ref_file, "r") as f:
                file_links = [line.strip() for line in f if line.strip() and not line.startswith("#")]
                referrers.extend(file_links)
    except Exception as e:
        log.warning(f"Could not load referrers.txt: {e}")
    return referrers


# ==========================================
# 🔍 TIER 1 SEARCH ENGINES - PROVEN TO WORK THROUGH PROXIES
# ==========================================
# These are the major search engines that have flexible TLS/proxy policies.
# Used 75% of the time in Mode A. The full SEARCH_DIRECTORIES list is used 25% for variety.
TIER_1_SEARCH_ENGINES = [
    "https://duckduckgo.com/?q=",
    "https://www.bing.com/search?q=",
    "https://search.yahoo.com/search?p=",
    "https://www.ecosia.org/search?q=",
    "https://search.brave.com/search?q=",
    "https://www.startpage.com/search?q=",
    "https://www.mojeek.com/search?q=",
    "https://www.qwant.com/?q=",
    "https://www.swisscows.com/en/web?query=",
    "https://en.wikipedia.org/w/index.php?search=",  # Wikipedia search works as a "search engine" experience
]


# ==========================================
# 🌐 MASSIVE SEARCH DIRECTORIES LIST (variety pool, 25% chance)
# ==========================================
SEARCH_DIRECTORIES = [
    # ---- Major Search Engines ----
    "https://duckduckgo.com/?q=",
    "https://www.bing.com/search?q=",
    "https://search.yahoo.com/search?p=",
    "https://www.ecosia.org/search?q=",
    "https://www.ask.com/web?q=",
    "https://search.brave.com/search?q=",
    "https://www.startpage.com/search?q=",
    "https://www.mojeek.com/search?q=",
    "https://www.yandex.com/search/?text=",
    "https://www.baidu.com/s?wd=",
    "https://www.swisscows.com/en/web?query=",
    # ---- E-Commerce & Retail ----
    "https://www.ebay.com/sch/i.html?_nkw=",
    "https://www.target.com/s?searchTerm=",
    "https://www.walmart.com/search?q=",
    "https://www.etsy.com/search?q=",
    "https://www.wayfair.com/keyword.php?keyword=",
    "https://www.newegg.com/p/pl?d=",
    "https://www.rei.com/search?q=",
    # ---- Reference & Education ----
    "https://en.wikipedia.org/w/index.php?search=",
    "https://www.britannica.com/search?query=",
    "https://www.dictionary.com/browse/",
    "https://www.merriam-webster.com/dictionary/",
    "https://www.ted.com/search?q=",
    "https://archive.org/search?query=",
    # ---- Food & Recipes ----
    "https://www.allrecipes.com/search?q=",
    "https://www.epicurious.com/search/",
    "https://www.yelp.com/search?find_desc=",
    # ---- Travel ----
    "https://www.tripadvisor.com/Search?q=",
    "https://www.atlasobscura.com/search?q=",
    # ---- Finance & Business ----
    "https://finance.yahoo.com/quote/",
    "https://www.investopedia.com/search#q=",
    "https://www.marketwatch.com/search?q=",
    # ---- Technology & Programming ----
    "https://stackoverflow.com/search?q=",
    "https://github.com/search?q=",
    "https://www.geeksforgeeks.org/search/?query=",
    "https://developer.mozilla.org/en-US/search?q=",
    # ---- News & Journalism ----
    "https://apnews.com/search?q=",
    "https://www.theguardian.com/search?q=",
    "https://www.politico.com/search?q=",
    "https://www.axios.com/search?q=",
    "https://www.vox.com/search?q=",
    "https://www.propublica.org/search/#q=",
    "https://www.aljazeera.com/search?q=",
    "https://news.google.com/search?q=",
    # ---- Entertainment & Media ----
    "https://www.imdb.com/find/?q=",
    "https://www.rottentomatoes.com/search/?search=",
    "https://letterboxd.com/search/",
    # ---- Books & Literature ----
    "https://www.goodreads.com/search?q=",
    "https://openlibrary.org/search?q=",
    # ---- Science & Nature ----
    "https://www.sciencedaily.com/search/?keyword=",
    "https://www.scientificamerican.com/search/?q=",
    # ---- Sports ----
    "https://www.espn.com/search/_/q/",
    "https://sports.yahoo.com/search?p=",
    # ---- Jobs ----
    "https://www.linkedin.com/jobs/search/?keywords=",
    "https://www.indeed.com/jobs?q=",
    # ---- Maps & Local ----
    "https://www.yelp.com/search?find_desc=",
    "https://foursquare.com/explore?q=",
    # ---- Events ----
    "https://www.eventbrite.com/d/",
    "https://www.meetup.com/find/?keywords=",
    # ---- Podcasts ----
    "https://podcasts.apple.com/us/search?term=",
    "https://www.listennotes.com/search/?q=",
    # ---- Video & Streaming ----
    "https://vimeo.com/search?q=",
    # ---- Gaming ----
    "https://store.steampowered.com/search/?term=",
    "https://www.ign.com/search?q=",
    "https://www.polygon.com/search?q=",
    # ---- AI ----
    "https://huggingface.co/models?search=",
    "https://arxiv.org/search/?searchtype=all&query=",
]


# ==========================================
# 🏢 SAFE HIGH-TRUST SITES (Mode B target pool)
# ==========================================
# Curated to remove sites that consistently fail through proxies
# (BBC, CNN, Reddit, BestBuy) and prioritize the ones that work.
SAFE_HIGH_TRUST_SITES = [
    # Tech & Programming (high success rate)
    "https://github.com/explore",
    "https://stackoverflow.com/questions",
    "https://techcrunch.com/",
    "https://www.theverge.com/",
    "https://arstechnica.com/",
    "https://www.engadget.com/",
    "https://news.ycombinator.com/",
    
    # Reference & Education (very high success rate)
    "https://en.wikipedia.org/wiki/Special:Random",
    "https://www.britannica.com/",
    "https://archive.org/",
    "https://www.ted.com/talks",
    
    # News (mid-tier, less aggressive WAF than CNN/BBC)
    "https://www.npr.org/sections/news/",
    "https://www.theatlantic.com/",
    "https://www.politico.com/",
    "https://www.axios.com/",
    "https://www.vox.com/",
    "https://www.huffpost.com/",
    "https://www.propublica.org/",
    "https://www.aljazeera.com/",
    
    # Lifestyle & Reference
    "https://www.imdb.com/chart/top/",
    "https://www.goodreads.com/list/show/1.Best_Books_Ever",
    "https://www.atlasobscura.com/",
    "https://www.smithsonianmag.com/",
    "https://www.nationalgeographic.com/",
    
    # Finance (Bloomberg works reliably)
    "https://www.bloomberg.com/markets",
    "https://www.forbes.com/business/",
    "https://finance.yahoo.com/",
    
    # Shopping (working ones only)
    "https://www.etsy.com/c/home-and-living",
    "https://www.ebay.com/b/Daily-Deals/bn_7114033402",
    "https://www.wayfair.com/",
    
    # Sports
    "https://www.espn.com/",
    
    # Recipes & Lifestyle
    "https://www.allrecipes.com/",
    "https://www.epicurious.com/",
]


# ==========================================
# PROXY ERROR DETECTION
# ==========================================
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


async def handle_generic_consent(page: Page, behavior: dict):
    """Clears generic cookie banners found on random web pages."""
    try:
        selectors = [
            "button:has-text('Accept all' i)", "button:has-text('I agree' i)", 
            "button:has-text('Accept Cookies' i)", "button:has-text('Got it' i)",
            "button#onetrust-accept-btn-handler", ".cookie-banner button"
        ]
        for sel in selectors:
            btn = page.locator(sel).first
            if await btn.is_visible(timeout=1000):
                await click_humanly(page, btn, behavior)
                await asyncio.sleep(lognormal_delay(800, 2000))
                return
    except Exception:
        pass


async def click_random_visible_link(page: Page, behavior: dict) -> bool:
    """Finds a visually prominent link on the page and clicks it using Fitts's Law."""
    try:
        links = await page.locator("a:visible").all()
        valid_links = []
        for link in links:
            box = await link.bounding_box()
            if box and box["width"] > 10 and box["height"] > 10:
                valid_links.append(link)

        if valid_links:
            target_link = random.choice(valid_links[:15])
            await target_link.scroll_into_view_if_needed()
            await asyncio.sleep(lognormal_delay(1000, 2500))
            await click_humanly(page, target_link, behavior)
            return True
    except Exception as e:
        log.debug(f"Failed to find or click a visible link: {e}")
    
    return False


# ---------------------------------------------------------------------------
# RESILIENT GOTO - try multiple URLs until one loads
# ---------------------------------------------------------------------------
async def _resilient_goto(page: Page, candidate_urls: list, persona_name: str,
                          mode_label: str, timeout: int = 30000) -> str:
    """
    Try candidate URLs one by one. Return the first one that loads successfully.
    Skip ones that fail with proxy-block errors.
    Returns None if all fail.
    """
    for i, url in enumerate(candidate_urls):
        try:
            log.info(f"    🧭 [{persona_name}] {mode_label} attempt {i+1}/{len(candidate_urls)}: {url}")
            await page.goto(url, timeout=timeout, wait_until="domcontentloaded")
            return url
        except Exception as e:
            err = str(e)
            if _is_proxy_block(err):
                log.info(f"    ⏭️ [{persona_name}] Blocked through proxy, trying next site...")
                continue
            # Non-proxy error - bubble up
            log.warning(f"    ⚠️ [{persona_name}] Unexpected error on {url}: {err[:100]}")
            return None
    log.warning(f"    ❌ [{persona_name}] All {len(candidate_urls)} candidates blocked through proxy.")
    return None


async def wander_session(page: Page, profile_dict: dict):
    persona_name = profile_dict.get("persona", {}).get("name", "UnknownBot")
    behavior = profile_dict.get("behavior", {})
    
    log.info(f"🌍 [{persona_name}] Starting Web Wander session...")

    all_referrers = load_referrers()

    modes = ["search", "direct"]
    weights = [0.5, 0.5]
    
    if all_referrers and len(all_referrers) > 0 and "YourSubreddit" not in all_referrers[0]:
        modes.append("referrer_strike")
        weights = [0.40, 0.35, 0.25] 

    mode = random.choices(modes, weights=weights)[0]

    try:
        if mode == "referrer_strike":
            # ---------------------------------------------------------
            # MODE C: EXTERNAL REFERRER STRIKE (unchanged)
            # ---------------------------------------------------------
            target_url = random.choice(all_referrers)
            log.info(f"    🚀 [{persona_name}] Mode C: External Referrer Strike!")
            log.info(f"    🧭 [{persona_name}] Navigating to Referrer: {target_url}")
            
            await page.goto(target_url, timeout=60000, wait_until="domcontentloaded")
            await handle_generic_consent(page, behavior)
            await smart_wait(page)

            log.info(f"    👀 [{persona_name}] Reading the referrer post/article...")
            await human_scroll(page, behavior)
            await idle_reading(page, {**behavior, "read_pause_range": (3, 8)})

            log.info(f"    🔎 [{persona_name}] Searching page for YouTube video link...")
            yt_links = await page.locator("a[href*='youtube.com/watch'], a[href*='youtu.be']").all()
            
            if yt_links:
                target_yt = random.choice(yt_links)
                await target_yt.scroll_into_view_if_needed()
                await asyncio.sleep(random.uniform(1.0, 3.0))
                log.info(f"    🖱️ [{persona_name}] Found YouTube link! Clicking through to YouTube...")
                await click_humanly(page, target_yt, behavior)
                await smart_wait(page, timeout=8000)
                watch_time = random.uniform(30, 120)
                log.info(f"    📺 [{persona_name}] Arrived at YouTube. Watching for {watch_time:.0f}s.")
                await asyncio.sleep(watch_time)
            else:
                log.warning(f"    ⚠️ [{persona_name}] No YouTube links found on the referrer page. Bouncing.")

        elif mode == "search":
            # ---------------------------------------------------------
            # MODE A: AI-Powered Search across SEARCH ENGINES
            # PATCHED: 75% Tier 1 engines, 25% variety pool, with retry
            # ---------------------------------------------------------
            log.info(f"    🧠 [{persona_name}] Mode A: Third-Party Search Engine")
            
            raw_search_term = await generate_dynamic_search(profile_dict, "Web")
            safe_search_term = urllib.parse.quote_plus(raw_search_term)
            
            # Build candidate list: 3 search engines to try
            candidates = []
            for _ in range(3):
                if random.random() < 0.75:
                    # 75% chance: Tier 1 (proven to work)
                    base = random.choice(TIER_1_SEARCH_ENGINES)
                else:
                    # 25% chance: variety pool
                    base = random.choice(SEARCH_DIRECTORIES)
                candidates.append(base + safe_search_term)
            
            # Deduplicate while preserving order
            seen = set()
            candidates = [u for u in candidates if not (u in seen or seen.add(u))]
            
            loaded_url = await _resilient_goto(page, candidates, persona_name, "Mode A search")
            if not loaded_url:
                log.warning(f"    ⚠️ [{persona_name}] All search engine attempts blocked. Skipping wander.")
                return
            
            await handle_generic_consent(page, behavior)
            await smart_wait(page)

            log.info(f"    👀 [{persona_name}] Reviewing search results...")
            await human_scroll(page, behavior)
            await idle_reading(page, behavior)

            log.info(f"    🖱️ [{persona_name}] Looking for a result to click...")
            if await click_random_visible_link(page, behavior):
                log.info(f"        ✅ [{persona_name}] Clicked a result. Reading destination page...")
                await smart_wait(page)
                await human_scroll(page, behavior)
                await idle_reading(page, behavior)
            else:
                log.warning(f"        ⚠️ [{persona_name}] Couldn't find valid link, staying on results.")

        else:
            # ---------------------------------------------------------
            # MODE B: Direct High-Trust Site Browsing
            # PATCHED: uses SAFE_HIGH_TRUST_SITES + retry
            # ---------------------------------------------------------
            log.info(f"    🏢 [{persona_name}] Mode B: Direct Authority Browsing")
            
            # Pick 3 random sites to try in order
            candidates = random.sample(SAFE_HIGH_TRUST_SITES, k=min(3, len(SAFE_HIGH_TRUST_SITES)))
            
            loaded_url = await _resilient_goto(page, candidates, persona_name, "Mode B browse")
            if not loaded_url:
                log.warning(f"    ⚠️ [{persona_name}] All authority sites blocked. Skipping wander.")
                return
            
            await handle_generic_consent(page, behavior)
            await smart_wait(page)

            log.info(f"    👀 [{persona_name}] Scrolling homepage (Loading media & tracking pixels)...")
            await human_scroll(page, behavior)
            await idle_reading(page, behavior)

            log.info(f"    🖱️ [{persona_name}] Looking for an internal link to follow...")
            if await click_random_visible_link(page, behavior):
                log.info(f"        ✅ [{persona_name}] Clicked internal link. Reading next page...")
                await smart_wait(page)
                await human_scroll(page, behavior)
                await idle_reading(page, behavior)
            else:
                log.warning(f"        ⚠️ [{persona_name}] Link wasn't clickable, staying on current page.")

        log.info(f"🎉 [{persona_name}] Web Wander complete!")

    except Exception as e:
        log.error(f"❌ [{persona_name}] Failed to complete wander session: {e}")