"""
youtube_strike.py
-----------------

Upgraded with:
- External Traffic Spoofing (Google, YouTube Search, Channel Page, Recommendations)
- Audience Retention Graph Engineering (The Rewind Spike)
- Account Maturation Gating
- Fitts's Law physics
- Ad handling during watch loop
- YouTube consent banner handling
- Multiple keyword support (each bot picks randomly)
- Channel browsing mode (discover videos organically from channel page)
- Graceful shutdown check during long watch loops
- Bailout entropy (small chance to bounce for realism)
- Search box clearing between route attempts
"""

import asyncio
import logging
import random
from playwright.async_api import Page

# Custom modules from your ecosystem
from behavior_engine import (
    move_mouse_humanly, smart_wait, human_scroll, 
    human_type, lognormal_delay, click_humanly, idle_reading
)
from llm_helper import generate_contextual_comment

log = logging.getLogger(__name__)

# Import shutdown flag (set by Ctrl+C handler in main.py)
try:
    from __main__ import shutdown_requested
except ImportError:
    shutdown_requested = False

def _is_shutdown():
    """Check if shutdown was requested."""
    try:
        from __main__ import shutdown_requested
        return shutdown_requested
    except:
        return False


# ---------------------------------------------------------------------------
# YOUTUBE HELPERS
# ---------------------------------------------------------------------------

async def handle_youtube_consent(page: Page, behavior: dict):
    """Clears YouTube cookie consent banner if present."""
    # Wait 3 seconds to ensure the consent modal has actually rendered
    await page.wait_for_timeout(3000)
    
    selectors = [
        "button[aria-label*='Accept' i]", 
        "button:has-text('Accept all')",
        "button:has-text('Alle akzeptieren')", # Common European proxy fallback
        "ytd-button-renderer:has-text('Accept all')", 
        ".ytd-consent-bump-v2-renderer button"
    ]
    for sel in selectors:
        try:
            btn = page.locator(sel).first
            if await btn.is_visible(timeout=2000):
                await btn.click(force=True) # Force click bypasses tricky z-indexes
                log.info("    🍪 Cleared YouTube consent banner.")
                await page.wait_for_timeout(3000) # Give UI time to remove overlay
                return
        except Exception:
            pass
async def handle_ads(page: Page, behavior: dict, pid: str):
    """Handles YouTube ads during playback. Sometimes watches full ad for trust."""
    try:
        skip_btn = page.locator(".ytp-ad-skip-button, .ytp-ad-skip-button-modern, .ytp-skip-ad-button").first
        if await skip_btn.is_visible(timeout=1500):
            if random.random() < 0.80:
                # Wait 2-5 seconds after skip button appears (human reaction time)
                await asyncio.sleep(random.uniform(2.0, 5.0))
                await click_humanly(page, skip_btn, behavior)
                log.info(f"    ⏭️ [{pid[:8]}] Skipped ad after organic delay.")
            else:
                log.info(f"    💰 [{pid[:8]}] Watching full ad to build account authority.")
                # Let the ad play — don't block, just continue the watch loop
    except Exception:
        pass

async def handle_google_consent(page: Page, behavior: dict):
    """Dismisses Google consent banner."""
    try:
        consent = page.locator("button:has-text('Accept all' i)").first
        if await consent.is_visible(timeout=2000):
            await click_humanly(page, consent, behavior)
            await asyncio.sleep(lognormal_delay(600, 1500))
    except Exception:
        pass

async def clear_search_box(page: Page, selector: str):
    """Clear any existing text in a search box before typing."""
    try:
        search_el = page.locator(selector).first
        if await search_el.is_visible(timeout=2000):
            await search_el.click()
            await page.keyboard.press("Control+a")
            await page.keyboard.press("Backspace")
            await asyncio.sleep(random.uniform(0.3, 0.6))
    except:
        pass

