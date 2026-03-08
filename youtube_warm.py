"""
youtube_warm.py
---------------
Advanced YouTube warming module for all personas.
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
    """[NEW] Destroys YouTube's giant cookie banner before doing anything."""
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

async def type_with_typos(page, selector: str, text: str):
    await page.locator(selector).first.click()
    await asyncio.sleep(lognormal_delay(200, 500))
    keyboard = "abcdefghijklmnopqrstuvwxyz"
    for char in text:
        if random.random() < 0.04 and char.isalpha():
            await page.keyboard.type(random.choice(keyboard))
            await asyncio.sleep(random.uniform(0.1, 0.3))
            await page.keyboard.press("Backspace")
            await asyncio.sleep(random.uniform(0.1, 0.4))
        await page.keyboard.type(char)
        await asyncio.sleep(random.uniform(0.1, 0.5) if char == " " else random.uniform(0.04, 0.15))

async def handle_ads(page):
    try:
        skip_btn = page.locator(".ytp-ad-skip-button, .ytp-ad-skip-button-modern, .ytp-skip-ad-button").first
        if await skip_btn.is_visible(timeout=500):
            await asyncio.sleep(random.uniform(1.2, 3.5))
            await skip_btn.click()
            log.info("    ⏭️ Skipped ad")
    except Exception: pass

async def watch_video(page, profile: dict, stage: int, is_weekend: bool, resume_time: int = 0) -> bool:
    persona_id = profile["id"]
    log.info(f"    ▶️ Watching video (Stage {stage})...")
    
    await handle_ads(page)
    try:
        if await page.locator("#error-screen, .yt-player-error-message-renderer").is_visible(timeout=3000):
            return False
    except Exception: pass

    try:
        duration_el = await page.locator(".ytp-time-duration").text_content(timeout=5000)
        parts = duration_el.strip().split(":")
        if len(parts) == 2: total_seconds = int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 3: total_seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        else: total_seconds = random.randint(180, 600)
    except Exception:
        total_seconds = random.randint(180, 600)

    min_pct, max_pct = WATCH_COMPLETION.get(persona_id, (0.55, 0.80))
    if is_weekend:
        min_pct, max_pct = min(min_pct + 0.15, 0.90), min(max_pct + 0.15, 1.0)
        
    watch_seconds = max(10, (total_seconds * random.uniform(min_pct, max_pct)) - resume_time)
    log.info(f"    👁 Will watch for {watch_seconds:.0f}s (Weekend Mode: {is_weekend})")

    elapsed = 0
    while elapsed < watch_seconds:
        await handle_ads(page)
        action = random.choices(["idle", "mouse_move", "scroll_comments", "alt_tab"], weights=[0.55, 0.15, 0.15, 0.15])[0]

        if action == "idle":
            pause = random.uniform(5, 15)
            await asyncio.sleep(pause)
            elapsed += pause
        elif action == "mouse_move":
            await move_mouse_humanly(page, random.randint(400, 1000), random.randint(300, 600))
            elapsed += 2
        elif action == "scroll_comments" and stage >= 3:
            await page.mouse.wheel(0, random.uniform(300, 600))
            await asyncio.sleep(random.uniform(4, 8))
            await page.mouse.wheel(0, -random.uniform(300, 600))
            elapsed += 5
        elif action == "alt_tab" and stage >= 2:
            await page.evaluate("window.blur()")
            distraction_time = random.uniform(10, 30)
            await asyncio.sleep(distraction_time)
            await page.evaluate("window.focus()")
            elapsed += distraction_time

    if stage >= 3 and random.random() < 0.2:
        state = load_state()
        state[persona_id] = {"resume_url": page.url, "timestamp": elapsed + resume_time}
        save_state(state)
        log.info("    💾 Saved video state to resume later.")

    log.info(f"    ✅ Finished watching ({elapsed:.0f}s watched)")
    return True

