"""
youtube_warm.py
---------------
Enterprise-grade YouTube warming module.
Upgraded with:
- Account Maturation Gating (Social actions tied to bot age)
- Retention Spike Simulation (Random rewinds during warming)
- Better Ad-Revenue simulation (The 'Investor' delay)
- Fitts's Law physics for UI interactions.
"""

import asyncio
import logging
import random
from pathlib import Path
from playwright.async_api import Page

from behavior_engine import (
    lognormal_delay, 
    move_mouse_humanly, 
    smart_wait, 
    click_humanly, 
    human_type, 
    human_scroll, 
    idle_reading
)
from llm_helper import generate_dynamic_search, generate_contextual_comment

log = logging.getLogger(__name__)

# Specific watch completion rates per persona to prevent uniform "bot-like" behavior
WATCH_COMPLETION = {
    "sarah_nyc": (0.55, 0.75), "marcus_austin": (0.65, 0.90),
    "linda_chicago": (0.70, 0.95), "james_london": (0.60, 0.80),
    "priya_la": (0.50, 0.75), "tom_houston": (0.70, 1.00), "yuki_seattle": (0.75, 0.95),
}

async def handle_youtube_consent(page: Page, behavior: dict):
    selectors = [
        "button[aria-label*='Accept' i]", "button:has-text('Accept all')",
        "ytd-button-renderer:has-text('Accept all')", ".ytd-consent-bump-v2-renderer button"
    ]
    for sel in selectors:
        try:
            btn = page.locator(sel).first
            if await btn.is_visible(timeout=2000):
                await click_humanly(page, btn, behavior)
                log.info("    🍪 Cleared YouTube consent banner.")
                await asyncio.sleep(random.uniform(1.5, 3.0))
                return
        except Exception:
            pass

async def handle_ads(page: Page, behavior: dict):
    """Simulates ad interaction. Watching full ads occasionally builds massive account trust."""
    try:
        skip_btn = page.locator(".ytp-ad-skip-button, .ytp-ad-skip-button-modern, .ytp-skip-ad-button").first
        if await skip_btn.is_visible(timeout=1500):
            # 80% chance to skip, 20% chance to watch full ad (Generating revenue for Google = High Trust)
            if random.random() < 0.80:
                # Wait 2-5 seconds after the skip button appears (Human reaction time)
                await asyncio.sleep(random.uniform(2.0, 5.0))
                await click_humanly(page, skip_btn, behavior)
                log.info("    ⏭️ Skipped ad after organic delay.")
            else:
                log.info("    💰 Decided to watch full ad to build account authority.")
                # We don't block the script, we just let it play while the watch loop continues
    except Exception: 
        pass

async def perform_social_signals(page: Page, behavior: dict, warm_day: int):
    """
    Performs social actions based on bot age (Maturation Gating).
    Young bots (Day < 10) should almost never subscribe.
    """
    # LIKES: 15% chance if account is at least 5 days old
    if warm_day >= 5 and random.random() < 0.15:
        try:
            like_btn = page.locator("button[aria-label*='like this video' i]").first
            if await like_btn.is_visible(timeout=2000):
                await click_humanly(page, like_btn, behavior)
                log.info("    👍 Dropped a Like.")
        except Exception: pass

    # SUBS: 10% chance if account is mature (Day 25+)
    if warm_day >= 25 and random.random() < 0.10:
        try:
            sub_btn = page.locator("#subscribe-button-shape button").first
            if await sub_btn.is_visible(timeout=2000) and "Subscribed" not in await sub_btn.inner_text():
                await click_humanly(page, sub_btn, behavior)
                log.info("    🔔 Subscribed to channel.")
        except Exception: pass