async def force_360p(page: Page, profile_id: str, behavior: dict):
    """Saves proxy bandwidth and reduces memory footprint."""
    try:
        player = page.locator("#movie_player").first
        if await player.is_visible(timeout=3000):
            box = await player.bounding_box()
            if box:
                await move_mouse_humanly(page, box["x"] + box["width"] * 0.5, box["y"] + box["height"] * 0.5)
            await asyncio.sleep(random.uniform(0.5, 1.0))
            
            gear_btn = page.locator("button.ytp-settings-button").first
            if await gear_btn.is_visible():
                await click_humanly(page, gear_btn, behavior)
                await asyncio.sleep(random.uniform(0.5, 1.2))
                
                quality_menu = page.locator("div.ytp-panel-menu >> text='Quality'").first
                if await quality_menu.is_visible():
                    await click_humanly(page, quality_menu, behavior)
                    await asyncio.sleep(random.uniform(0.5, 1.2))
                    
                    res_360 = page.locator("div.ytp-menuitem-label >> text='360p'").first
                    if await res_360.is_visible():
                        await click_humanly(page, res_360, behavior)
                        log.info(f"    ⚙️ [{profile_id[:8]}] Set resolution to 360p.")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# DISCOVERY ROUTES
# ---------------------------------------------------------------------------

async def route_google_search(page: Page, pid: str, behavior: dict, keyword: str, channel: str) -> bool:
    """Route A: Find video via Google Search (high-authority external signal)."""
    log.info(f"    🌐 [{pid[:8]}] Route: External Google Search (High Authority)...")
    
    await page.goto("https://www.google.com", wait_until="domcontentloaded")
    await smart_wait(page, timeout=5000)
    await handle_google_consent(page, behavior)
    
    search_query = f"{keyword} {channel} youtube"
    await human_type(page, "textarea[name='q'], input[name='q']", search_query, behavior)
    await page.keyboard.press("Enter")
    await smart_wait(page, timeout=8000)
    
    # Hunt for YouTube link in Google results
    yt_link = page.locator(f"a[href*='youtube.com/watch']:has-text('{channel}')").first
    if await yt_link.is_visible(timeout=5000):
        await yt_link.scroll_into_view_if_needed()
        await asyncio.sleep(random.uniform(1.0, 2.0))
        await click_humanly(page, yt_link, behavior)
        return True
    
    # Fallback: any YouTube link from results
    any_yt = page.locator("a[href*='youtube.com/watch']").first
    if await any_yt.is_visible(timeout=3000):
        await any_yt.scroll_into_view_if_needed()
        await asyncio.sleep(random.uniform(1.0, 2.0))
        await click_humanly(page, any_yt, behavior)
        return True
    
    return False

async def route_youtube_search(page: Page, pid: str, behavior: dict, keyword: str, channel: str) -> bool:
    """Route B: Find video via native YouTube search."""
    log.info(f"    🔎 [{pid[:8]}] Route: Native YouTube Search...")
    
    await page.goto("https://www.youtube.com", wait_until="domcontentloaded")
    await handle_youtube_consent(page, behavior)
    await smart_wait(page, timeout=8000)
    
    # Click and clear search box before typing
    search_box = page.locator("input#search, input[name='search_query']").first
    await click_humanly(page, search_box, behavior)
    await clear_search_box(page, "input#search")
    
    await human_type(page, "input#search", keyword, behavior)
    await page.keyboard.press("Enter")
    await smart_wait(page, timeout=8000)
    
    # Scroll through results looking for the target channel
    for scroll_attempt in range(5):
        target_el = page.locator(f"ytd-video-renderer:has-text('{channel}') a#video-title").first
        if await target_el.is_visible(timeout=2000):
            log.info(f"    🚨 [{pid[:8]}] Target acquired in Search! Clicking...")
            await click_humanly(page, target_el, behavior)
            return True
        await human_scroll(page, behavior)
        await asyncio.sleep(random.uniform(1.5, 3.0))
    
    # Fallback: click any result that looks relevant
    any_result = page.locator("ytd-video-renderer a#video-title").first
    if await any_result.is_visible(timeout=2000):
        log.info(f"    🔍 [{pid[:8]}] Channel not in top results, clicking best match...")
        await click_humanly(page, any_result, behavior)
        return True
    
    return False

