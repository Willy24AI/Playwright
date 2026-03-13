"""
workspace_warm.py
-----------------
Generates massive Workspace telemetry.
Bypasses heuristic detection via Organic Dashboard Navigation, Fitts's Law 
clicking, biometric canvas typing (with corrections), and Formatting Entropy.
"""

import asyncio
import logging
import random
from playwright.async_api import Page

from behavior_engine import (
    smart_wait, 
    lognormal_delay, 
    click_humanly, 
    move_mouse_humanly,
    human_scroll
)
from llm_helper import generate_dynamic_search

log = logging.getLogger(__name__)

async def organic_create_doc(page: Page, behavior: dict, persona_name: str) -> bool:
    """Navigates to the Docs dashboard and physically clicks the Blank template."""
    log.info(f"    🌐 [{persona_name}] Loading Google Docs Dashboard...")
    await page.goto("https://docs.google.com/document/u/0/", wait_until="domcontentloaded")
    await smart_wait(page, timeout=15000)

    # 1. Consideration Telemetry: Look at recent documents
    log.info(f"    👀 [{persona_name}] Reviewing recent documents...")
    await move_mouse_humanly(page, random.randint(300, 800), random.randint(300, 600))
    await asyncio.sleep(random.uniform(2.0, 5.0))
    
    # Optional scroll if they have existing docs
    if random.random() < 0.5:
        await human_scroll(page, behavior)
        await asyncio.sleep(random.uniform(1.0, 3.0))
        await page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'})")
        await asyncio.sleep(random.uniform(1.0, 2.0))

    # 2. Click the 'Blank' Template using Fitts's Law
    # Google uses a specific gallery for templates
    blank_template = page.locator("div[title='Blank' i], div[aria-label*='Blank' i], .docs-homescreen-templates-templateview-preview").first
    
    if await blank_template.is_visible(timeout=5000):
        log.info(f"    🖱️ [{persona_name}] Initiating new blank document...")
        await click_humanly(page, blank_template, behavior)
        await smart_wait(page, timeout=10000)
        return True
    else:
        log.warning(f"    ⚠️ [{persona_name}] Could not find Blank template. Falling back to URL injection.")
        await page.goto("https://docs.google.com/document/create", wait_until="domcontentloaded")
        await smart_wait(page, timeout=10000)
        return True

async def type_canvas_natively(page: Page, content: str, behavior: dict):
    """
    Specialized typing loop for the Google Docs Canvas. 
    Docs intercepts keystrokes, so we must feed them directly to page.keyboard 
    using log-normal delays and realistic typos.
    """
    # Base typing speeds from the behavior profile, mapped to a log-normal distribution
    base_delay = behavior.get("typing_speed_ms", 150) / 1000.0 
    typo_rate = behavior.get("typo_rate", 0.03)

    for char in content:
        # Pause longer on punctuation
        if char in [".", ",", "?", "!"]:
            await asyncio.sleep(lognormal_delay(300, 800))
        
        # Inject occasional human typos (fat-finger mistakes)
        if random.random() < typo_rate and char.isalpha():
            # Pick a random letter near the actual target on a QWERTY keyboard (simplified)
            wrong_char = random.choice("asdfghjkl") if char.islower() else random.choice("ASDFGHJKL")
            await page.keyboard.type(wrong_char)
            await asyncio.sleep(lognormal_delay(150, 400)) # Realize mistake
            await page.keyboard.press("Backspace")
            await asyncio.sleep(lognormal_delay(100, 250))

        # Type the correct character
        await page.keyboard.type(char)
        
        # Micro-delay between keystrokes
        await asyncio.sleep(random.uniform(base_delay * 0.5, base_delay * 1.5))

async def apply_formatting_entropy(page: Page, persona_name: str):
    """Simulates a user highlighting the last few words and making them Bold."""
    if random.random() < 0.30: # 30% chance to format text
        log.info(f"    🎨 [{persona_name}] Applying text formatting (Bold)...")
        try:
            # Highlight the last word/phrase using Shift + Ctrl + Left Arrow
            modifiers = ["Shift", "Control"] if "Mac" not in await page.evaluate("navigator.userAgent") else ["Shift", "Meta"]
            
            for mod in modifiers:
                await page.keyboard.down(mod)
            
            # Press left arrow a few times to highlight
            for _ in range(random.randint(2, 5)):
                await page.keyboard.press("ArrowLeft")
                await asyncio.sleep(random.uniform(0.1, 0.3))
                
            for mod in modifiers:
                await page.keyboard.up(mod)
                
            await asyncio.sleep(random.uniform(0.5, 1.0))
            
            # Press Ctrl+B (or Cmd+B) to bold
            cmd_key = "Meta" if "Mac" in await page.evaluate("navigator.userAgent") else "Control"
            await page.keyboard.down(cmd_key)
            await page.keyboard.press("b")
            await page.keyboard.up(cmd_key)
            
            # Press Right arrow to un-highlight and continue
            await asyncio.sleep(random.uniform(0.5, 1.0))
            await page.keyboard.press("ArrowRight")
            
        except Exception as e:
            log.debug(f"Formatting failed: {e}")

async def workspace_warm_session(page: Page, profile: dict):
    persona_name = profile.get("persona", {}).get("name", "UnknownBot")
    behavior = profile.get("behavior", {})
    
    log.info(f"📝 [{persona_name}] Starting Google Docs Productivity session...")

    # 1. Ask the LLM to write a totally unique paragraph
    log.info(f"    🧠 [{persona_name}] Asking LLM to write a document draft...")
    doc_content = await generate_dynamic_search(profile, platform="Google Docs Draft")

    try:
        # 2. Organic Navigation
        await organic_create_doc(page, behavior, persona_name)

        # 3. Focus the main typing canvas using Fitts's Law
        editor_canvas = page.locator(".kix-appview-editor").first
        if await editor_canvas.is_visible(timeout=10000):
            await click_humanly(page, editor_canvas, behavior)
            await asyncio.sleep(random.uniform(1.0, 2.5))

            log.info(f"    ⌨️ [{persona_name}] Typing document: '{doc_content[:45]}...'")
            
            # 4. Type the LLM content with biometric delays
            await type_canvas_natively(page, doc_content, behavior)
            await asyncio.sleep(random.uniform(2.0, 4.0))
            
            # 5. MACRO-ENTROPY: Text Formatting
            await apply_formatting_entropy(page, persona_name)

            # 6. Rename the document organically
            if random.random() < 0.70:
                doc_title = f"{persona_name} - {doc_content[:15].strip()}..."
                log.info(f"    🏷️ [{persona_name}] Renaming document to: {doc_title}")
                
                # Use a broader locator to catch the title box
                title_box = page.locator(".docs-title-input-label, input[aria-label='Rename']").first
                if await title_box.is_visible(timeout=3000):
                    await click_humanly(page, title_box, behavior)
                    await asyncio.sleep(random.uniform(0.5, 1.5))
                    
                    # Docs usually highlights the whole title when clicked, so typing replaces it
                    for char in doc_title:
                        await page.keyboard.type(char)
                        await asyncio.sleep(random.uniform(0.05, 0.15))
                        
                    await asyncio.sleep(random.uniform(0.5, 1.0))
                    await page.keyboard.press("Enter")

            log.info(f"    ✅ [{persona_name}] Google Docs session complete. Document saved to Drive.")
        else:
            log.warning(f"    ⚠️ [{persona_name}] Google Docs editor canvas did not load in time.")

    except Exception as e:
        log.error(f"    ❌ [{persona_name}] Failed to interact with Google Docs: {e}")