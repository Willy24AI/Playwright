"""
behavior_engine.py
------------------
Master suite of human-simulation primitives. 
Uses log-normal distributions, Fitts's Law, and physics-based movement 
to bypass advanced behavioral telemetry.
"""

import asyncio
import math
import random
import time

# Global state tracker to prevent cursor teleportation between function calls
CURSOR_STATE = {"x": 0, "y": 0, "initialized": False}

# ---------------------------------------------------------------------------
# TIMING & PHYSICS UTILITIES
# ---------------------------------------------------------------------------

def lognormal_delay(min_ms: float, max_ms: float) -> float:
    """
    Returns a delay in seconds using a log-normal distribution.
    Humans rarely act at a fixed 'average' speed; most actions are fast, 
    with a long tail of occasional slow outliers.
    """
    mu = (math.log(min_ms) + math.log(max_ms)) / 2
    sigma = (math.log(max_ms) - math.log(min_ms)) / 6
    raw = random.lognormvariate(mu, sigma)
    clamped = max(min_ms, min(max_ms, raw))
    return clamped / 1000

def wpm_to_keystroke_ms(wpm: int) -> tuple[float, float]:
    """Converts WPM to millisecond ranges for typing speed."""
    ms_per_char = 60_000 / (wpm * 5)
    return ms_per_char * 0.7, ms_per_char * 1.3

# ---------------------------------------------------------------------------
# MOUSE MOVEMENT & CLICKING
# ---------------------------------------------------------------------------

async def move_mouse_humanly(page, target_x: float, target_y: float, speed_factor: float = 1.0):
    """
    Simulates natural hand movement using Fitts's Law and proportional Bezier curves.
    Features: State tracking, Ease-out deceleration, and micro-tremors.
    """
    global CURSOR_STATE
    
    # 1. Statefulness: Start from last known position
    if not CURSOR_STATE["initialized"]:
        start_x, start_y = random.randint(100, 600), random.randint(100, 600)
        await page.mouse.move(start_x, start_y) # Instantly place it once for the session
        CURSOR_STATE["initialized"] = True
    else:
        start_x, start_y = CURSOR_STATE["x"], CURSOR_STATE["y"]

    # 12% chance to overshoot (miss the target slightly and correct)
    if random.random() < 0.12:
        target_x += random.randint(-15, 15)
        target_y += random.randint(-15, 15)

    # 2. Fitts's Law: Calculate Distance
    distance = math.hypot(target_x - start_x, target_y - start_y)
    
    # Ignore micro-movements to avoid division by zero or jitter loops
    if distance < 2: 
        await page.mouse.move(target_x, target_y)
        CURSOR_STATE["x"], CURSOR_STATE["y"] = target_x, target_y
        return

    # Base steps on distance (~1 step per 15 pixels, clamped for safety)
    steps = max(15, min(100, int(distance / 15))) 

    # 3. Proportional Bezier Curves: Human hands naturally arc outwards.
    angle = math.atan2(target_y - start_y, target_x - start_x)
    
    # The magnitude of the arc is proportional to the distance (10-20% of distance)
    arc_magnitude = distance * random.uniform(0.1, 0.2)
    
    # Randomly choose if the arc goes "above" or "below" the straight line
    direction = random.choice([-1, 1]) 
    perp_angle = angle + (math.pi / 2 * direction)

    # Control points placed at 30% and 70% of the journey, pushed outward perpendicularly
    cp1_x = start_x + (distance * 0.3) * math.cos(angle) + arc_magnitude * math.cos(perp_angle)
    cp1_y = start_y + (distance * 0.3) * math.sin(angle) + arc_magnitude * math.sin(perp_angle)
    
    cp2_x = start_x + (distance * 0.7) * math.cos(angle) + arc_magnitude * math.cos(perp_angle)
    cp2_y = start_y + (distance * 0.7) * math.sin(angle) + arc_magnitude * math.sin(perp_angle)

    for i in range(steps + 1):
        t = i / steps
        # Simple ease-out (humans decelerate as they approach the target)
        t_eased = 1 - (1 - t) * (1 - t) 
        
        x = ((1-t_eased)**3 * start_x + 3*(1-t_eased)**2 * t_eased * cp1_x + 
             3*(1-t_eased)*t_eased**2 * cp2_x + t_eased**3 * target_x)
        y = ((1-t_eased)**3 * start_y + 3*(1-t_eased)**2 * t_eased * cp1_y + 
             3*(1-t_eased)*t_eased**2 * cp2_y + t_eased**3 * target_y)

        # Micro-tremor (Simulates physical muscle jitter)
        jitter = 1.5 if speed_factor < 0.8 else 0.9
        await page.mouse.move(x + random.uniform(-jitter, jitter), y + random.uniform(-jitter, jitter))

        # Consistent polling rate pause (~120Hz monitor refresh rate equivalent)
        await asyncio.sleep(0.008 / speed_factor)

    # Update global state tracker
    CURSOR_STATE["x"], CURSOR_STATE["y"] = target_x, target_y