async def route_channel_page(page: Page, pid: str, behavior: dict, channel: str, pick_random_video: bool = True) -> bool:
    """Route C: Find video via channel page (browse videos tab)."""
    log.info(f"    🛣️ [{pid[:8]}] Route: Channel Page Browse...")
    
    # ---------------------------------------------------------
    # 1. NAVIGATION: Direct URL vs. Native Search
    # ---------------------------------------------------------
    if channel.startswith("http"):
        log.info(f"    🌐 [{pid[:8]}] Direct URL detected, navigating straight to channel...")
        await page.goto(channel, wait_until="domcontentloaded")
        await handle_youtube_consent(page, behavior)
        await smart_wait(page, timeout=5000)
    else:
        # If it's just a name, search for it natively
        if "youtube.com" not in page.url:
            await page.goto("https://www.youtube.com", wait_until="domcontentloaded")
            await handle_youtube_consent(page, behavior)
            await smart_wait(page)
        
        # Clear and search for the channel
        search_box = page.locator("input#search, input[name='search_query']").first
        await click_humanly(page, search_box, behavior)
        await clear_search_box(page, "input#search")
        
        await human_type(page, "input#search", channel, behavior)
        await page.keyboard.press("Enter")
        await smart_wait(page, timeout=5000)
        
        # Find the channel in results
        channel_link = page.locator(f"ytd-channel-renderer:has-text('{channel}') a#main-link").first
        if not await channel_link.is_visible(timeout=5000):
            # Try alternative selector
            channel_link = page.locator(f"ytd-channel-renderer a#main-link").first
        
        if await channel_link.is_visible(timeout=3000):
            await click_humanly(page, channel_link, behavior)
            await smart_wait(page, timeout=5000)
        else:
            log.warning(f"    ⚠️ [{pid[:8]}] Could not find channel link in search results.")
            return False

    # ---------------------------------------------------------
    # 2. BROWSE VIDEOS TAB
    # ---------------------------------------------------------
    log.info(f"    👀 [{pid[:8]}] Browsing channel page...")
    await idle_reading(page, {**behavior, "read_pause_range": (2, 5)})
    
    # Click Videos tab (Using multiple fallbacks for YouTube's UI variations)
    videos_tab = page.locator("div.yt-tab-shape-wiz__tab:has-text('Videos'), div.tp-yt-paper-tab:has-text('Videos')").first
    if await videos_tab.is_visible(timeout=5000):
        await click_humanly(page, videos_tab, behavior)
        await page.wait_for_timeout(3000) # Wait for network request to fetch videos
    
    # ---------------------------------------------------------
    # 3. EXPLICIT WAIT FOR VIDEO RENDER (Proxy Safeguard)
    # ---------------------------------------------------------
    log.info(f"    ⏳ [{pid[:8]}] Waiting for videos to load...")
    try:
        # Give slow proxies up to 15 seconds to load the video grid
        await page.locator("a#video-title-link, a#video-title").first.wait_for(state="visible", timeout=15000)
    except Exception:
        log.warning(f"    ⚠️ [{pid[:8]}] Videos never loaded on channel page. Proxy too slow or channel is empty.")
        return False

    # ---------------------------------------------------------
    # 4. PICK A VIDEO & CLICK
    # ---------------------------------------------------------
    video_links = await page.locator("a#video-title-link, a#video-title").all()
    
    if video_links:
        if pick_random_video and len(video_links) > 1:
            # Pick from first 5 videos with weighted preference for newer ones
            pool = video_links[:min(5, len(video_links))]
            weights = [0.35, 0.25, 0.20, 0.12, 0.08][:len(pool)]
            target_vid = random.choices(pool, weights=weights, k=1)[0]
            log.info(f"    🎲 [{pid[:8]}] Picked random video from channel (1 of {len(pool)})")
        else:
            target_vid = video_links[0]
            log.info(f"    📌 [{pid[:8]}] Picking latest video from channel")
        
        await target_vid.scroll_into_view_if_needed()
        await asyncio.sleep(random.uniform(0.5, 1.5))
        await click_humanly(page, target_vid, behavior)
        return True
    
    return False
