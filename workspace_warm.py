"""
workspace_warm.py
-----------------
Generates massive Workspace telemetry by creating a new Google Doc, 
using the LLM to write out a unique paragraph, and renaming the document.
"""

import asyncio
import logging
import random
from playwright.async_api import Page

from behavior_engine import smart_wait, lognormal_delay
from llm_helper import generate_dynamic_search

log = logging.getLogger(__name__)

async def workspace_warm_session(page: Page, profile: dict):
    persona_name = profile.get("persona", {}).get("name", "UnknownBot")
    behavior = profile.get("behavior", {})
    
    log.info(f"📝 [{persona_name}] Starting Google Docs Productivity session...")

    # 1. Ask the LLM to write a totally unique paragraph based on the bot's topics
    log.info(f"🧠 [{persona_name}] Asking LLM to write a document draft...")
    doc_content = await generate_dynamic_search(profile, platform="Google Docs Draft")
    doc_content = doc_content.strip('"').strip()

    # 2. Navigate directly to the "Create Blank Document" URL
    log.info(f"🚀 [{persona_name}] Spinning up a new blank Google Doc...")
    await page.goto("https://docs.google.com/document/create", wait_until="domcontentloaded")
    await smart_wait(page, timeout=12000)

    try:
        # 3. Focus the main typing canvas (.kix-appview-editor)
        editor_canvas = page.locator(".kix-appview-editor").first
        await editor_canvas.click(timeout=10000)
        await asyncio.sleep(random.uniform(1.0, 2.0))

        log.info(f"⌨️ [{persona_name}] Typing document: '{doc_content[:45]}...'")
        
        # 4. Type the LLM content into the document natively
        min_kd, max_kd = 0.05, 0.15
        for char in doc_content:
            # Inject occasional human typos
            if random.random() < behavior.get("typo_rate", 0.03) and char.isalpha():
                await page.keyboard.type(random.choice("asdfghjkl"))
                await asyncio.sleep(random.uniform(0.2, 0.5))
                await page.keyboard.press("Backspace")
                await asyncio.sleep(random.uniform(0.1, 0.3))

            await page.keyboard.type(char)
            await asyncio.sleep(random.uniform(min_kd, max_kd))

        await asyncio.sleep(random.uniform(2.0, 4.0))

        # 5. Rename the document using a snippet of the LLM text
        if random.random() < 0.70:
            doc_title = f"{persona_name} - {doc_content[:15].strip()}..."
            log.info(f"🏷️ [{persona_name}] Renaming document to: {doc_title}")
            
            title_box = page.locator(".docs-title-input-label").first
            if await title_box.is_visible(timeout=3000):
                await title_box.click()
                await asyncio.sleep(1)
                await page.keyboard.type(doc_title)
                await page.keyboard.press("Enter")

        log.info(f"✅ [{persona_name}] Google Docs session complete. Document saved to Drive.")

    except Exception as e:
        log.error(f"❌ [{persona_name}] Failed to interact with Google Docs: {e}")