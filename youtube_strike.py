"""
youtube_strike.py
-----------------
The "Red Zone" Target Execution Module.
Upgraded with External Traffic Spoofing, Audience Retention Graph Engineering (The Rewind Spike), 
Account Maturation Gating, and Fitts's Law physics.
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

async def force_360p(page: Page, profile_id: str, behavior: dict):
    """Saves proxy bandwidth and reduces memory footprint using Fitts's Law clicking."""
    try:
        player = page.locator("#movie_player").first
        if await player.is_visible(timeout=3000):
            # Move mouse over the player to reveal the controls
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
        pass # Let video play naturally if UI changes

async def execute_target_strike(page: Page, profile: dict, target_keyword: str, target_channel: str, warm_day: int = 15):
    """Executes the highly organic search, watch, and algorithmic manipulation sequence."""
    pid = profile["id"]
    behavior = profile.get("behavior", {})
    
    # 🛡️ ACCOUNT MATURATION GATING
    # We restrict social actions based on the age of the bot to prevent spam detection
    can_like = warm_day >= 10
    can_sub_comment = warm_day >= 25
    
    log.info(f"🎯 [{pid[:8]}] INITIATING TARGET STRIKE: '{target_keyword}' (Day {warm_day} Bot)")

    try:
        # 1. DISCOVERY ROUTING (Traffic Diversification)
        route_roll = random.random()
        found_target = False

        if route_roll < 0.35:
            # --- ROUTE A: EXTERNAL GOOGLE SEARCH (The High-Authority Signal) ---
            log.info(f"    🌐 [{pid[:8]}] Routing via External Google Search (High Authority)...")
            await page.goto("https://www.google.com", wait_until="domcontentloaded")
            await smart_wait(page, timeout=5000)
            
            # Dismiss Google consent if present
            consent = page.locator("button:has-text('Accept all' i)").first
            if await consent.is_visible(timeout=2000): await click_humanly(page, consent, behavior)
            
            # Search for the video on Google
            search_query = f"{target_keyword} {target_channel} youtube"
            await human_type(page, "textarea[name='q'], input[name='q']", search_query, behavior)
            await page.keyboard.press("Enter")
            await smart_wait(page, timeout=8000)
            
            # Hunt for the YouTube link in Google results
            yt_link = page.locator(f"a[href*='youtube.com/watch']:has-text('{target_channel}')").first
            if await yt_link.is_visible():
                await yt_link.scroll_into_view_if_needed()
                await asyncio.sleep(random.uniform(1.0, 2.0))
                await click_humanly(page, yt_link, behavior)
                found_target = True

        if not found_target and route_roll < 0.65:
            # --- ROUTE B: DIRECT YOUTUBE SEARCH ---
            log.info(f"    🔎 [{pid[:8]}] Routing via Native YouTube Search...")
            await page.goto("https://www.youtube.com", wait_until="domcontentloaded")
            await smart_wait(page, timeout=8000)
            
            search_box = page.locator("input#search, input[name='search_query']").first
            await click_humanly(page, search_box, behavior)
            await human_type(page, "input#search", target_keyword, behavior)
            await page.keyboard.press("Enter")
            await smart_wait(page, timeout=8000)
            
            for _ in range(5):
                target_el = page.locator(f"ytd-video-renderer:has-text('{target_channel}') a#video-title").first
                if await target_el.is_visible():
                    log.info(f"    🚨 [{pid[:8]}] Target acquired in Search! Clicking thumbnail...")
                    await click_humanly(page, target_el, behavior)
                    found_target = True
                    break
                await human_scroll(page, behavior)
                await asyncio.sleep(random.uniform(1.5, 3.0))

        if not found_target:
            # --- ROUTE C: THE CHANNEL PAGE FALLBACK ---
            log.info(f"    🛣️ [{pid[:8]}] Routing via Channel Page...")
            if "youtube.com" not in page.url:
                await page.goto("https://www.youtube.com", wait_until="domcontentloaded")
                await smart_wait(page)
            
            # Simple search just for the channel
            await human_type(page, "input#search", target_channel, behavior)
            await page.keyboard.press("Enter")
            await smart_wait(page, timeout=5000)
            
            channel_link = page.locator(f"ytd-channel-renderer:has-text('{target_channel}') a#main-link").first
            if await channel_link.is_visible():
                await click_humanly(page, channel_link, behavior)
                await smart_wait(page, timeout=5000)
                
                videos_tab = page.locator("div.yt-tab-shape-wiz__tab:has-text('Videos')").first
                if await videos_tab.is_visible():
                    await click_humanly(page, videos_tab, behavior)
                    await smart_wait(page, timeout=3000)
                
                # Pick the latest video
                first_vid = page.locator("ytd-rich-item-renderer a#video-title-link").first
                if await first_vid.is_visible():
                    await click_humanly(page, first_vid, behavior)
                    found_target = True

        if not found_target:
            log.warning(f"    ❌ [{pid[:8]}] Target not found through any route. Aborting strike.")
            return

        await smart_wait(page, timeout=10000)

        # 2. Preparation
        await force_360p(page, pid, behavior)
        await page.locator("body").click(force=True) # Ensure page focus for keyboard shortcuts

        # 3. Calculate Watch Time Entropy
        duration_str = "5:00"
        try:
            dur_el = page.locator(".ytp-time-duration").first
            if await dur_el.is_visible(): duration_str = await dur_el.inner_text()
        except Exception: pass
        
        total_seconds = 300 
        parts = duration_str.split(":")
        if len(parts) == 2: total_seconds = int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 3: total_seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])

        r = random.random()
        if r < 0.20: watch_pct = random.uniform(0.40, 0.60)  
        elif r < 0.70: watch_pct = random.uniform(0.65, 0.85) 
        elif r < 0.90: watch_pct = random.uniform(0.85, 0.95) 
        else: watch_pct = 1.0                                 

        target_watch_time = int(total_seconds * watch_pct)
        log.info(f"    ⏱️ [{pid[:8]}] Entropy Engine: Watching {watch_pct*100:.1f}% ({target_watch_time}s).")

        # 4. Deep Cognitive Micro-Interactions Loop
        time_watched = 0
        rewind_spiked = False

        while time_watched < target_watch_time:
            chunk = random.randint(15, 35)
            await asyncio.sleep(chunk)
            time_watched += chunk
            
            action_roll = random.random()
            
            # --- RETENTION GRAPH SPIKING (The Viral Rewind) ---
            # Midway through the video, force a rewind to rewatch a section.
            if not rewind_spiked and time_watched > (target_watch_time * 0.4) and random.random() < 0.35:
                log.info(f"    ⏪ [{pid[:8]}] RETENTION SPIKE: Rewinding 20s to re-watch a specific moment.")
                await page.keyboard.press("j")
                await asyncio.sleep(0.5)
                await page.keyboard.press("j") # Double tap for 20s
                time_watched -= 20 # Adjust math
                rewind_spiked = True
                continue

            # Standard Interactions
            if action_roll < 0.05:
                log.info(f"    ⏸️ [{pid[:8]}] Attention loss: Pausing video...")
                await page.keyboard.press("k")
                await asyncio.sleep(random.uniform(15, 45))
                await page.keyboard.press("k")
            elif action_roll < 0.20:
                more_btn = page.locator("tp-yt-paper-button#expand").first
                if await more_btn.is_visible(): await click_humanly(page, more_btn, behavior)
            elif action_roll < 0.30:
                await page.evaluate("window.scrollBy(0, 600)")
                await asyncio.sleep(random.uniform(5, 12))
                await page.evaluate("window.scrollTo(0, 0)")
            elif action_roll < 0.40:
                await page.keyboard.press("c") # Captions

        # 5. MATURATION-GATED Social Engagement
        if can_like and random.random() < 0.15: 
            like_btn = page.locator("button[aria-label^='like this video' i]").first
            if await like_btn.is_visible():
                await click_humanly(page, like_btn, behavior)
                log.info(f"    👍 [{pid[:8]}] Dropped a Like.")
                await asyncio.sleep(random.uniform(1.0, 2.5))

        if can_sub_comment and random.random() < 0.05: 
            sub_btn = page.locator("#subscribe-button-shape button").first
            if await sub_btn.is_visible() and "Subscribed" not in await sub_btn.inner_text():
                await click_humanly(page, sub_btn, behavior)
                log.info(f"    🔔 [{pid[:8]}] Subscribed to channel.")
                await asyncio.sleep(random.uniform(1.5, 3.0))

        if can_sub_comment and random.random() < 0.04: 
            log.info(f"    🧠 [{pid[:8]}] Analyzing DOM for contextual comment generation...")
            title_el = page.locator("h1.ytd-watch-metadata").first
            video_title = await title_el.inner_text() if await title_el.is_visible() else "Video"

            desc_el = page.locator("ytd-text-inline-expander#description-inline-expander").first
            desc_text = await desc_el.inner_text() if await desc_el.is_visible() else ""
            desc_text = desc_text[:500] 

            await page.evaluate("window.scrollBy(0, 600)")
            await asyncio.sleep(random.uniform(2.0, 4.0))
            
            comment_box = page.locator("#simplebox-placeholder").first
            if await comment_box.is_visible():
                await click_humanly(page, comment_box, behavior)
                await asyncio.sleep(random.uniform(1.0, 2.0))
                
                comment_text = await generate_contextual_comment(profile, video_title, desc_text)
                await human_type(page, "#contenteditable-root", comment_text, behavior)
                await asyncio.sleep(random.uniform(1.0, 2.0))
                
                submit_btn = page.locator("#submit-button").first
                await click_humanly(page, submit_btn, behavior)
                log.info(f"    💬 [{pid[:8]}] Left comment: '{comment_text}'")
                
            await page.evaluate("window.scrollTo(0, 0)")

        # 6. Post-Watch Handoff (The Up-Next Algorithm)
        log.info(f"    🤝 [{pid[:8]}] Executing Post-Watch Handoff (Up Next)...")
        sidebar_videos = await page.locator("ytd-compact-video-renderer a#thumbnail").all()
        if sidebar_videos:
            target_next = random.choice(sidebar_videos[:5])
            await target_next.scroll_into_view_if_needed()
            await asyncio.sleep(random.uniform(0.5, 1.5))
            await click_humanly(page, target_next, behavior)
            
            handoff_time = random.uniform(45, 90)
            log.info(f"    📺 [{pid[:8]}] Handoff successful. Watching for {handoff_time:.0f}s before exit.")
            await asyncio.sleep(handoff_time)

    except Exception as e:
        log.error(f"    ❌ [{pid[:8]}] Target strike failed/interrupted: {e}")