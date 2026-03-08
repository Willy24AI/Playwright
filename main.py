"""
main.py
-------
Complete orchestrator for scalable daily browser warming.
Runs BOTH Google Search warming AND YouTube warming per session.

[UPGRADED ENTERPRISE FEATURES]
  1. Supabase Integration: Fetches active profiles dynamically from the cloud database.
  2. OpenAI Integration: Dynamically generates mathematically unique Google Search queries.
  3. Telemetry: Logs successful warm-up timestamps back to Supabase.
  4. Circadian Rhythm: The built-in scheduler (--schedule) drifts randomly by ±1.5 hours.
  5. PARALLEL EXECUTION: Uses an asyncio.Semaphore to run multiple profiles concurrently.

Usage:
  python main.py -c 5                   # Run 5 profiles concurrently (RECOMMENDED)
  python main.py --google-only          # Google Search only
  python main.py --youtube-only         # YouTube only
  python main.py --day 15               # specify warming day
  python main.py --schedule -c 5        # run daily on a schedule with 5 concurrent browsers
  python main.py --profile sarah_nyc    # run one specific profile ID
"""

import asyncio
import argparse
import logging
import os
import random
import time
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
from playwright.async_api import async_playwright

from auth import get_token
from mlx_api import start_profile, stop_profile
from profiles_config import fetch_active_profiles, update_last_run
from behavior_engine import (
    human_type,
    human_scroll,
    click_humanly,
    idle_reading,
    smart_wait,
    lognormal_delay,
    move_mouse_humanly,
)
from youtube_warm import youtube_warm_session
from llm_helper import generate_dynamic_search

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

# ---------------------------------------------------------------------------
# LOGGING
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

PERSONA_ICONS = {
    "sarah_nyc":     "👩‍💼", "marcus_austin": "🧑‍💻", "linda_chicago": "👩‍🍳",
    "james_london":  "🧑‍💼", "priya_la":      "👩‍🎨", "tom_houston":   "🧑‍🔧",
    "yuki_seattle":  "👩‍🔬",
}

def plog(profile_id: str, msg: str):
    icon = PERSONA_ICONS.get(profile_id, "👤")
    log.info(f"{icon} [{profile_id[:15]:15s}] {msg}")

# ---------------------------------------------------------------------------
# STEALTH PATCHES
# ---------------------------------------------------------------------------
STEALTH_SCRIPT = """
() => {
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined, configurable: true });
    Object.defineProperty(navigator, 'plugins', {
        get: () => { const a=[1,2,3,4,5]; a.__proto__=PluginArray.prototype; return a; }
    });
    Object.defineProperty(navigator, 'languages', { get: () => ['en-US','en'] });
    if (!window.chrome) window.chrome = { runtime: {} };
    const _q = window.navigator.permissions.query;
    window.navigator.permissions.query = (p) =>
        p.name==='notifications' ? Promise.resolve({state:Notification.permission}) : _q(p);
}
"""

def pick_result(results, weights):
    n = min(len(results), len(weights))
    if n == 0: return None
    return random.choices(results[:n], weights=weights[:n], k=1)[0]

async def handle_consent(page, pid):
    try:
        btn = page.locator("button:has-text('Accept all'), button:has-text('Alle akzeptieren')")
        if await btn.is_visible(timeout=3000):
            plog(pid, "🍪 Accepting cookie consent...")
            await btn.first.click()
            await asyncio.sleep(lognormal_delay(600, 1500))
    except Exception:
        pass

