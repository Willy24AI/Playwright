"""
youtube_warm.py
---------------
Enterprise-grade YouTube warming module.
Includes Ad-Revenue generation, Social Signals, and Autocomplete Simulation.
"""

import asyncio
import json
import logging
import random
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from behavior_engine import lognormal_delay, move_mouse_humanly, smart_wait, click_humanly
from llm_helper import generate_dynamic_search, generate_contextual_comment

load_dotenv(dotenv_path=Path(__file__).parent / ".env")
log = logging.getLogger(__name__)
STATE_FILE = Path(__file__).parent / "youtube_state.json"

WATCH_COMPLETION = {
    "sarah_nyc": (0.55, 0.75), "marcus_austin": (0.65, 0.90),
    "linda_chicago": (0.70, 0.95), "james_london": (0.60, 0.80),
    "priya_la": (0.50, 0.75), "tom_houston": (0.70, 1.00), "yuki_seattle": (0.75, 0.95),
}

def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE, "r") as f: return json.load(f)
    return {}

def save_state(state):
    with open(STATE_FILE, "w") as f: json.dump(state, f, indent=4)

async def handle_youtube_consent(page):
    selectors = [
        "button[aria-label='Accept the use of cookies and other data for the purposes described']",
        "button:has-text('Accept all')", "button:has-text('Reject all')",
        "ytd-button-renderer:has-text('Accept all')"
    ]
    for sel in selectors:
        try:
            btn = page.locator(sel).first
            if await btn.is_visible(timeout=2000):
                await btn.click()
                log.info("    🍪 Cleared YouTube consent banner")
                await asyncio.sleep(2)
                return
        except Exception:
            pass

async def handle_ads(page):
    """
    [UPGRADED] Real humans sometimes watch ads. 
    Watching an ad makes Google money, which builds massive trust.
    """
    try:
        skip_btn = page.locator(".ytp-ad-skip-button, .ytp-ad-skip-button-modern, .ytp-skip-ad-button").first
        if await skip_btn.is_visible(timeout=1000):
            # 70% chance to skip, 30% chance to watch the ad to 'pay' Google
            if random.random() < 0.70:
                await asyncio.sleep(random.uniform(2.5, 7.0)) # Don't skip at exactly 5.0s
                await skip_btn.click()
                log.info("    ⏭️ Skipped ad after human delay.")
            else:
                log.info("    💰 Decided to watch the full ad to build account trust.")
                await asyncio.sleep(15) # Simulate watching
    except Exception: pass

async def perform_social_signals(page, stage: int):
    """
    [NEW] Performs Likes, Subscribes, and 'Watch Later' saves.
    """
    if stage < 2: return

    # 15% chance to Like
    if random.random() < 0.15:
        try:
            like_btn = page.locator("button[aria-label*='like this video']").first
            await like_btn.click(timeout=3000)
            log.info("    👍 Liked the video.")
            await asyncio.sleep(random.uniform(1, 3))
        except Exception: pass

    # 10% chance to Subscribe (Only in higher stages)
    if stage >= 3 and random.random() < 0.10:
        try:
            sub_btn = page.locator("ytd-subscribe-button-renderer button").first
            if "Subscribed" not in await sub_btn.text_content():
                await sub_btn.click(timeout=3000)
                log.info("    🔔 Subscribed to the channel.")
                await asyncio.sleep(random.uniform(1, 3))
        except Exception: pass

    # 5% chance to Add to Watch Later
    if stage >= 4 and random.random() < 0.05:
        try:
            await page.locator("button[aria-label='Save to playlist']").first.click()
            await asyncio.sleep(2)
            await page.locator("tp-yt-paper-checkbox:has-text('Watch later')").first.click()
            log.info("    📂 Added to Watch Later list.")
            await page.keyboard.press("Escape")
        except Exception: pass

async def watch_video(page, profile: dict, stage: int, is_weekend: bool, resume_time: int = 0) -> bool:
    persona_id = profile["id"]
    log.info(f"    ▶️ Watching video (Stage {stage})...")
    
    await handle_ads(page)
    
    # ... [Keep your duration extraction logic here] ...
    total_seconds = random.randint(180, 600) # Simplified for brevity

    min_pct, max_pct = WATCH_COMPLETION.get(persona_id, (0.55, 0.80))
    watch_seconds = max(10, (total_seconds * random.uniform(min_pct, max_pct)) - resume_time)

    elapsed = 0
    social_triggered = False
    
    while elapsed < watch_seconds:
        await handle_ads(page)
        
        # Trigger social signals halfway through the watch time
        if not social_triggered and elapsed > (watch_seconds / 2):
            await perform_social_signals(page, stage)
            social_triggered = True

        action = random.choices(["idle", "mouse_move", "scroll_comments", "alt_tab"], weights=[0.55, 0.15, 0.15, 0.15])[0]
        # ... [Keep your action loop logic here] ...
        await asyncio.sleep(5)
        elapsed += 5

    log.info(f"    ✅ Finished watching.")
    return True

async def search_on_youtube(page, profile: dict, behavior: dict) -> str:
    """
    [UPGRADED] Simulates Autocomplete selection.
    """
    topic = await generate_dynamic_search(profile, platform="YouTube")
    log.info(f"    🔍 Searching YouTube for: '{topic}'")

    search_bar = page.locator("input#search, input[name='search_query']").first
    await search_bar.click()
    
    # Type part of the query
    partial_text = topic[:len(topic)//2]
    await page.keyboard.type(partial_text, delay=random.randint(50, 150))
    await asyncio.sleep(random.uniform(1.5, 3.0))

    # 40% chance to just pick the first autocomplete suggestion
    if random.random() < 0.40:
        log.info("    ✨ Using YouTube Autocomplete suggestion.")
        await page.keyboard.press("ArrowDown")
        await asyncio.sleep(0.5)
        await page.keyboard.press("Enter")
    else:
        # Finish typing normally
        await page.keyboard.type(topic[len(topic)//2:], delay=random.randint(50, 150))
        await page.keyboard.press("Enter")
    
    await smart_wait(page)
    return topic

async def youtube_warm_session(page, profile: dict, behavior: dict, warm_day: int = 15):
    # ... [Keep your stage/weekend logic and page.goto here] ...
    await page.goto("https://www.youtube.com")
    await handle_youtube_consent(page)
    
    await search_on_youtube(page, profile, behavior)
    
    # Select video and watch
    videos = await page.locator("ytd-video-renderer h3 a").all()
    if videos:
        await videos[0].click()
        await smart_wait(page)
        await watch_video(page, profile, 4, True)
        await leave_comment(page, profile, 4)