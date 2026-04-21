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

[FIXED]:
- truststore SSL fix for Multilogin X desktop app compatibility
- Cookie save order: Playwright closes FIRST, then MLX stops with verification
- Proxy error handling: probe recovery before aborting (handles transient drops)
- No WindowsSelectorEventLoopPolicy (breaks Playwright on Windows)
- Shutdown verification: retries MLX stop until profile actually closes
- Skip profiles already warmed in last N hours (prevents re-running on crash recovery)
- Mid-session proxy drops on ANY task (youtube, gmail, maps, etc.) now recover
  gracefully instead of killing the whole profile
"""

import asyncio
import argparse
import logging
import os
import random
import signal
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# Fix SSL: Use Windows native certificate store
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

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
# PROXY ERROR DETECTION
# ---------------------------------------------------------------------------
# All Chromium errors that mean "proxy hiccup" rather than "page broken".
# Applies to ANY session type — google, youtube, gmail, maps, shopping, etc.
PROXY_ERROR_SIGNATURES = (
    "ERR_INVALID_AUTH_CREDENTIALS",
    "ERR_PROXY_CONNECTION_FAILED",
    "ERR_TUNNEL_CONNECTION_FAILED",
    "ERR_PROXY_AUTH_REQUESTED",
    "ERR_PROXY_AUTH_UNSUPPORTED",
    "ERR_PROXY_CERTIFICATE_INVALID",
    "ERR_HTTPS_PROXY_TUNNEL_RESPONSE_REDIRECT",
)

def is_proxy_error(error_msg: str) -> bool:
    """Returns True if the error string indicates a proxy-layer problem."""
    return any(sig in error_msg for sig in PROXY_ERROR_SIGNATURES)


# ---------------------------------------------------------------------------
# GRACEFUL SHUTDOWN SYSTEM
# ---------------------------------------------------------------------------
shutdown_requested = False
running_profiles = {}  # {profile_id: token} — profiles currently in a browser session

def request_shutdown(signum=None, frame=None):
    """Called on Ctrl+C. Sets flag so workers stop picking up new profiles."""
    global shutdown_requested
    if shutdown_requested:
        log.warning("\n⚠️ Force kill! Cookies may not be saved.")
        os._exit(1)
    shutdown_requested = True
    log.warning("\n🛑 SHUTDOWN REQUESTED — Saving cookies for all running profiles...")
    log.warning("   (Press Ctrl+C again to force quit without saving)")

signal.signal(signal.SIGINT, request_shutdown)

async def register_running_profile(profile_id: str, token: str):
    global running_profiles
    running_profiles[profile_id] = token

async def unregister_running_profile(profile_id: str):
    global running_profiles
    running_profiles.pop(profile_id, None)

async def emergency_save_all():
    """Called during shutdown — stops all running MLX profiles to save cookies."""
    if not running_profiles:
        log.info("   No profiles running — clean exit.")
        return
    
    log.info(f"   💾 Saving {len(running_profiles)} running profiles...")
    folder_id = os.getenv("MLX_FOLDER_ID", "").strip()
    
    for profile_id, token in list(running_profiles.items()):
        try:
            stop_url = f"https://launcher.mlx.yt:45001/api/v2/profile/f/{folder_id}/p/{profile_id}/stop"
            headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
            async with httpx.AsyncClient(verify=False, timeout=10) as client:
                await client.get(stop_url, headers=headers)
            log.info(f"   ✅ {profile_id[:8]} — cookies saved")
        except Exception as e:
            log.warning(f"   ⚠️ {profile_id[:8]} — failed to save: {str(e)[:40]}")
    
    await asyncio.sleep(3)
    log.info("   💾 All profiles saved. Exiting cleanly.")


# ---------------------------------------------------------------------------
# SHUTDOWN VERIFICATION — ensure MLX actually closed the profile
# ---------------------------------------------------------------------------
async def verify_profile_stopped(profile_uuid: str, token: str, pid: str, max_retries: int = 3):
    """
    Verifies an MLX profile actually stopped. If not, re-sends stop signal.
    
    MLX returns:
      - 200 if the profile WAS running and is now stopping → still active, retry
      - 404 if the profile is NOT running → stopped confirmed
    """
    folder_id = os.getenv("MLX_FOLDER_ID", "").strip()
    if not folder_id:
        return
    
    stop_url = f"https://launcher.mlx.yt:45001/api/v2/profile/f/{folder_id}/p/{profile_uuid}/stop"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    
    for attempt in range(max_retries):
        await asyncio.sleep(2 + attempt)
        try:
            async with httpx.AsyncClient(verify=False, timeout=10) as client:
                resp = await client.get(stop_url, headers=headers)
                
                if resp.status_code == 404:
                    plog(pid, "✅ MLX profile confirmed stopped.")
                    return True
                elif resp.status_code == 200:
                    plog(pid, f"⚠️ MLX still had profile running, re-sent stop (try {attempt+1}/{max_retries})")
                else:
                    plog(pid, f"⚠️ Unexpected verify status {resp.status_code}")
                    return False
        except Exception as e:
            plog(pid, f"⚠️ Verify failed: {str(e)[:50]}")
    
    plog(pid, f"⚠️ Profile may still be running in MLX after {max_retries} stop attempts.")
    return False


# ---------------------------------------------------------------------------
# PROXY RECOVERY — probe whether a proxy is back after a hiccup
# ---------------------------------------------------------------------------
async def probe_proxy_recovery(page, pid: str, wait_seconds: int = 10) -> bool:
    """
    Called after a proxy error on ANY task. Waits, then probes a lightweight URL
    through the same browser to see if the proxy has recovered.
    
    Returns True if recovered, False if proxy is genuinely dead.
    
    Why generate_204? Tiny endpoint Google uses for connectivity checks.
    Loads in milliseconds, no parsing, perfect for "is the proxy alive" probes.
    """
    plog(pid, f"⏳ Waiting {wait_seconds}s for proxy to recover...")
    await asyncio.sleep(wait_seconds)
    
    probe_urls = [
        "https://www.google.com/generate_204",
        "https://www.gstatic.com/generate_204",
    ]
    
    for probe_url in probe_urls:
        try:
            await page.goto(probe_url, wait_until="domcontentloaded", timeout=15000)
            return True
        except Exception as e:
            err = str(e)
            if not is_proxy_error(err):
                # Non-proxy error on probe — try the next probe URL
                continue
    
    return False


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
async def warm_profile(profile: dict, token: str, run_google: bool = True, run_youtube: bool = True, run_wander: bool = True, warm_day: int = 15, strike_keyword: str = None, strike_channel: str = None, fast_mode: bool = False):
    pid = profile["id"]
    profile_id = profile.get("profile_id")
    behavior = profile.get("behavior", {})
    browser_cfg = profile.get("browser", {"viewport": {"width": 1920, "height": 1080}})

    mode_label = "⚡ FAST" if fast_mode else "🔄 FULL"
    plog(pid, f"🚀 Starting swarm sequence (Day {warm_day}) [{mode_label}]")
    
    update_profile_status(pid, status="RUNNING", tasks=[])
    completed_tasks = []
    proxy_recovery_attempts = 0
    MAX_PROXY_RECOVERIES = 2  # Allow up to 2 proxy recoveries per profile

    if not profile_id:
        plog(pid, "❌ Missing profile_id in profile data.")
        update_profile_status(pid, status="FAILED", error_msg="Missing MLX profile_id")
        return

    # --- LAUNCH PROFILE ---
    try:
        loop = asyncio.get_running_loop()
        ws_url = await loop.run_in_executor(None, start_profile, profile_id, token)
    except ConnectionError as e:
        if "PROXY_ERROR" in str(e):
            plog(pid, f"⚠️ Proxy dead — skipping profile")
            update_profile_status(pid, status="PROXY_ERROR", error_msg=str(e))
            return
        plog(pid, f"❌ MLX Launch Fail: {e}")
        update_profile_status(pid, status="FAILED", error_msg=f"MLX Error: {str(e)}")
        return
    except Exception as e:
        plog(pid, f"❌ MLX Launch Fail: {e}")
        update_profile_status(pid, status="FAILED", error_msg=f"MLX Error: {str(e)}")
        return

    await register_running_profile(profile_id, token)

    page = None
    context = None
    browser = None

    # --- CONNECT PLAYWRIGHT ---
    async with async_playwright() as p:
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
            await verify_profile_stopped(profile_id, token, pid)
            await unregister_running_profile(profile_id)
            update_profile_status(pid, status="FAILED", error_msg="CDP Connection Failed")
            return

        context = browser.contexts[0] if browser.contexts else await browser.new_context(
            viewport=browser_cfg.get("viewport"), locale=browser_cfg.get("locale"), timezone_id=browser_cfg.get("timezone")
        )
        await context.add_init_script(STEALTH_SCRIPT)
        
        context.set_default_timeout(60000)
        context.set_default_navigation_timeout(90000)
        
        page = context.pages[0] if context.pages else await context.new_page()

        vp = browser_cfg.get("viewport", {"width": 1920, "height": 1080})
        await page.set_viewport_size({"width": vp["width"] + random.randint(-4, 4), "height": vp["height"] + random.randint(-4, 4)})

        # --- BUILD SESSION LIST ---
        sessions = []
        if strike_keyword and strike_channel:
            sessions.append("youtube_strike")
            plog(pid, f"🎯 STRIKE MISSION Queued: {strike_keyword} -> {strike_channel}")
        
        if run_google: sessions.append("google")
        if run_youtube and "youtube_strike" not in sessions: sessions.append("youtube")
        
        if fast_mode:
            plog(pid, f"⚡ Fast mode: {len(sessions)} core sessions only")
        else:
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

        # --- EXECUTE SESSIONS ---
        for session_type in sessions:
            if shutdown_requested:
                plog(pid, "🛑 Shutdown requested — saving cookies and exiting...")
                break
            
            plog(pid, f"⚡ Active Task: {session_type.upper()}")
            
            try:
                if session_type == "google": await google_session(page, profile)
                elif session_type == "youtube": await youtube_warm_session(page, profile, behavior, warm_day=warm_day)
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
                
            except PlaywrightTimeoutError:
                plog(pid, f"⚠️ Task '{session_type}' timed out. Skipping to next module.")
            except Exception as e:
                error_msg = str(e)
                
                # PROXY HICCUP — recover instead of aborting (works for ANY task)
                if is_proxy_error(error_msg):
                    plog(pid, f"⚠️ Proxy hiccup during '{session_type}'.")
                    
                    if proxy_recovery_attempts >= MAX_PROXY_RECOVERIES:
                        plog(pid, f"❌ Proxy has failed {MAX_PROXY_RECOVERIES}+ times. Aborting remaining tasks.")
                        break
                    
                    proxy_recovery_attempts += 1
                    recovered = await probe_proxy_recovery(page, pid, wait_seconds=10)
                    
                    if recovered:
                        plog(pid, f"✅ Proxy recovered ({proxy_recovery_attempts}/{MAX_PROXY_RECOVERIES}). Continuing to next task.")
                        # Don't break — fall through to next task
                    else:
                        plog(pid, f"❌ Proxy still dead after probe. Aborting remaining tasks.")
                        break
                else:
                    # Non-proxy error — log and skip just this one task
                    plog(pid, f"⚠️ Task '{session_type}' encountered an error: {str(e)[:80]}. Skipping.")

            if len(sessions) > 1 and session_type != sessions[-1]:
                pause = random.uniform(3, 8) if fast_mode else random.uniform(8, 20)
                plog(pid, f"⏸ Task Transition: {pause:.0f}s break...")
                await asyncio.sleep(pause)

        # --- SHUTDOWN: Close Playwright FIRST, then MLX, then verify ---
        plog(pid, f"✅ Daily routine completed ({len(completed_tasks)}/{len(sessions)} tasks). Saving cookies...")
        update_profile_status(pid, status="SUCCESS", tasks=completed_tasks)
        
        # 1. Close Playwright first — disconnects CDP cleanly so MLX can shut down
        try:
            await page.close()
        except Exception: pass
        try:
            await context.close()
        except Exception: pass
        try:
            await browser.close()
        except Exception: pass
        
        # 2. Brief pause so Playwright fully releases the CDP connection
        await asyncio.sleep(2)
        
        # 3. Send stop signal to MLX (saves cookies to cloud)
        await loop.run_in_executor(None, stop_profile, profile_id, token)
        plog(pid, "💾 Stop signal sent, verifying shutdown...")
        
        # 4. Verify MLX actually stopped the profile (retries until confirmed)
        await verify_profile_stopped(profile_id, token, pid, max_retries=3)
        
        # 5. Remove from running tracker
        await unregister_running_profile(profile_id)
        
        plog(pid, "🏁 Profile session complete.")


# ---------------------------------------------------------------------------
# ORCHESTRATOR
# ---------------------------------------------------------------------------
async def run_all(selected_ids=None, run_google=True, run_youtube=True, run_wander=True, warm_day=15, max_concurrent=15, region=None, strike_keyword=None, strike_channel=None, strike_window=2.0, fast_mode=False, skip_recent_hours=0):
    log.info("🔑 Authenticating with Multilogin...")
    try:
        token = get_token()
    except Exception as e:
        log.error(f"❌ Auth Failed: {e}")
        return

    token_state = {"token": token, "last_refresh": time.time()}
    token_lock = asyncio.Lock()
    
    async def get_fresh_token():
        async with token_lock:
            age = time.time() - token_state["last_refresh"]
            if age > 1200:
                try:
                    loop = asyncio.get_running_loop()
                    new_token = await loop.run_in_executor(None, get_token)
                    token_state["token"] = new_token
                    token_state["last_refresh"] = time.time()
                    log.info("🔑 Token auto-refreshed")
                except Exception as e:
                    log.warning(f"⚠️ Token refresh failed: {e} — using existing token")
            return token_state["token"]

    profiles_to_run = fetch_active_profiles(selected_ids, region=region)
    if not profiles_to_run:
        log.error(f"No active profiles found in database for region: {region or 'ALL'}.")
        return

    # Skip profiles warmed recently
    if skip_recent_hours > 0:
        from profiles_config import get_supabase_client
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=skip_recent_hours)).isoformat()
        try:
            sb = get_supabase_client()
            recent_resp = sb.table("profiles")\
                .select("profile_id, last_used_at")\
                .eq("status", "google_logged_in")\
                .gte("last_used_at", cutoff)\
                .execute()
            recent_ids = {r["profile_id"] for r in (recent_resp.data or [])}
            
            before = len(profiles_to_run)
            profiles_to_run = [p for p in profiles_to_run if p.get("id") not in recent_ids]
            skipped = before - len(profiles_to_run)
            
            if skipped > 0:
                log.info(f"⏭️ Skipping {skipped} profiles warmed in last {skip_recent_hours}h")
        except Exception as e:
            log.warning(f"Could not filter recent profiles: {e}")
    
    if not profiles_to_run:
        log.info(f"✅ All profiles already warmed within last {skip_recent_hours}h. Nothing to do.")
        return

    mode_label = "⚡ FAST" if fast_mode else "🔄 FULL"
    log.info(f"🚀 SWARM START: {len(profiles_to_run)} bots | Region: {region or 'GLOBAL'} | Concurrency: {max_concurrent} | Mode: {mode_label}")
    
    if fast_mode:
        est_per_profile = 9
        est_total = (len(profiles_to_run) * est_per_profile) / max_concurrent
        log.info(f"⏱️ Estimated time: ~{est_total:.0f} minutes ({est_total/60:.1f} hours)")
    
    sem = asyncio.Semaphore(max_concurrent)

    async def process_profile(profile):
        if shutdown_requested:
            return
        
        base_stagger = random.uniform(1.0, 15.0)
        
        if strike_keyword:
            window_seconds = strike_window * 3600
            velocity_delay = random.betavariate(2, 4) * window_seconds
            stagger = base_stagger + velocity_delay
            plog(profile["id"], f"🕒 Viral Velocity applied. Bot will launch in {stagger/60:.1f} minutes.")
        else:
            stagger = base_stagger
        
        waited = 0
        while waited < stagger:
            if shutdown_requested:
                return
            await asyncio.sleep(min(1.0, stagger - waited))
            waited += 1.0
        
        if shutdown_requested:
            return
        
        async with sem:
            fresh_token = await get_fresh_token()
            await warm_profile(profile, fresh_token, run_google, run_youtube, run_wander, warm_day, strike_keyword, strike_channel, fast_mode=fast_mode)
            update_last_run(profile["id"])
            await asyncio.sleep(random.uniform(2, 5))

    tasks = [process_profile(profile) for profile in profiles_to_run]
    await asyncio.gather(*tasks, return_exceptions=True)
    
    if shutdown_requested:
        await emergency_save_all()
    
    log.info("🏁 Full Farm Cycle Complete.")

# ---------------------------------------------------------------------------
# DAILY SCHEDULER
# ---------------------------------------------------------------------------
def run_scheduler(selected_ids=None, run_google=True, run_youtube=True, run_wander=True, warm_day=15, concurrency=15, region=None, strike_keyword=None, strike_channel=None, strike_window=2.0, fast_mode=False, skip_recent_hours=0):
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
        
        asyncio.run(run_all(selected_ids, run_google, run_youtube, run_wander, current_day, max_concurrent=concurrency, region=region, strike_keyword=strike_keyword, strike_channel=strike_channel, strike_window=strike_window, fast_mode=fast_mode, skip_recent_hours=skip_recent_hours))
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
    
    parser.add_argument("--strike-keyword", type=str, nargs="+", default=None, help="Target search phrases for YouTube Strike (multiple = each bot picks randomly)")
    parser.add_argument("--strike-channel", type=str, default=None, help="Exact channel name for YouTube Strike verification")
    parser.add_argument("--strike-window", type=float, default=2.0, help="Hours to organically spread the strike traffic across.")
    parser.add_argument("--fast", action="store_true", help="Fast mode: Google + YouTube only, ~8-10 min per profile instead of ~22 min")
    parser.add_argument("--browse-channel", action="store_true", help="Strike via channel browsing: bots visit channel page and pick videos organically")
    
    parser.add_argument("--skip-recent", type=int, default=0, metavar="HOURS",
                        help="Skip profiles successfully warmed in the last N hours (default: 0, don't skip).")

    args = parser.parse_args()

    g, y, w = True, True, True
    if args.google_only: y, w = False, False
    elif args.youtube_only: g, w = False, False
    elif args.wander_only: g, y = False, False

    if (args.strike_keyword and not args.strike_channel) or (args.strike_channel and not args.strike_keyword and not args.browse_channel):
        log.error("❌ Strike Mission Error: You must provide BOTH --strike-keyword and --strike-channel, or use --browse-channel with --strike-channel.")
        exit(1)
    
    strike_kw = args.strike_keyword
    if args.browse_channel and args.strike_channel and not strike_kw:
        strike_kw = ["__browse_channel__"]

    if args.dry_run:
        bots = fetch_active_profiles(args.profile, region=args.region)
        log.info(f"Dry-run: {len(bots)} profiles detected for region '{args.region or 'ALL'}'.")
        if args.fast:
            est = (len(bots) * 9) / args.concurrency
            log.info(f"⚡ Fast mode: ~{est:.0f} min ({est/60:.1f} hours) at -c {args.concurrency}")
        if strike_kw:
            log.info(f"Dry-run Strike Active: Targeting {strike_kw} on channel '{args.strike_channel}' over {args.strike_window} hours.")
    elif args.schedule:
        run_scheduler(args.profile, g, y, w, args.day, args.concurrency, args.region, strike_kw, args.strike_channel, args.strike_window, fast_mode=args.fast, skip_recent_hours=args.skip_recent)
    else:
        # NOTE: Do NOT use WindowsSelectorEventLoopPolicy — it breaks Playwright
        asyncio.run(run_all(args.profile, g, y, w, args.day, max_concurrent=args.concurrency, region=args.region, strike_keyword=strike_kw, strike_channel=args.strike_channel, strike_window=args.strike_window, fast_mode=args.fast, skip_recent_hours=args.skip_recent))