# ---------------------------------------------------------------------------
# GOOGLE SEARCH SESSION
# ---------------------------------------------------------------------------
async def google_session(page, profile: dict):
    pid = profile["id"]
    behavior = profile["behavior"]
    topic = await generate_dynamic_search(profile, platform="Google Search")

    plog(pid, f"🔍 Google: '{topic}'")
    await page.goto("https://www.google.com", wait_until="domcontentloaded")
    await smart_wait(page)
    await handle_consent(page, pid)
    await idle_reading(page, {**behavior, "read_pause_range": (1, 3)})

    await human_type(page, "textarea[name='q'], input[name='q']", topic, behavior)
    await asyncio.sleep(lognormal_delay(200, 700))
    await page.keyboard.press("Enter")
    await smart_wait(page)

    plog(pid, "Reading search results...")
    await idle_reading(page, behavior)

    results = []
    for sel in ["div.g h3", "[data-sokoban-container] h3", "div[jscontroller] h3", "h3.LC20lb"]:
        results = await page.locator(sel).all()
        if len(results) >= 2: break

    if not results:
        plog(pid, "⚠️ No results found")
        return

    target = pick_result(results, behavior["result_position_weights"])
    if not target: return

    plog(pid, f"Clicking result...")
    try:
        await target.scroll_into_view_if_needed(timeout=5000)
        await page.evaluate("window.scrollBy(0, -150)") 
        await asyncio.sleep(lognormal_delay(300, 800))
    except Exception:
        pass
        
    try:
        await click_humanly(page, target, behavior)
    except Exception as e:
        plog(pid, "⚠️ Standard click failed, using forced JS click.")
        await target.evaluate("el => el.click()")

    await smart_wait(page)
    await asyncio.sleep(lognormal_delay(800, 2500))

    plog(pid, "Reading article...")
    scroll_sessions = random.randint(*behavior["scroll_sessions"])
    for s in range(scroll_sessions):
        try:
            await human_scroll(page, behavior)
            if s < scroll_sessions - 1:
                await idle_reading(page, behavior)
        except Exception as e:
            if "closed" in str(e).lower(): return
            raise

    plog(pid, "✅ Google session complete")

# ---------------------------------------------------------------------------
# CORE PROFILE SESSION
# ---------------------------------------------------------------------------
async def warm_profile(profile: dict, token: str, run_google: bool = True, run_youtube: bool = True, warm_day: int = 15):
    pid = profile["id"]
    profile_id = profile["profile_id"]
    behavior = profile["behavior"]
    browser_cfg = profile["browser"]

    plog(pid, f"Starting warm session (Day {warm_day})")

    try:
        # Wrap the API call in run_in_executor to prevent blocking the async event loop
        loop = asyncio.get_running_loop()
        ws_url = await loop.run_in_executor(None, start_profile, profile_id, token)
    except Exception as e:
        plog(pid, f"❌ Could not start profile: {e}")
        return

    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp(ws_url)
        except Exception as e:
            plog(pid, f"❌ Playwright could not connect: {e}")
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, stop_profile, profile_id, token)
            return

        context = browser.contexts[0] if browser.contexts else await browser.new_context(
            viewport=browser_cfg["viewport"], locale=browser_cfg["locale"], timezone_id=browser_cfg["timezone"],
        )

        await context.add_init_script(STEALTH_SCRIPT)
        page = context.pages[0] if context.pages else await context.new_page()

        vp = browser_cfg["viewport"]
        await page.set_viewport_size({"width": vp["width"] + random.randint(-4, 4), "height": vp["height"] + random.randint(-4, 4)})

        try:
            sessions = []
            if run_google: sessions.append("google")
            if run_youtube: sessions.append("youtube")

            if len(sessions) == 2 and random.random() < 0.40:
                sessions.reverse()

            for session_type in sessions:
                if session_type == "google":
                    await google_session(page, profile)
                elif session_type == "youtube":
                    plog(pid, f"📺 Starting YouTube session...")
                    await youtube_warm_session(page, profile, behavior, warm_day=warm_day)
                    plog(pid, "✅ YouTube session complete")

                if len(sessions) > 1:
                    pause = random.uniform(15, 45)
                    plog(pid, f"⏸ Switching tasks in {pause:.0f}s...")
                    await asyncio.sleep(pause)

            plog(pid, "✅ Full warm session complete.")

        except Exception as e:
            plog(pid, f"⚠️ Session error: {e}")

        finally:
            try: await browser.close()
            except Exception: pass
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, stop_profile, profile_id, token)
            plog(pid, "💾 Profile stopped and cookies saved.")