async def click_humanly(page, element, behavior: dict):
    """Clicks an element by moving the mouse to a random point within its bounds."""
    try:
        box = await element.bounding_box()
        if not box:
            await element.click(force=True)
            return

        # Target a random spot inside the button, not the exact geometric center
        click_x = box["x"] + box["width"] * random.uniform(0.15, 0.85)
        click_y = box["y"] + box["height"] * random.uniform(0.15, 0.85)

        wpm_avg = sum(behavior.get("wpm_range", [50, 80])) / 2
        await move_mouse_humanly(page, click_x, click_y, speed_factor=wpm_avg / 65)
        
        # Hover pause: simulate the 'thought' before clicking
        h_min, h_max = behavior.get("pre_click_hover_ms", [150, 450])
        await asyncio.sleep(lognormal_delay(h_min, h_max))
        
        await page.mouse.click(click_x, click_y)
    except Exception:
        # Fallback to JS click if the element is covered by a popup/overlay
        await element.evaluate("el => el.click()")

# ---------------------------------------------------------------------------
# TYPING (WITH DWELL TIME, TYPOS & BIGRAMS)
# ---------------------------------------------------------------------------

# Common bigrams humans type faster due to muscle memory
FAST_BIGRAMS = {"th", "he", "in", "er", "an", "re", "on", "at", "st", "en", "ed"}

async def human_type(page, selector: str, text: str, behavior: dict):
    """
    Types text with persona-specific speed, realistic typos, 
    muscle-memory bigram acceleration, and simulated physical key dwell times.
    """
    element = page.locator(selector).first
    await element.focus()
    await asyncio.sleep(lognormal_delay(250, 600))

    min_kd, max_kd = wpm_to_keystroke_ms(random.randint(*behavior.get("wpm_range", [40, 80])))

    for i, char in enumerate(text):
        # Typo logic: types a nearby key, pauses, backspaces, and corrects
        if random.random() < behavior.get("typo_rate", 0.03) and char.isalpha():
            typo_keys = "asdfghjklqwertyuiop"
            # Adding dwell time to the typo keypress
            await page.keyboard.type(random.choice(typo_keys), delay=random.uniform(70, 120))
            await asyncio.sleep(lognormal_delay(150, 400)) # Pause to 'realize' mistake
            await page.keyboard.press("Backspace", delay=random.uniform(50, 100))
            await asyncio.sleep(lognormal_delay(100, 300))

        # Core typing execution WITH dwell time (the time the physical key is pressed down)
        await page.keyboard.type(char, delay=random.uniform(70, 120))

        # Flight time simulation (time between releasing one key and pressing the next)
        # Bigram speedup: if current + next char are common, type faster
        if i < len(text) - 1 and text[i:i+2].lower() in FAST_BIGRAMS:
            delay = lognormal_delay(min_kd * 0.4, min_kd * 0.8)
        elif char == " ":
            delay = lognormal_delay(min_kd * 1.2, max_kd * 1.5) # Longer pause on spaces
        else:
            delay = lognormal_delay(min_kd, max_kd)

        await asyncio.sleep(delay)

# ---------------------------------------------------------------------------
# SCROLLING (TRACKPAD EMULATION)
# ---------------------------------------------------------------------------

async def human_scroll(page, behavior: dict):
    """
    Simulates high-precision trackpad scrolling using fractional pixel deltas.
    Includes momentum and 're-reading' back-scrolls.
    """
    sessions = random.randint(*behavior.get("scroll_sessions", [3, 6]))
    for _ in range(sessions):
        chunk_min, chunk_max = behavior.get("scroll_chunk", [150, 400])
        dist = random.uniform(chunk_min, chunk_max * 2.5)
        
        scrolled = 0
        while scrolled < dist:
            # Fractional deltas are a high-trust hardware signal
            step = random.uniform(32.4, 118.9)
            await page.mouse.wheel(0, step)
            scrolled += step
            
            # 7% chance to scroll back up slightly (mimicking a human re-reading a line)
            if random.random() < behavior.get("back_scroll_chance", 0.07):
                await asyncio.sleep(0.4)
                await page.mouse.wheel(0, -random.uniform(40, 90))
                await asyncio.sleep(lognormal_delay(500, 1500))
            
            await asyncio.sleep(lognormal_delay(60, 180))
        
        # Pause to read the newly revealed content
        read_min, read_max = behavior.get("read_pause_range", [2, 6])
        await asyncio.sleep(lognormal_delay(read_min * 1000, read_max * 1000))

# ---------------------------------------------------------------------------
# IDLE & WAIT LOGIC
# ---------------------------------------------------------------------------

async def smart_wait(page, timeout: int = 15000):
    """Waits for the DOM to be visible and stable before proceeding."""
    try:
        await page.wait_for_selector("body", state="visible", timeout=timeout)
        await asyncio.sleep(lognormal_delay(600, 2000))
    except Exception:
        pass

async def idle_reading(page, behavior: dict):
    """
    Simulates a human reading a page: mouse drifts aimlessly 
    and tiny micro-scolls occur periodically.
    """
    p_min, p_max = behavior.get("read_pause_range", [5, 15])
    duration = random.uniform(p_min, p_max)
    start_time = time.time()
    
    while time.time() - start_time < duration:
        roll = random.random()
        if roll < 0.25:
            # Mouse drift
            await move_mouse_humanly(page, random.randint(100, 1000), random.randint(100, 700), 0.7)
        elif roll < 0.40:
            # Tiny twitch scroll (fidgeting)
            await page.mouse.wheel(0, random.uniform(-40, 40))
        
        await asyncio.sleep(random.uniform(2.5, 6.0))