async def route_recommendation(page: Page, pid: str, behavior: dict, keyword: str, channel: str) -> bool:
    """Route D: Find video via YouTube recommendations (watch a related video first, then find target in sidebar)."""
    log.info(f"    🔄 [{pid[:8]}] Route: Recommendation Discovery...")
    
    await page.goto("https://www.youtube.com", wait_until="domcontentloaded")
    await handle_youtube_consent(page, behavior)
    await smart_wait(page, timeout=8000)
    
    # Search for a related topic (not the exact keyword)
    related_query = keyword.split()[0] if keyword else "trending"
    search_box = page.locator("input#search, input[name='search_query']").first
    await click_humanly(page, search_box, behavior)
    await clear_search_box(page, "input#search")
    
    await human_type(page, "input#search", related_query, behavior)
    await page.keyboard.press("Enter")
    await smart_wait(page, timeout=8000)
    
    # Click any video from results
    first_vid = page.locator("ytd-video-renderer a#video-title").first
    if await first_vid.is_visible(timeout=3000):
        await click_humanly(page, first_vid, behavior)
        await smart_wait(page, timeout=5000)
        
        # Watch briefly (30-60s)
        brief_watch = random.uniform(30, 60)
        log.info(f"    📺 [{pid[:8]}] Watching seed video for {brief_watch:.0f}s...")
        await asyncio.sleep(brief_watch)
        
        # Check sidebar for target channel
        sidebar_target = page.locator(f"ytd-compact-video-renderer:has-text('{channel}') a#thumbnail").first
        if await sidebar_target.is_visible(timeout=3000):
            log.info(f"    🎯 [{pid[:8]}] Found target in recommendations!")
            await sidebar_target.scroll_into_view_if_needed()
            await asyncio.sleep(random.uniform(0.5, 1.5))
            await click_humanly(page, sidebar_target, behavior)
            return True
        
        # If not found in sidebar, click a random recommendation and check again
        sidebar_vids = await page.locator("ytd-compact-video-renderer a#thumbnail").all()
        if sidebar_vids and len(sidebar_vids) > 2:
            random_rec = random.choice(sidebar_vids[:5])
            await click_humanly(page, random_rec, behavior)
            await smart_wait(page, timeout=5000)
            
            # Final check for target in new sidebar
            final_check = page.locator(f"ytd-compact-video-renderer:has-text('{channel}') a#thumbnail").first
            if await final_check.is_visible(timeout=3000):
                log.info(f"    🎯 [{pid[:8]}] Found target in 2nd-hop recommendations!")
                await click_humanly(page, final_check, behavior)
                return True
    
    return False


# ---------------------------------------------------------------------------
# CORE STRIKE EXECUTION
# ---------------------------------------------------------------------------