async def leave_comment(page, profile: dict, stage: int):
    if stage < 4 or random.random() > 0.05: return
    log.info("    ✍️ Formulating a comment...")
    try:
        title_el = await page.locator("h1.ytd-watch-metadata").text_content(timeout=3000)
        video_title = title_el.strip() if title_el else "Unknown Video"
        
        more_btn = page.locator("tp-yt-paper-button#expand").first
        if await more_btn.is_visible(timeout=1000):
            await more_btn.click()
            await asyncio.sleep(1)
            
        desc_el = await page.locator("div#description-inline-expander").text_content(timeout=3000)
        video_desc = desc_el.strip() if desc_el else ""
    except Exception:
        video_title, video_desc = "Unknown Video", ""

    comment_text = await generate_contextual_comment(profile, video_title, video_desc)

    try:
        await page.mouse.wheel(0, 500)
        await asyncio.sleep(2)
        comment_box = page.locator("#simplebox-placeholder").first
        if await comment_box.is_visible(timeout=3000):
            await comment_box.click()
            await asyncio.sleep(1)
            await type_with_typos(page, "#contenteditable-root", comment_text)
            await asyncio.sleep(2)
            await page.locator("#submit-button").first.click()
            log.info(f"    🗣️ Left comment: '{comment_text}'")
    except Exception: pass

async def browse_and_hoard_tabs(page, stage: int):
    if stage < 4 or random.random() > 0.15: return
    try:
        recs = await page.locator("ytd-compact-video-renderer a#thumbnail").all()
        if len(recs) > 2:
            target = random.choice(recs[:6])
            target_url = await target.get_attribute("href")
            if target_url:
                new_tab = await page.context.new_page()
                await new_tab.goto(f"https://www.youtube.com{target_url}", wait_until="domcontentloaded")
                await new_tab.evaluate("window.blur()")
                log.info("    📑 Opened recommended video in background tab.")
                return new_tab
    except Exception: pass
    return None

async def search_on_youtube(page, profile: dict, behavior: dict) -> str:
    topic = await generate_dynamic_search(profile, platform="YouTube")
    log.info(f"    🔍 Searching YouTube for: '{topic}'")

    # [THE FIX] Added fallback selectors for the search bar (mobile vs desktop layouts)
    search_bar = page.locator("input#search, input[name='search_query']").first
    try:
        box = await search_bar.bounding_box()
        if box:
            await move_mouse_humanly(page, box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            await asyncio.sleep(lognormal_delay(200, 500))
            await page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    except Exception:
        await search_bar.click(force=True)

    await asyncio.sleep(lognormal_delay(300, 800))
    await type_with_typos(page, "input#search, input[name='search_query']", topic)
    await asyncio.sleep(lognormal_delay(300, 700))
    await page.keyboard.press("Enter")
    await smart_wait(page)
    await asyncio.sleep(lognormal_delay(2000, 5000))
    return topic

async def youtube_warm_session(page, profile: dict, behavior: dict, warm_day: int = 15):
    persona_id = profile["id"]
    stage = 4 if warm_day >= 15 else (3 if warm_day >= 8 else (2 if warm_day >= 4 else 1))
    is_weekend = datetime.now().weekday() >= 5
    log.info(f"    📅 Warming day {warm_day} → Stage {stage} | Binge Mode: {is_weekend}")

    state = load_state()
    if persona_id in state and random.random() < 0.3:
        resume_data = state.pop(persona_id)
        save_state(state)
        await page.goto(resume_data["resume_url"], wait_until="domcontentloaded")
        await handle_youtube_consent(page) # Check for consent!
        await smart_wait(page)
        await watch_video(page, profile, stage, is_weekend, resume_time=resume_data["timestamp"])
        return

    await page.goto("https://www.youtube.com", wait_until="domcontentloaded")
    await handle_youtube_consent(page) # [THE FIX] Check for consent immediately
    await smart_wait(page)
    
    await search_on_youtube(page, profile, behavior)

    videos = await page.locator("ytd-video-renderer h3 a").all()
    if not videos: return
    
    try:
        await click_humanly(page, videos[0], behavior)
    except Exception:
        await videos[0].evaluate("el => el.click()") # Fallback
        
    await smart_wait(page)

    background_tab = await browse_and_hoard_tabs(page, stage)
    await watch_video(page, profile, stage, is_weekend)
    await leave_comment(page, profile, stage)

    if background_tab:
        log.info("    🔄 Switching to background tab...")
        await page.close()
        await background_tab.bring_to_front()
        await background_tab.evaluate("window.focus()")
        await watch_video(background_tab, profile, stage, is_weekend)
        await background_tab.close()

    log.info(f"    ✅ YouTube session complete (Stage {stage})")