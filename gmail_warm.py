"""
gmail_warm.py
-------------
Advanced Inbox Management Simulation.
Bypasses heuristic detection via Fitts's Law clicking, chaotic task flows,
inbox triage (archive/delete), tab switching, and deep-reading link clicks.
"""

import asyncio
import logging
import random
from playwright.async_api import Page

from behavior_engine import click_humanly, human_scroll, move_mouse_humanly, smart_wait, lognormal_delay

log = logging.getLogger(__name__)

async def simulate_inbox_triage(page: Page, behavior: dict, persona_name: str):
    """Simulates a human mass-selecting promotional or spam emails to delete/archive."""
    log.info(f"    🧹 [{persona_name}] Initiating Inbox Triage (Organizing mail)...")
    try:
        # Find all unselected checkboxes in the email list
        checkboxes = await page.locator("div[role='checkbox'][aria-checked='false']").all()
        if not checkboxes or len(checkboxes) < 3:
            return

        # Randomly select 1 to 3 emails to triage
        to_triage = random.sample(checkboxes[:10], random.randint(1, 3))
        for box in to_triage:
            await click_humanly(page, box, behavior)
            await asyncio.sleep(lognormal_delay(400, 1200))
        
        # 70% chance to Archive, 30% chance to Delete
        if random.random() < 0.70:
            action_btn = page.locator("div[aria-label='Archive']").first
            action_name = "Archive"
        else:
            action_btn = page.locator("div[aria-label='Delete']").first
            action_name = "Delete"

        if await action_btn.is_visible(timeout=2000):
            await click_humanly(page, action_btn, behavior)
            log.info(f"    🗑️ [{persona_name}] Triaged selected emails via '{action_name}'.")
            await asyncio.sleep(lognormal_delay(1500, 3000))

    except Exception as e:
        log.debug(f"Triage skipped or interrupted: {e}")


async def switch_inbox_tabs(page: Page, behavior: dict, persona_name: str):
    """Simulates a user checking their Promotions or Social tabs."""
    try:
        tabs = ["Promotions", "Social", "Updates"]
        target_tab = random.choice(tabs)
        
        tab_element = page.locator(f"div[role='tab']:has-text('{target_tab}')").first
        if await tab_element.is_visible(timeout=2000):
            log.info(f"    🗂️ [{persona_name}] Checking the '{target_tab}' tab...")
            await click_humanly(page, tab_element, behavior)
            await smart_wait(page, timeout=5000)
            await asyncio.sleep(lognormal_delay(1000, 3000))
    except Exception:
        pass


async def gmail_warm_session(page: Page, profile: dict):
    persona_name = profile.get("persona", {}).get("name", "UnknownBot")
    behavior = profile.get("behavior", {})
    
    log.info(f"📧 [{persona_name}] Starting Advanced Gmail Management session...")

    # 1. Navigate directly to the authenticated inbox
    await page.goto("https://mail.google.com/mail/u/0/#inbox", wait_until="domcontentloaded")
    await smart_wait(page, timeout=15000)

    try:
        # 🎲 THE ENTROPY MATRIX: 30% chance to check another tab first
        if random.random() < 0.30:
            await switch_inbox_tabs(page, behavior, persona_name)

        # 🎲 THE ENTROPY MATRIX: 20% chance to perform Inbox Triage
        if random.random() < 0.20:
            await simulate_inbox_triage(page, behavior, persona_name)

        # 2. Look for email rows (tr.zA handles both read and unread)
        log.info(f"    👀 [{persona_name}] Scanning inbox for emails to read...")
        
        # Prioritize unread (tr.zE) but fallback to standard (tr.zA)
        emails = await page.locator("tr.zE").all()
        if not emails:
            emails = await page.locator("tr.zA").all()

        if emails:
            # Pick one of the top 8 recent emails using weighted randomness
            weights = [0.30, 0.25, 0.15, 0.10, 0.05, 0.05, 0.05, 0.05]
            n = min(len(emails), len(weights))
            target_email = random.choices(emails[:n], weights=weights[:n], k=1)[0]
            
            # Hover over the email to simulate reading the subject line
            box = await target_email.bounding_box()
            if box:
                # Target a random spot inside the email row, NOT the geometric center
                hover_x = box["x"] + box["width"] * random.uniform(0.2, 0.8)
                hover_y = box["y"] + box["height"] * random.uniform(0.2, 0.8)
                await move_mouse_humanly(page, hover_x, hover_y)
                await asyncio.sleep(lognormal_delay(800, 2500)) # Reading the subject line
            
            # Use our mathematically sound Fitts's Law clicker
            await click_humanly(page, target_email, behavior)
            log.info(f"    🖱️ [{persona_name}] Clicked an email. Reading...")
            await smart_wait(page)
            
            # 3. Read the email body
            # THE BAILOUT: 15% chance they realize it's boring and leave immediately
            if random.random() < 0.15:
                log.info(f"    🏃‍♂️ [{persona_name}] Email was uninteresting. Bailing out quickly...")
                await asyncio.sleep(random.uniform(1.0, 3.0))
            else:
                scroll_amount = random.randint(2, 6)
                for _ in range(scroll_amount):
                    await human_scroll(page, behavior)
                    await asyncio.sleep(lognormal_delay(1500, 4000))
                
                # DEEP READ: 15% chance to click a link inside the email (Massive Trust Signal)
                if random.random() < 0.15:
                    email_links = await page.locator("div.a3s a").all() # .a3s is the Gmail message body class
                    if email_links:
                        safe_link = random.choice(email_links[:5])
                        log.info(f"    🔗 [{persona_name}] Clicking outbound link inside email...")
                        
                        # Catch popup/new tab navigation
                        async with page.context.expect_page(timeout=10000) as new_page_info:
                            await click_humanly(page, safe_link, behavior)
                        
                        try:
                            new_page = await new_page_info.value
                            await new_page.wait_for_load_state("domcontentloaded")
                            await asyncio.sleep(random.uniform(4.0, 10.0))
                            await human_scroll(new_page, behavior)
                            await new_page.close()
                            log.info(f"    🔙 [{persona_name}] Returned from external link.")
                        except Exception:
                            pass # If new tab fails, just continue
                
            # 4. Go back to Inbox
            back_btn = page.locator("div[aria-label='Back to Inbox']").first
            if await back_btn.is_visible():
                await click_humanly(page, back_btn, behavior)
            else:
                await page.go_back()
                
            await asyncio.sleep(random.uniform(2.0, 4.0))
            log.info(f"    ✅ [{persona_name}] Gmail session complete.")
            
        else:
            log.warning(f"    ⚠️ [{persona_name}] Inbox is empty or couldn't find email rows.")

    except Exception as e:
        log.error(f"    ❌ [{persona_name}] Failed to navigate Gmail: {e}")