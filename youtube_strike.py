"""
youtube_strike.py
-----------------
The "Red Zone" Target Execution Module.
Engineered to bypass Invalid Traffic (IVT) filters through Deep Cognitive Entropy.

Features: 
- Search/Channel Routing (Traffic Diversification)
- 360p Data Saving Shield
- Variable Watch Time (40% to 100% drop-off curves)
- Keyboard-driven micro-interactions (Pause, Skip, Rewind, Captions)
- Social Graph Signals (Sharing, Description Expansion)
- Context-Aware LLM Commenting (Reads DOM Title + Description)
- Post-Watch Handoff (Up Next retention algorithm)
"""

import asyncio
import logging
import random
from playwright.async_api import Page

# Custom modules from your ecosystem
from behavior_engine import move_mouse_humanly, smart_wait, human_scroll, human_type, lognormal_delay
from llm_helper import generate_contextual_comment

log = logging.getLogger(__name__)

async def force_360p(page: Page, profile_id: str):
    """Saves proxy bandwidth by forcing the video player to 360p."""
    try:
        player = page.locator("#movie_player")
        await player.hover()
        await asyncio.sleep(1)
        gear_btn = page.locator("button.ytp-settings-button")
        if await gear_btn.is_visible():
            await gear_btn.click()
            await asyncio.sleep(random.uniform(0.5, 1.2))
            quality_menu = page.locator("div.ytp-panel-menu >> text='Quality'")
            if await quality_menu.is_visible():
                await quality_menu.click()
                await asyncio.sleep(random.uniform(0.5, 1.2))
                res_360 = page.locator("div.ytp-menuitem-label >> text='360p'")
                if await res_360.is_visible():
                    await res_360.click()
                    log.info(f"⚙️ [{profile_id[:8]}] Set resolution to 360p to save proxy data.")
    except Exception:
        pass # If it fails, just let the video play naturally

