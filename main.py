"""
main.py
-------
Nexus Enterprise Farm Orchestrator.
Complete production-ready brain for browser warming and targeted strikes.

[UPGRADED]: 
- Resilient Task Execution
- Playwright CDP Retry Matrix
- Database Bloat Protection (Free-Tier Safe)
- Viral Velocity Pacing (Beta Distribution S-Curve for Strikes)
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
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# Custom Modules
from auth import get_token
from mlx_api import start_profile, stop_profile
from profiles_config import fetch_active_profiles, update_last_run, update_profile_status
from behavior_engine import (
    human_type, human_scroll, click_humanly, idle_reading, 
    smart_wait, lognormal_delay, move_mouse_humanly
)

# Pillars
from youtube_warm import youtube_warm_session
from youtube_strike import execute_target_strike
from llm_helper import generate_dynamic_search
from wander_the_web import wander_session
from newsletter_sub import subscribe_to_newsletter
from maps_warm import maps_warm_session
from workspace_warm import workspace_warm_session
from calendar_warm import calendar_warm_session
from news_warm import news_warm_session
from gmail_warm import gmail_warm_session
from shopping_warm import shopping_warm_session
from oauth_warm import oauth_warm_session
from drive_warm import drive_warm_session

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

# ---------------------------------------------------------------------------
# LOGGING & PERSONA ICONS
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

PERSONA_ICONS = {
    "sarah_nyc": "👩‍💼", "marcus_austin": "🧑‍💻", "linda_chicago": "👩‍🍳",
    "james_london": "🧑‍💼", "priya_la": "👩‍🎨", "tom_houston": "🧑‍🔧",
    "yuki_seattle": "👩‍🔬",
}

def plog(profile_id: str, msg: str):
    icon = PERSONA_ICONS.get(profile_id, "👤")
    log.info(f"{icon} [{profile_id[:15]:15s}] {msg}")

# ---------------------------------------------------------------------------
# STEALTH PATCHES (EVADE TRACKING)
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
        btn = page.locator("button:has-text('Accept all' i), button:has-text('Alle akzeptieren' i)").first
        if await btn.is_visible(timeout=3000):
            plog(pid, "🍪 Accepting cookie consent...")
            await btn.click()
            await asyncio.sleep(lognormal_delay(600, 1500))
    except Exception:
        pass

# ---------------------------------------------------------------------------
# GOOGLE SEARCH SESSION
# ---------------------------------------------------------------------------
async def google_session(page, profile: dict):
    pid = profile["id"]
    behavior = profile.get("behavior", {})
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

    plog(pid, "👀 Reading search results...")
    await idle_reading(page, behavior)

    results = []
    for sel in ["div.g h3", "[data-sokoban-container] h3", "div[jscontroller] h3", "h3.LC20lb"]:
        results = await page.locator(sel).all()
        if len(results) >= 2: break

    if not results:
        plog(pid, "⚠️ No results found")
        return

    target = pick_result(results, behavior.get("result_position_weights", [0.4, 0.3, 0.2, 0.1]))
    if not target: return

    plog(pid, f"🖱️ Clicking organic result...")
    try:
        await target.scroll_into_view_if_needed(timeout=5000)
        await page.evaluate("window.scrollBy(0, -150)") 
        await asyncio.sleep(lognormal_delay(300, 800))
        await click_humanly(page, target, behavior)
    except Exception:
        await target.evaluate("el => el.click()")

    await smart_wait(page)
    await asyncio.sleep(lognormal_delay(800, 2500))

    scroll_sessions = random.randint(*behavior.get("scroll_sessions", [3, 6]))
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
# CORE PROFILE SESSION (THE ROUTER)
# ---------------------------------------------------------------------------
async def warm_profile(profile: dict, token: str, run_google: bool = True, run_youtube: bool = True, run_wander: bool = True, warm_day: int = 15, strike_keyword: str = None, strike_channel: str = None):
    pid = profile["id"]
    profile_id = profile.get("profile_id")
    behavior = profile.get("behavior", {})
    browser_cfg = profile.get("browser", {"viewport": {"width": 1920, "height": 1080}})

    plog(pid, f"🚀 Starting swarm sequence (Day {warm_day})")
    
    update_profile_status(pid, status="RUNNING", tasks=[])
    completed_tasks = []

    if not profile_id:
        plog(pid, "❌ Missing profile_id in profile data.")
        update_profile_status(pid, status="FAILED", error_msg="Missing MLX profile_id")
        return

    try:
        loop = asyncio.get_running_loop()
        ws_url = await loop.run_in_executor(None, start_profile, profile_id, token)
    except Exception as e:
        plog(pid, f"❌ MLX Launch Fail: {e}")
        update_profile_status(pid, status="FAILED", error_msg=f"MLX Error: {str(e)}")
        return

    async with async_playwright() as p:
        browser = None
        for attempt in range(3):
            try:
                browser = await p.chromium.connect_over_cdp(ws_url, timeout=15000)
                break
            except Exception as e:
                plog(pid, f"⚠️ CDP Connect timeout/refused (Attempt {attempt+1}/3). Retrying in 3s...")
                await asyncio.sleep(3)
                
        if not browser:
            plog(pid, f"❌ Playwright CDP Fail after 3 attempts.")
            await loop.run_in_executor(None, stop_profile, profile_id, token)
            update_profile_status(pid, status="FAILED", error_msg="CDP Connection Failed")
            return

        context = browser.contexts[0] if browser.contexts else await browser.new_context(
            viewport=browser_cfg.get("viewport"), locale=browser_cfg.get("locale"), timezone_id=browser_cfg.get("timezone")
        )
        await context.add_init_script(STEALTH_SCRIPT)
        page = context.pages[0] if context.pages else await context.new_page()

        vp = browser_cfg.get("viewport", {"width": 1920, "height": 1080})
        await page.set_viewport_size({"width": vp["width"] + random.randint(-4, 4), "height": vp["height"] + random.randint(-4, 4)})

        sessions = []
        if strike_keyword and strike_channel:
            sessions.append("youtube_strike")
            plog(pid, f"🎯 STRIKE MISSION Queued: {strike_keyword} -> {strike_channel}")
        
        if run_google: sessions.append("google")
        if run_youtube and "youtube_strike" not in sessions: sessions.append("youtube")
        if run_wander: sessions.append("wander")

        if random.random() < 0.20: sessions.append("newsletter")
        if random.random() < 0.30: sessions.append("maps")
        if random.random() < 0.15: sessions.append("workspace")
        if random.random() < 0.10: sessions.append("calendar")
        if random.random() < 0.25: sessions.append("news")
        if random.random() < 0.30: sessions.append("gmail") 
        if random.random() < 0.25: sessions.append("shopping")
        if random.random() < 0.10: sessions.append("oauth")
        if random.random() < 0.10: sessions.append("drive")

        random.shuffle(sessions) 

        for session_type in sessions:
            plog(pid, f"⚡ Active Task: {session_type.upper()}")
            
            try:
                if session_type == "google": await google_session(page, profile)
                elif session_type == "youtube": await youtube_warm_session(page, profile, behavior, warm_day=warm_day)
                # 🛡️ MATURATION UPGRADE: Passed warm_day into the strike function
                elif session_type == "youtube_strike": await execute_target_strike(page, profile, strike_keyword, strike_channel, warm_day=warm_day)
                elif session_type == "wander": await wander_session(page, profile) 
                elif session_type == "newsletter": await subscribe_to_newsletter(page, profile)
                elif session_type == "maps": await maps_warm_session(page, profile)
                elif session_type == "workspace": await workspace_warm_session(page, profile)
                elif session_type == "calendar": await calendar_warm_session(page, profile)
                elif session_type == "news": await news_warm_session(page, profile)
                elif session_type == "gmail": await gmail_warm_session(page, profile)
                elif session_type == "shopping": await shopping_warm_session(page, profile)
                elif session_type == "oauth": await oauth_warm_session(page, profile)
                elif session_type == "drive": await drive_warm_session(page, profile)

                completed_tasks.append(session_type)
                
                # 🛡️ DB BLOAT FIX: Removed intermediate updates to keep Supabase Free-Tier safe.
                # update_profile_status(pid, status="RUNNING", tasks=completed_tasks)
                
            except PlaywrightTimeoutError:
                plog(pid, f"⚠️ Task '{session_type}' timed out. Skipping to next module.")
            except Exception as e:
                plog(pid, f"⚠️ Task '{session_type}' encountered an error: {e}. Skipping.")

            if len(sessions) > 1 and session_type != sessions[-1]:
                pause = random.uniform(8, 20)
                plog(pid, f"⏸ Task Transition: {pause:.0f}s break...")
                await asyncio.sleep(pause)

        plog(pid, "✅ Daily routine completed. Flushing cookies...")
        update_profile_status(pid, status="SUCCESS", tasks=completed_tasks)
        
        try:
            await page.close()
            await context.close()
            await browser.close()
        except Exception: pass
        
        await loop.run_in_executor(None, stop_profile, profile_id, token)
        plog(pid, "💾 Profile saved and stopped cleanly.")


# ---------------------------------------------------------------------------
# ORCHESTRATOR
# ---------------------------------------------------------------------------
async def run_all(selected_ids=None, run_google=True, run_youtube=True, run_wander=True, warm_day=15, max_concurrent=15, region=None, strike_keyword=None, strike_channel=None, strike_window=2.0):
    log.info("🔑 Authenticating with Multilogin...")
    try:
        token = get_token()
    except Exception as e:
        log.error(f"❌ Auth Failed: {e}")
        return

    profiles_to_run = fetch_active_profiles(selected_ids, region=region)
    if not profiles_to_run:
        log.error(f"No active profiles found in database for region: {region or 'ALL'}.")
        return

    log.info(f"🚀 SWARM START: {len(profiles_to_run)} bots | Region: {region or 'GLOBAL'} | Concurrency: {max_concurrent}")
    sem = asyncio.Semaphore(max_concurrent)

    async def process_profile(profile):
        # 📈 VIRAL VELOCITY CURVE: S-Curve Pacing for Strike Missions
        base_stagger = random.uniform(1.0, 15.0) # Standard MLX port protection
        
        if strike_keyword:
            # We use a Beta Distribution (alpha=2, beta=4) to simulate an organic viral spike.
            # Start slow, spike sharply in the middle, and taper off with a long tail.
            window_seconds = strike_window * 3600
            velocity_delay = random.betavariate(2, 4) * window_seconds
            stagger = base_stagger + velocity_delay
            plog(profile["id"], f"🕒 Viral Velocity applied. Bot will launch in {stagger/60:.1f} minutes.")
        else:
            stagger = base_stagger
            
        await asyncio.sleep(stagger)
        
        async with sem:
            await warm_profile(profile, token, run_google, run_youtube, run_wander, warm_day, strike_keyword, strike_channel)
            update_last_run(profile["id"])
            await asyncio.sleep(random.uniform(2, 5))

    tasks = [process_profile(profile) for profile in profiles_to_run]
    await asyncio.gather(*tasks)
    log.info("🏁 Full Farm Cycle Complete.")

# ---------------------------------------------------------------------------
# DAILY SCHEDULER
# ---------------------------------------------------------------------------
def run_scheduler(selected_ids=None, run_google=True, run_youtube=True, run_wander=True, warm_day=15, concurrency=15, region=None, strike_keyword=None, strike_channel=None, strike_window=2.0):
    run_time = os.getenv("SCHEDULE_TIME", "09:00").strip()
    log.info(f"📅 Scheduler active — Daily target: {run_time} | Region: {region or 'GLOBAL'}")
    
    current_day = warm_day
    while True:
        now = datetime.now()
        h, m = map(int, run_time.split(":"))
        target = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if target <= now: target += timedelta(days=1)
            
        jitter = random.uniform(-90, 90)
        actual_target = target + timedelta(minutes=jitter)
        wait = (actual_target - now).total_seconds()

        log.info(f"⏰ Next run: {actual_target.strftime('%H:%M:%S')} (in {wait/3600:.1f}h)")
        time.sleep(max(wait, 0))
        
        asyncio.run(run_all(selected_ids, run_google, run_youtube, run_wander, current_day, max_concurrent=concurrency, region=region, strike_keyword=strike_keyword, strike_channel=strike_channel, strike_window=strike_window))
        current_day += 1

# ---------------------------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Nexus Enterprise Farm Orchestrator")
    parser.add_argument("--profile", "-p", nargs="+", default=None)
    parser.add_argument("--schedule", "-s", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--google-only", action="store_true")
    parser.add_argument("--youtube-only", action="store_true")
    parser.add_argument("--wander-only", action="store_true")
    parser.add_argument("--day", type=int, default=15)
    
    parser.add_argument("--concurrency", "-c", type=int, default=15)
    parser.add_argument("--region", "-r", type=str, default=None, help="Filter bots by timezone (e.g., 'australia', 'america')")
    
    parser.add_argument("--strike-keyword", type=str, default=None, help="Target search phrase for YouTube Strike")
    parser.add_argument("--strike-channel", type=str, default=None, help="Exact channel name for YouTube Strike verification")
    
    # NEW: Velocity Window Argument
    parser.add_argument("--strike-window", type=float, default=2.0, help="Hours to organically spread the strike traffic across.")

    args = parser.parse_args()

    g, y, w = True, True, True
    if args.google_only: y, w = False, False
    elif args.youtube_only: g, w = False, False
    elif args.wander_only: g, y = False, False

    if (args.strike_keyword and not args.strike_channel) or (args.strike_channel and not args.strike_keyword):
        log.error("❌ Strike Mission Error: You must provide BOTH --strike-keyword and --strike-channel.")
        exit(1)

    if args.dry_run:
        bots = fetch_active_profiles(args.profile, region=args.region)
        log.info(f"Dry-run: {len(bots)} profiles detected for region '{args.region or 'ALL'}'.")
        if args.strike_keyword:
            log.info(f"Dry-run Strike Active: Targeting '{args.strike_keyword}' on channel '{args.strike_channel}' over {args.strike_window} hours.")
    elif args.schedule:
        run_scheduler(args.profile, g, y, w, args.day, args.concurrency, args.region, args.strike_keyword, args.strike_channel, args.strike_window)
    else:
        asyncio.run(run_all(args.profile, g, y, w, args.day, max_concurrent=args.concurrency, region=args.region, strike_keyword=args.strike_keyword, strike_channel=args.strike_channel, strike_window=args.strike_window))