# ---------------------------------------------------------------------------
# ORCHESTRATOR
# ---------------------------------------------------------------------------
async def run_all(selected_ids=None, run_google=True, run_youtube=True, warm_day=15, max_concurrent=3):
    log.info("🔑 Authenticating with Multilogin...")
    try:
        token = get_token()
    except Exception as e:
        log.error(f"❌ Authentication failed: {e}")
        return

    profiles_to_run = fetch_active_profiles(selected_ids)
    if not profiles_to_run:
        log.error("No matching profiles found in database.")
        return

    mode = []
    if run_google: mode.append("Google")
    if run_youtube: mode.append("YouTube")
    
    log.info(f"🚀 Launching {len(profiles_to_run)} profile(s) | Mode: {' + '.join(mode)} | Day {warm_day}")
    log.info(f"🚦 CONCURRENCY LEVEL: {max_concurrent} browsers at a time")

    # [NEW] The Semaphore limits how many browsers open at exactly the same time.
    sem = asyncio.Semaphore(max_concurrent)

    async def process_profile(profile):
        async with sem:
            # Add a slight random delay before starting to avoid hitting the Multilogin API exactly at the same millisecond
            await asyncio.sleep(random.uniform(0.5, 4.0))
            await warm_profile(profile, token, run_google, run_youtube, warm_day)
            update_last_run(profile["id"])
            # Small breather after closing before the Semaphore lets the next profile start
            await asyncio.sleep(random.uniform(2, 5))

    # Create and run all tasks concurrently
    tasks = [process_profile(profile) for profile in profiles_to_run]
    await asyncio.gather(*tasks)

    log.info("🏁 All profiles complete.\n")


# ---------------------------------------------------------------------------
# DAILY SCHEDULER
# ---------------------------------------------------------------------------
def run_scheduler(selected_ids=None, run_google=True, run_youtube=True, warm_day=15, concurrency=3):
    run_time = os.getenv("SCHEDULE_TIME", "09:00").strip()
    log.info(f"📅 Scheduler active — base target time is {run_time} daily.")
    log.info("   Press Ctrl+C to stop.\n")

    current_day = warm_day
    while True:
        now = datetime.now()
        h, m = map(int, run_time.split(":"))
        target = now.replace(hour=h, minute=m, second=0, microsecond=0)
        
        if target <= now:
            target += timedelta(days=1)
            
        jitter_minutes = random.uniform(-90, 90)
        actual_target = target + timedelta(minutes=jitter_minutes)
        
        if actual_target <= now:
            actual_target = now + timedelta(minutes=5)
            
        wait = (actual_target - now).total_seconds()

        log.info(f"⏰ Next run randomly shifted to {actual_target.strftime('%Y-%m-%d %H:%M:%S')} "
                 f"(in {wait/3600:.1f}h) | Warming day {current_day}")
        
        time.sleep(wait)
        log.info(f"▶ Daily warm starting — Day {current_day}")
        asyncio.run(run_all(selected_ids, run_google, run_youtube, current_day, max_concurrent=concurrency))
        current_day += 1

# ---------------------------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scalable Multilogin daily warmer")
    parser.add_argument("--profile", "-p", nargs="+", default=None)
    parser.add_argument("--schedule", "-s", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--google-only", action="store_true")
    parser.add_argument("--youtube-only", action="store_true")
    parser.add_argument("--day", type=int, default=15)
    
    # [NEW] Concurrency Argument
    parser.add_argument("--concurrency", "-c", type=int, default=3,
                        help="Number of browsers to run at the same time (default: 3)")
    
    args = parser.parse_args()

    run_google = not args.youtube_only
    run_youtube = not args.google_only

    if args.dry_run:
        db_profiles = fetch_active_profiles(args.profile)
        if db_profiles:
            log.info(f"Total profiles fetched: {len(db_profiles)}")
    elif args.schedule:
        run_scheduler(args.profile, run_google, run_youtube, args.day, args.concurrency)
    else:
        asyncio.run(run_all(args.profile, run_google, run_youtube, args.day, max_concurrent=args.concurrency))