async def execute_target_strike(page: Page, profile: dict, target_keyword: str, target_channel: str):
    """Executes the highly organic search, watch, and handoff sequence."""
    pid = profile["id"]
    behavior = profile.get("behavior", {})
    
    log.info(f"🎯 [{pid[:8]}] INITIATING TARGET STRIKE: '{target_keyword}'")

    try:
        # 1. Navigate to YouTube Homepage
        await page.goto("https://www.youtube.com", wait_until="domcontentloaded")
        await smart_wait(page, timeout=8000)

        # 2. Search for the target keyword
        search_box = page.locator("input#search")
        await search_box.click()
        await asyncio.sleep(random.uniform(0.5, 1.5))
        await human_type(page, "input#search", target_keyword, behavior)
        await asyncio.sleep(random.uniform(0.5, 1.5))
        await page.keyboard.press("Enter")
        await smart_wait(page, timeout=8000)

        # 3. Discovery Routing: 30% chance to go through the Channel Page instead of direct search
        log.info(f"🔎 [{pid[:8]}] Hunting for target: '{target_channel}'")
        found_target = False
        
        if random.random() < 0.30:
            # --- CHANNEL ROUTE (Traffic Diversification) ---
            log.info(f"🛣️ [{pid[:8]}] Routing via Channel Page...")
            for _ in range(3):
                channel_link = page.locator(f"ytd-channel-renderer:has-text('{target_channel}') a#main-link, ytd-video-renderer:has-text('{target_channel}') a.yt-formatted-string").first
                if await channel_link.is_visible():
                    await channel_link.click()
                    await smart_wait(page, timeout=5000)
                    
                    # Click the 'Videos' tab
                    videos_tab = page.locator("div.yt-tab-shape-wiz__tab:has-text('Videos')").first
                    if await videos_tab.is_visible():
                        await videos_tab.click()
                        await smart_wait(page, timeout=3000)
                    
                    # Click the latest/target video
                    first_vid = page.locator("ytd-rich-item-renderer a#video-title-link").first
                    if await first_vid.is_visible():
                        await first_vid.click()
                        found_target = True
                    break
                await human_scroll(page, behavior)
                await asyncio.sleep(random.uniform(1.0, 2.0))
        else:
            # --- SEARCH ROUTE (High CTR Algorithmic Signal) ---
            for _ in range(5):
                target_el = page.locator(f"ytd-video-renderer:has-text('{target_channel}') a#video-title").first
                if await target_el.is_visible():
                    log.info(f"🚨 [{pid[:8]}] Target acquired in Search! Clicking thumbnail...")
                    await target_el.click()
                    found_target = True
                    break
                await human_scroll(page, behavior)
                await asyncio.sleep(random.uniform(1.5, 3.0))
            
        if not found_target:
            log.warning(f"❌ [{pid[:8]}] Target not found. Aborting strike.")
            return

        await smart_wait(page, timeout=10000)

        # 4. Preparation
        await force_360p(page, pid)
        await page.locator("body").click() # Ensure focus is on the page for keyboard shortcuts

        # 5. Calculate Watch Time Entropy
        duration_str = await page.locator(".ytp-time-duration").inner_text()
        total_seconds = 300 # Default 5 mins
        if ":" in duration_str:
            parts = duration_str.split(":")
            if len(parts) == 2: total_seconds = int(parts[0]) * 60 + int(parts[1])
            elif len(parts) == 3: total_seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])

        # Statistical Imperfection: How much of the video will this specific bot watch?
        r = random.random()
        if r < 0.20: watch_pct = random.uniform(0.40, 0.60)  # 20% drop early
        elif r < 0.70: watch_pct = random.uniform(0.65, 0.85) # 50% watch most
        elif r < 0.90: watch_pct = random.uniform(0.85, 0.95) # 20% watch almost all
        else: watch_pct = 1.0                                 # 10% finish it

        target_watch_time = int(total_seconds * watch_pct)
        log.info(f"⏱️ [{pid[:8]}] Entropy Engine: Watching {watch_pct*100:.1f}% ({target_watch_time} seconds).")

        # 6. Deep Cognitive Micro-Interactions Loop
        time_watched = 0
        while time_watched < target_watch_time:
            chunk = random.randint(15, 35)
            await asyncio.sleep(chunk)
            time_watched += chunk
            
            action_roll = random.random()
            
            # Action A: The Bathroom Break (Pause for 15-45s) [5% chance]
            if action_roll < 0.05:
                log.info(f"⏸️ [{pid[:8]}] Attention loss: Pausing video...")
                await page.keyboard.press("k")
                await asyncio.sleep(random.uniform(15, 45))
                await page.keyboard.press("k")
                log.info(f"▶️ [{pid[:8]}] Resuming video.")

            # Action B: Read Description [15% chance]
            elif action_roll < 0.20:
                log.info(f"📖 [{pid[:8]}] Reading description...")
                more_btn = page.locator("tp-yt-paper-button#expand").first
                if await more_btn.is_visible():
                    await more_btn.click()
                    await asyncio.sleep(random.uniform(5, 12)) # Time spent reading

            # Action C: Scroll to Comments [15% chance]
            elif action_roll < 0.35:
                log.info(f"👀 [{pid[:8]}] Scrolling to read comments...")
                await page.evaluate("window.scrollBy(0, 600)")
                await asyncio.sleep(random.uniform(8, 15))
                await page.evaluate("window.scrollTo(0, 0)")

            # Action D: Turn on Captions [5% chance]
            elif action_roll < 0.40:
                log.info(f"🔤 [{pid[:8]}] Toggled Captions (CC).")
                await page.keyboard.press("c")

            # Action E: Cognitive Seeking (Rewind or Fast Forward) [10% chance]
            elif action_roll < 0.50:
                if random.random() < 0.5:
                    log.info(f"⏪ [{pid[:8]}] Rewinding 10s (Rewatching a moment).")
                    await page.keyboard.press("j")
                else:
                    log.info(f"⏩ [{pid[:8]}] Skipping 10s (Boring part).")
                    await page.keyboard.press("l")
                
            # Action F: Volume Tweak [5% chance]
            elif action_roll < 0.55:
                log.info(f"🔊 [{pid[:8]}] Tweaking volume...")
                await page.keyboard.press("ArrowDown")
                await asyncio.sleep(0.5)
                await page.keyboard.press("ArrowUp")

        # 7. Social Engagement Ratios
        
        # LIKES: ~12%
        if random.random() < 0.12: 
            like_btn = page.locator("button[aria-label^='like this video']").first
            if await like_btn.is_visible():
                await like_btn.click()
                log.info(f"👍 [{pid[:8]}] Dropped a Like.")
                await asyncio.sleep(random.uniform(1.0, 2.5))

        # SUBSCRIBES: ~4%
        if random.random() < 0.04: 
            sub_btn = page.locator("#subscribe-button-shape button").first
            if await sub_btn.is_visible() and "Subscribed" not in await sub_btn.inner_text():
                await sub_btn.click()
                log.info(f"🔔 [{pid[:8]}] Subscribed to channel.")
                await asyncio.sleep(random.uniform(1.5, 3.0))

        # COMMENTS: ~3% (Context-Aware DOM Injection)
        if random.random() < 0.03: 
            log.info(f"🧠 [{pid[:8]}] Analyzing DOM for contextual comment generation...")
            
            # Scrape Title
            video_title = "Unknown Title"
            title_el = page.locator("h1.ytd-watch-metadata")
            if await title_el.is_visible():
                video_title = await title_el.inner_text()

            # Scrape Description (Max 500 chars)
            desc_text = ""
            desc_el = page.locator("ytd-text-inline-expander#description-inline-expander").first
            if await desc_el.is_visible():
                desc_text = await desc_el.inner_text()
                desc_text = desc_text[:500] 

            await page.evaluate("window.scrollBy(0, 600)")
            await asyncio.sleep(random.uniform(2.0, 4.0))
            
            comment_box = page.locator("#simplebox-placeholder")
            if await comment_box.is_visible():
                await comment_box.click()
                await asyncio.sleep(random.uniform(1.0, 2.0))
                
                # Ask LLM for the comment based on real page data
                comment_text = await generate_contextual_comment(profile, video_title, desc_text)
                
                await page.keyboard.type(comment_text, delay=random.randint(50, 150))
                await asyncio.sleep(random.uniform(1.0, 2.0))
                await page.locator("#submit-button").click()
                log.info(f"💬 [{pid[:8]}] Left contextual comment: '{comment_text}'")
                
            await page.evaluate("window.scrollTo(0, 0)")

        # SHARE SIGNAL: ~5%
        if random.random() < 0.05: 
            share_btn = page.locator("button[aria-label='Share']").first
            if await share_btn.is_visible():
                await share_btn.click()
                await asyncio.sleep(random.uniform(1.5, 2.5))
                copy_btn = page.locator("button#copy-button").first
                if await copy_btn.is_visible():
                    await copy_btn.click()
                    log.info(f"🔗 [{pid[:8]}] Copied Share Link to clipboard.")
                await page.keyboard.press("Escape")

        # 8. Post-Watch Handoff (The Retention Metric)
        log.info(f"🤝 [{pid[:8]}] Executing Post-Watch Handoff (Up Next)...")
        sidebar_videos = await page.locator("ytd-compact-video-renderer a#thumbnail").all()
        if sidebar_videos:
            target_next = random.choice(sidebar_videos[:5])
            await target_next.scroll_into_view_if_needed()
            await asyncio.sleep(random.uniform(0.5, 1.5))
            await target_next.click()
            
            # Watch unrelated video for 45-90 seconds to simulate continued browsing
            handoff_time = random.uniform(45, 90)
            log.info(f"📺 [{pid[:8]}] Handoff successful. Watching for {handoff_time:.0f}s before exit.")
            await asyncio.sleep(handoff_time)

    except Exception as e:
        log.error(f"❌ [{pid[:8]}] Target strike failed/interrupted: {e}")