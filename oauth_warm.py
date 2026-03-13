"""
oauth_warm.py
-------------
Universal OAuth Handshake.
Bypasses heuristic detection by simulating 'Consideration Telemetry' 
(reading the homepage before signing up), handles generic cookie banners, 
and executes Fitts's Law clicks on Google Identity popups.
"""

import asyncio
import logging
import random
from playwright.async_api import Page

from behavior_engine import (
    human_scroll, 
    click_humanly, 
    idle_reading, 
    smart_wait, 
    move_mouse_humanly,
    lognormal_delay
)
from llm_helper import generate_dynamic_search

log = logging.getLogger(__name__)

async def handle_generic_consent(page: Page):
    """Clicks generic cookie banners on unknown third-party sites."""
    try:
        selectors = [
            "button:has-text('Accept all')", "button:has-text('I agree')", 
            "button:has-text('Accept Cookies')", "button:has-text('Got it')",
            "button#onetrust-accept-btn-handler" # Extremely common enterprise cookie banner
        ]
        for sel in selectors:
            btn = page.locator(sel).first
            if await btn.is_visible(timeout=1500):
                await click_humanly(page, btn, {})
                await asyncio.sleep(lognormal_delay(1000, 2500))
                return
    except Exception:
        pass

async def oauth_warm_session(page: Page, profile: dict):
    persona_name = profile.get("persona", {}).get("name", "UnknownBot")
    behavior = profile.get("behavior", {})
    
    # 1. Ask LLM for a site based on interest
    domain = await generate_dynamic_search(profile, platform="OAuth Target")
    target_url = f"https://www.{domain.strip().lower()}"
    
    log.info(f"🔐 [{persona_name}] Attempting OAuth discovery on: {target_url}")

    try:
        await page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
        await handle_generic_consent(page)
        await smart_wait(page)

        # 2. CONSIDERATION TELEMETRY (Macro-Entropy)
        # Real humans don't instantly click login on a site they just discovered.
        log.info(f"    👀 [{persona_name}] Browsing homepage to build Consideration Telemetry...")
        scrolls = random.randint(1, 3)
        for _ in range(scrolls):
            await human_scroll(page, behavior)
            await idle_reading(page, behavior)
            
        # Scroll back to top where login buttons usually live
        log.info(f"    🔙 [{persona_name}] Scrolling back to top navigation...")
        await page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'})")
        await asyncio.sleep(random.uniform(1.5, 3.5))

        # 3. Universal Search for 'Sign In' or 'Login'
        login_selectors = "a:has-text('Log in' i), button:has-text('Sign in' i), a:has-text('Get Started' i), a:has-text('Sign Up' i)"
        login_trigger = page.locator(login_selectors).first
        
        if await login_trigger.is_visible(timeout=5000):
            log.info(f"    🖱️ [{persona_name}] Found site login trigger. Clicking...")
            await click_humanly(page, login_trigger, behavior)
            await asyncio.sleep(lognormal_delay(2000, 4000))

        # 4. Universal Google Button Heuristic
        google_selectors = [
            "button:has-text('Continue with Google' i)",
            "a:has-text('Continue with Google' i)",
            "div[id*='google-signin']",
            "button[aria-label*='Google' i]",
            "span:has-text('Sign in with Google' i)",
            "div:has-text('Sign in with Google' i)"
        ]
        
        google_btn = None
        for sel in google_selectors:
            loc = page.locator(sel).first
            if await loc.is_visible(timeout=2000):
                google_btn = loc
                break

        if google_btn:
            log.info(f"    🛡️ [{persona_name}] Found Google Auth entry point on {domain}")
            
            # Catch the popup window using Fitts's Law click
            try:
                async with page.context.expect_page(timeout=10000) as popup_info:
                    await click_humanly(page, google_btn, behavior)
                
                popup = await popup_info.value
                await popup.wait_for_load_state("domcontentloaded")
                
                # 5. Handle the actual Google Account Selector (The popup)
                log.info(f"    🔄 [{persona_name}] Handling Google secure popup...")
                await smart_wait(popup, timeout=5000)
                
                # This DOM belongs to Google, so selectors are highly standardized
                account_selector = popup.locator("div[data-identifier], div.BHzsHc, div[data-email]").first
                if await account_selector.is_visible(timeout=8000):
                    # Use our physics engine on the popup page context
                    await click_humanly(popup, account_selector, behavior)
                    log.info(f"    ✅ [{persona_name}] Selected Google Account.")
                    
                    # Sometimes Google asks "Continue as [Name]?" to confirm sharing data
                    confirm_btn = popup.locator("button:has-text('Continue')").first
                    if await confirm_btn.is_visible(timeout=4000):
                        await asyncio.sleep(random.uniform(1.0, 2.5))
                        await click_humanly(popup, confirm_btn, behavior)
                        log.info(f"    ✅ [{persona_name}] Confirmed OAuth data sharing.")

                    log.info(f"    🎉 [{persona_name}] OAuth handshake complete for {domain}!")
                    await asyncio.sleep(random.uniform(5.0, 8.0)) # Let the redirect to the main site happen
                else:
                    log.warning(f"    ⚠️ [{persona_name}] Google account selector not visible in popup.")
                    await popup.close()
            except Exception as e:
                log.warning(f"    ⚠️ [{persona_name}] Popup interception failed: {e}")
        else:
            log.warning(f"    ⚠️ [{persona_name}] Could not find a clear Google login on {domain}. Moving on.")

    except Exception as e:
        log.warning(f"    ❌ [{persona_name}] OAuth flow interrupted: {e}")