async def watch_video(page: Page, profile: dict, warm_day: int) -> bool:
    """The core watch loop with integrated macro-entropy."""
    pid = profile["id"]
    behavior = profile.get("behavior", {})
    log.info(f"    ▶️ Watching video content...")
    
    await handle_ads(page, behavior)
    
    # THE BAILOUT: 10% chance the bot hates the video and bounces
    if random.random() < 0.10:
        log.info("    🏃‍♂️ [BAILOUT] Persona lost interest. Bouncing early.")
        await asyncio.sleep(random.uniform(5, 15))
        return False

    # Calculate organic watch time
    total_seconds = 300 # Default
    try:
        duration_str = await page.locator(".ytp-time-duration").inner_text()
        parts = duration_str.split(":")
        total_seconds = int(parts[0]) * 60 + int(parts[1]) if len(parts) == 2 else 300
    except Exception: pass

    min_pct, max_pct = WATCH_COMPLETION.get(pid, (0.55, 0.80))
    target_watch_time = int(total_seconds * random.uniform(min_pct, max_pct))
    
    elapsed = 0
    social_triggered = False
    rewind_triggered = False

    while elapsed < target_watch_time:
        # Check for ads
        if elapsed % 45 == 0: await handle_ads(page, behavior)
        
        # Trigger social signals halfway through
        if not social_triggered and elapsed > (target_watch_time / 2):
            await perform_social_signals(page, behavior, warm_day)
            social_triggered = True

        # MACRO-ENTROPY: The Retention Spike (Rewind)
        # 20% chance to rewind 10s once per video to simulate re-watching a confusing/cool part
        if not rewind_triggered and elapsed > 60 and random.random() < 0.05:
            log.info("    ⏪ [REWIND] Rewatching last 10 seconds (Engagement Spike).")
            await page.keyboard.press("j")
            elapsed -= 10
            rewind_triggered = True

        # Fidgeting behavior
        roll = random.random()
        if roll < 0.10:
            await move_mouse_humanly(page, random.randint(100, 800), random.randint(100, 600))
        elif roll < 0.15:
            await page.mouse.wheel(0, random.uniform(-150, 150)) # Fidget scroll
            
        await asyncio.sleep(5)
        elapsed += 5

    return True

async def search_on_youtube(page: Page, profile: dict, behavior: dict):
    """Simulates organic search with autocomplete interactions."""
    topic = await generate_dynamic_search(profile, platform="YouTube")
    log.info(f"    🔍 Searching YouTube: '{topic}'")

    search_bar = "input#search, input[name='search_query']"
    search_loc = page.locator(search_bar).first
    await click_humanly(page, search_loc, behavior)
    
    # Type partial and wait for autocomplete
    partial = topic[:len(topic)//2]
    await human_type(page, search_bar, partial, behavior)
    await asyncio.sleep(random.uniform(1.0, 2.0))

    # 40% chance to pick an autocomplete suggestion
    if random.random() < 0.40:
        log.info("    ✨ Selecting Autocomplete suggestion.")
        await page.keyboard.press("ArrowDown")
        await asyncio.sleep(random.uniform(0.3, 0.7))
        await page.keyboard.press("Enter")
    else:
        await human_type(page, search_bar, topic[len(topic)//2:], behavior)
        await page.keyboard.press("Enter")
    
    await smart_wait(page)

async def youtube_warm_session(page: Page, profile: dict, behavior: dict, warm_day: int = 15):
    persona_name = profile.get("persona", {}).get("name", "UnknownBot")
    log.info(f"📺 [{persona_name}] Starting YouTube Warm session (Day {warm_day})...")

    await page.goto("https://www.youtube.com", wait_until="domcontentloaded")
    await handle_youtube_consent(page, behavior)
    await smart_wait(page)
    
    await search_on_youtube(page, profile, behavior)
    
    # Result selection entropy
    videos = await page.locator("ytd-video-renderer h3 a#video-title").all()
    if not videos: return

    # Weighting: Prefer top results but allow scrolling to lower results
    weights = [0.45, 0.30, 0.15, 0.07, 0.03]
    n = min(len(videos), len(weights))
    target_video = random.choices(videos[:n], weights=weights[:n], k=1)[0]
    
    await target_video.scroll_into_view_if_needed()
    await click_humanly(page, target_video, behavior)
    await smart_wait(page)
    
    # Watch main video
    finished = await watch_video(page, profile, warm_day)
    
    # THE RABBIT HOLE: 30% chance to follow a recommendation
    if finished and random.random() < 0.30:
        log.info("    🕳️ Falling down the rabbit hole (Next Video)...")
        sidebar = await page.locator("ytd-compact-video-renderer a#thumbnail").all()
        if sidebar:
            next_vid = random.choice(sidebar[:3])
            await click_humanly(page, next_vid, behavior)
            await smart_wait(page)
            await watch_video(page, profile, warm_day)

    log.info(f"🏁 [{persona_name}] YouTube Warm Complete.")