async def execute_target_strike(page: Page, profile: dict, target_keyword, target_channel: str, warm_day: int = 15):
    """
    Executes the highly organic search, watch, and algorithmic manipulation sequence.
    
    target_keyword can be:
    - A single string: "how to build a PC"
    - A list of strings: ["how to build a PC", "best gaming setup", "PC build guide"]
      Each bot picks one randomly for traffic diversity.
    """
    pid = profile["id"]
    behavior = profile.get("behavior", {})
    
    # Handle multiple keywords — pick one randomly per bot
    browse_mode = False
    if isinstance(target_keyword, list):
        if "__browse_channel__" in target_keyword:
            browse_mode = True
            keyword = target_channel  # Use channel name as the search term
            log.info(f"    🔎 [{pid[:8]}] Browse-channel mode: discovering videos organically")
        else:
            keyword = random.choice(target_keyword)
            log.info(f"    🎲 [{pid[:8]}] Picked keyword from pool: '{keyword}'")
    else:
        keyword = target_keyword
    
    # ACCOUNT MATURATION GATING
    can_like = warm_day >= 10
    can_sub_comment = warm_day >= 25
    
    log.info(f"🎯 [{pid[:8]}] INITIATING TARGET STRIKE: '{keyword}' -> {target_channel} (Day {warm_day})")

    try:
       # --- BAILOUT ENTROPY ---
        # 5% chance the bot "isn't interested" and bounces (realistic organic behavior)
        if random.random() < 0.05:
            log.info(f"    🏃 [{pid[:8]}] [BAILOUT] Bot decided not to search today. Skipping strike.")
            return

        # ---------------------------------------------------------
        # NEW: HOMEPAGE SEED WARMUP (Build organic session history)
        # ---------------------------------------------------------
        if browse_mode and random.random() < 0.85: # 85% chance to warm up first
            log.info(f"    📺 [{pid[:8]}] Building session history: Going to homepage first...")
            await page.goto("https://www.youtube.com", wait_until="domcontentloaded")
            await handle_youtube_consent(page, behavior)
            await smart_wait(page, timeout=5000)
            
            # Grab top videos from the homepage
            home_vids = await page.locator("ytd-rich-item-renderer a#video-title-link").all()
            if home_vids:
                seed_vid = random.choice(home_vids[:10]) # Pick randomly from top 10
                await seed_vid.scroll_into_view_if_needed()
                await asyncio.sleep(random.uniform(0.5, 1.5))
                await click_humanly(page, seed_vid, behavior)
                
                # Watch for 1 to 2.5 minutes
                seed_watch = random.uniform(60, 150) 
                log.info(f"    🍿 [{pid[:8]}] Watching random seed video for {seed_watch:.0f}s before striking...")
                
                # Wait 15s to let the video start, check for an ad, then finish waiting
                await asyncio.sleep(15) 
                await handle_ads(page, behavior, pid)
                await asyncio.sleep(max(0, seed_watch - 15))

        # --- DISCOVERY ROUTING (Traffic Diversification) ---
        found_target = False

        # --- PREPARATION ---
        await force_360p(page, pid, behavior)
        # Safely ensure focus without triggering Playwright viewport geometry errors
        await page.mouse.click(5, 5) 
        await page.evaluate("window.focus()")
        # --- CALCULATE WATCH TIME ---
        target_watch_time = int(total_seconds * watch_pct)
        log.info(f"    ⏱️ [{pid[:8]}] Watch plan: {watch_pct*100:.1f}% ({target_watch_time}s of {total_seconds}s)")

        # ---------------------------------------------------------
        # NEW: MAXIMUM WATCH TIME CAP (e.g., 10 minutes / 600 seconds)
        # ---------------------------------------------------------
        max_time_seconds = 600 
        if target_watch_time > max_time_seconds:
            log.info(f"    ⏳ [{pid[:8]}] Capping marathon session from {target_watch_time}s to {max_time_seconds}s.")
            target_watch_time = max_time_seconds
        duration_str = "5:00"
        try:
            dur_el = page.locator(".ytp-time-duration").first
            if await dur_el.is_visible(timeout=3000):
                duration_str = await dur_el.inner_text()
        except Exception:
            pass
        
        total_seconds = 300
        parts = duration_str.split(":")
        if len(parts) == 2:
            total_seconds = int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 3:
            total_seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])

        # Watch time entropy — varied completion rates
        r = random.random()
        if r < 0.15:
            watch_pct = random.uniform(0.35, 0.55)   # Short watch
        elif r < 0.60:
            watch_pct = random.uniform(0.60, 0.82)   # Standard watch
        elif r < 0.85:
            watch_pct = random.uniform(0.82, 0.95)   # Deep watch
        else:
            watch_pct = 1.0                           # Full completion

        target_watch_time = int(total_seconds * watch_pct)
        log.info(f"    ⏱️ [{pid[:8]}] Watch plan: {watch_pct*100:.1f}% ({target_watch_time}s of {total_seconds}s)")

        # --- DEEP WATCH LOOP ---
        time_watched = 0
        rewind_spiked = False
        ad_check_interval = 45  # Check for ads every 45s

        while time_watched < target_watch_time:
            # Check for shutdown
            if _is_shutdown():
                log.info(f"    🛑 [{pid[:8]}] Shutdown during watch. Exiting loop.")
                break
            
            chunk = random.randint(12, 30)
            await asyncio.sleep(chunk)
            time_watched += chunk
            
            # Handle ads periodically
            if time_watched % ad_check_interval < chunk:
                await handle_ads(page, behavior, pid)
            
            action_roll = random.random()
            
            # RETENTION GRAPH SPIKING (The Viral Rewind)
            if not rewind_spiked and time_watched > (target_watch_time * 0.4) and random.random() < 0.35:
                log.info(f"    ⏪ [{pid[:8]}] RETENTION SPIKE: Rewinding 20s to re-watch a moment.")
                await page.keyboard.press("j")
                await asyncio.sleep(0.5)
                await page.keyboard.press("j")  # Double tap for 20s
                time_watched -= 20
                rewind_spiked = True
                continue

            # Standard micro-interactions
            if action_roll < 0.04:
                # Pause/unpause (attention drift)
                log.info(f"    ⏸️ [{pid[:8]}] Attention loss: Pausing video...")
                await page.keyboard.press("k")
                await asyncio.sleep(random.uniform(10, 35))
                await page.keyboard.press("k")
            elif action_roll < 0.15:
                # Expand description
                more_btn = page.locator("tp-yt-paper-button#expand").first
                if await more_btn.is_visible(timeout=1000):
                    await click_humanly(page, more_btn, behavior)
            elif action_roll < 0.25:
                # Scroll to comments and back
                await page.evaluate("window.scrollBy(0, 600)")
                await asyncio.sleep(random.uniform(4, 10))
                await page.evaluate("window.scrollTo(0, 0)")
            elif action_roll < 0.30:
                # Toggle captions
                await page.keyboard.press("c")
            elif action_roll < 0.35:
                # Mouse fidget over player
                await move_mouse_humanly(page, random.randint(100, 800), random.randint(100, 500))
            elif action_roll < 0.40:
                # Scroll fidget
                await page.mouse.wheel(0, random.uniform(-100, 100))

        # --- MATURATION-GATED SOCIAL ENGAGEMENT ---
        
        # Likes (15% chance if account >= 10 days old)
        if can_like and random.random() < 0.15:
            try:
                like_btn = page.locator("button[aria-label*='like this video' i]").first
                if await like_btn.is_visible(timeout=2000):
                    await click_humanly(page, like_btn, behavior)
                    log.info(f"    👍 [{pid[:8]}] Dropped a Like.")
                    await asyncio.sleep(random.uniform(1.0, 2.5))
            except Exception:
                pass

        # Subscribe (5% chance if account >= 25 days old)
        if can_sub_comment and random.random() < 0.05:
            try:
                sub_btn = page.locator("#subscribe-button-shape button").first
                if await sub_btn.is_visible(timeout=2000) and "Subscribed" not in await sub_btn.inner_text():
                    await click_humanly(page, sub_btn, behavior)
                    log.info(f"    🔔 [{pid[:8]}] Subscribed to channel.")
                    await asyncio.sleep(random.uniform(1.5, 3.0))
            except Exception:
                pass

        # Comment (4% chance if account >= 25 days old)
        if can_sub_comment and random.random() < 0.04:
            try:
                log.info(f"    🧠 [{pid[:8]}] Generating contextual comment...")
                title_el = page.locator("h1.ytd-watch-metadata").first
                video_title = await title_el.inner_text() if await title_el.is_visible(timeout=2000) else "Video"

                desc_el = page.locator("ytd-text-inline-expander#description-inline-expander").first
                desc_text = await desc_el.inner_text() if await desc_el.is_visible(timeout=2000) else ""
                desc_text = desc_text[:500]

                await page.evaluate("window.scrollBy(0, 600)")
                await asyncio.sleep(random.uniform(2.0, 4.0))
                
                comment_box = page.locator("#simplebox-placeholder").first
                if await comment_box.is_visible(timeout=3000):
                    await click_humanly(page, comment_box, behavior)
                    await asyncio.sleep(random.uniform(1.0, 2.0))
                    
                    comment_text = await generate_contextual_comment(profile, video_title, desc_text)
                    await human_type(page, "#contenteditable-root", comment_text, behavior)
                    await asyncio.sleep(random.uniform(1.0, 2.0))
                    
                    submit_btn = page.locator("#submit-button").first
                    if await submit_btn.is_visible(timeout=2000):
                        await click_humanly(page, submit_btn, behavior)
                        log.info(f"    💬 [{pid[:8]}] Left comment: '{comment_text}'")
                    
                await page.evaluate("window.scrollTo(0, 0)")
            except Exception as e:
                log.debug(f"    Comment failed: {e}")

        # --- POST-WATCH HANDOFF (Up-Next Algorithm) ---
        if not _is_shutdown():
            log.info(f"    🤝 [{pid[:8]}] Post-Watch Handoff (Up Next)...")
            try:
                sidebar_videos = await page.locator("ytd-compact-video-renderer a#thumbnail").all()
                if sidebar_videos:
                    # Weighted pick from top 5 recommendations
                    pool = sidebar_videos[:min(5, len(sidebar_videos))]
                    weights = [0.35, 0.25, 0.20, 0.12, 0.08][:len(pool)]
                    target_next = random.choices(pool, weights=weights, k=1)[0]
                    
                    await target_next.scroll_into_view_if_needed()
                    await asyncio.sleep(random.uniform(0.5, 1.5))
                    await click_humanly(page, target_next, behavior)
                    
                    handoff_time = random.uniform(40, 90)
                    log.info(f"    📺 [{pid[:8]}] Handoff: Watching recommendation for {handoff_time:.0f}s...")
                    
                    # Watch in chunks so we can check for shutdown
                    watched_handoff = 0
                    while watched_handoff < handoff_time:
                        if _is_shutdown():
                            break
                        await asyncio.sleep(min(10, handoff_time - watched_handoff))
                        watched_handoff += 10
                        
                        # Check for ads during handoff too
                        if watched_handoff % 30 < 10:
                            await handle_ads(page, behavior, pid)
            except Exception:
                pass

        log.info(f"    🏁 [{pid[:8]}] Strike complete.")

    except Exception as e:
        log.error(f"    ❌ [{pid[:8]}] Target strike failed/interrupted: {e}")