"""
oauth_warm.py
-------------
Universal OAuth Handshake.
Dynamically navigates to an interest-based site chosen by the LLM 
and performs a 'Sign in with Google' handshake.
"""

import asyncio
import logging
import random
from playwright.async_api import Page
from behavior_engine import move_mouse_humanly, smart_wait, lognormal_delay
from llm_helper import generate_dynamic_search

log = logging.getLogger(__name__)

async def oauth_warm_session(page: Page, profile: dict):
    persona_name = profile.get("persona", {}).get("name", "UnknownBot")
    
    # 1. Ask LLM for a site based on interest
    domain = await generate_dynamic_search(profile, platform="OAuth Target")
    target_url = f"https://www.{domain.strip().lower()}"
    
    log.info(f"🔐 [{persona_name}] Attempting OAuth discovery on: {target_url}")

    try:
        await page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
        await smart_wait(page)

        # 2. Universal Search for 'Sign In' or 'Login'
        # Most sites hide the Google button inside a Login modal
        login_triggers = page.locator("a:has-text('Log in'), button:has-text('Sign in'), a:has-text('Get Started')").first
        if await login_triggers.is_visible(timeout=5000):
            await login_triggers.click()
            await asyncio.sleep(2)

        # 3. Universal Google Button Heuristic
        # We look for common attributes used by Google's Identity library
        google_selectors = [
            "button:has-text('Continue with Google')",
            "div[id*='google-signin']",
            "iframe[title*='Sign in with Google']",
            "button[aria-label*='Google']",
            "span:has-text('Sign in with Google')"
        ]
        
        google_btn = None
        for sel in google_selectors:
            loc = page.locator(sel).first
            if await loc.is_visible(timeout=2000):
                google_btn = loc
                break

        if google_btn:
            log.info(f"🖱️ [{persona_name}] Found Google Auth entry point on {domain}")
            
            # Catch the popup window
            async with page.context.expect_page() as popup_info:
                await google_btn.click(force=True)
            
            popup = await popup_info.value
            await popup.wait_for_load_state("domcontentloaded")
            
            # 4. Handle the actual Google Account Selector
            log.info(f"🛡️ [{persona_name}] Handling Google secure popup...")
            await smart_wait(popup, timeout=5000)
            
            # This part is standard across ALL sites because it's Google's own code
            account_selector = popup.locator("div[data-identifier], div.BHzsHc").first
            if await account_selector.is_visible(timeout=5000):
                await account_selector.click()
                log.info(f"✅ [{persona_name}] OAuth handshake complete for {domain}!")
                await asyncio.sleep(5) # Let the redirect happen
            else:
                await popup.close()
        else:
            log.warning(f"⚠️ [{persona_name}] Could not find a clear Google login on {domain}. Moving on.")

    except Exception as e:
        log.warning(f"❌ [{persona_name}] OAuth flow interrupted: {e}")