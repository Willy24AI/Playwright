"""
gmail_warm.py
-------------
Simulates Active Inbox Management. Navigates to Gmail, finds an email 
(prioritizing unread ones), opens it, reads it, and returns to the inbox.
"""

import asyncio
import logging
import random
from playwright.async_api import Page

from behavior_engine import human_scroll, move_mouse_humanly, smart_wait, lognormal_delay

log = logging.getLogger(__name__)

async def gmail_warm_session(page: Page, profile: dict):
    persona_name = profile.get("persona", {}).get("name", "UnknownBot")
    behavior = profile.get("behavior", {})
    
    log.info(f"📧 [{persona_name}] Starting Gmail Inbox Management session...")

    # 1. Navigate directly to the authenticated inbox
    await page.goto("https://mail.google.com/mail/u/0/#inbox", wait_until="domcontentloaded")
    await smart_wait(page, timeout=15000)

    try:
        # 2. Look for email rows. Google uses 'tr.zA' for all emails, and 'tr.zE' for unread ones.
        log.info(f"👀 [{persona_name}] Scanning inbox for emails to read...")
        
        # Try finding unread emails first, fallback to any email
        emails = await page.locator("tr.zE").all()
        if not emails:
            emails = await page.locator("tr.zA").all()

        if emails:
            # Pick one of the top 5 recent emails
            target_email = random.choice(emails[:5])
            
            box = await target_email.bounding_box()
            if box:
                await move_mouse_humanly(page, box["x"] + box["width"]/2, box["y"] + box["height"]/2)
                await asyncio.sleep(random.uniform(0.5, 1.2))
            
            await target_email.click()
            log.info(f"🖱️ [{persona_name}] Clicked an email. Reading...")
            await smart_wait(page)
            
            # 3. Read the email body
            # Gmail uses role="listitem" or deep divs for the email body. A general scroll works best.
            scroll_amount = random.randint(2, 5)
            for _ in range(scroll_amount):
                await human_scroll(page, behavior)
                await asyncio.sleep(lognormal_delay(1500, 4000))
                
            # 4. Go back to Inbox
            log.info(f"🔙 [{persona_name}] Returning to inbox...")
            back_btn = page.locator("div[aria-label='Back to Inbox']").first
            if await back_btn.is_visible():
                await back_btn.click()
            else:
                await page.go_back() # Fallback if UI changed
                
            await asyncio.sleep(random.uniform(2.0, 4.0))
            log.info(f"✅ [{persona_name}] Gmail session complete.")
            
        else:
            log.warning(f"⚠️ [{persona_name}] Inbox is empty or couldn't find email rows.")

    except Exception as e:
        log.error(f"❌ [{persona_name}] Failed to navigate Gmail: {e}")