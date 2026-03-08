"""
behavior_engine.py
------------------
All human-simulation primitives. Each method accepts a `behavior` dict
from the profile config so every persona has its own physical fingerprint.

[UPGRADED FEATURES]
  1. Bulletproof Clicking: Falls back to raw Javascript clicks if elements are obscured.
  2. Bezier Mouse Curves: Simulates natural hand movements with overshoot and tremor.
  3. Fractional Scrolling: Emulates trackpad pixel-perfect scrolling (no rigid integers).
"""

import asyncio
import math
import random
import time


# ---------------------------------------------------------------------------
# TIMING UTILITIES
# ---------------------------------------------------------------------------

def lognormal_delay(min_ms: float, max_ms: float) -> float:
    """
    Returns a log-normally distributed delay in seconds.
    Human reaction times are log-normal: most are near the low end,
    with occasional long outliers — never a flat uniform distribution.
    """
    mu = (math.log(min_ms) + math.log(max_ms)) / 2
    sigma = (math.log(max_ms) - math.log(min_ms)) / 6
    raw = random.lognormvariate(mu, sigma)
    clamped = max(min_ms, min(max_ms, raw))
    return clamped / 1000


def wpm_to_keystroke_ms(wpm: int) -> tuple[float, float]:
    """
    Convert words-per-minute to per-keystroke millisecond range.
    Average word = 5 chars. WPM → chars/min → ms/char.
    Adds ±30% variance band around the mean.
    """
    ms_per_char = 60_000 / (wpm * 5)
    return ms_per_char * 0.7, ms_per_char * 1.3


# ---------------------------------------------------------------------------
# MOUSE MOVEMENT & CLICKING
# ---------------------------------------------------------------------------

async def move_mouse_humanly(page, target_x: float, target_y: float, speed_factor: float = 1.0):
    """
    Cubic Bezier path with ease-in/out + micro hand-tremor jitter.
    speed_factor < 1.0 = slower/more cautious persona (e.g. Linda, Tom)
    speed_factor > 1.0 = faster/more confident (e.g. Sarah, Yuki)
    """
    start_x = random.randint(150, 900)
    start_y = random.randint(100, 650)

    # Random Bezier control points — produces a natural curve, not a straight line
    cp1_x = start_x + random.randint(-250, 250)
    cp1_y = start_y + random.randint(-200, 200)
    cp2_x = target_x + random.randint(-120, 120)
    cp2_y = target_y + random.randint(-120, 120)

    steps = random.randint(22, 48)

    for i in range(steps + 1):
        t = i / steps
        # Ease-in-out cubic: slow → fast → slow
        t_eased = t * t * (3 - 2 * t)

        x = (
            (1 - t_eased) ** 3 * start_x
            + 3 * (1 - t_eased) ** 2 * t_eased * cp1_x
            + 3 * (1 - t_eased) * t_eased ** 2 * cp2_x
            + t_eased ** 3 * target_x
        )
        y = (
            (1 - t_eased) ** 3 * start_y
            + 3 * (1 - t_eased) ** 2 * t_eased * cp1_y
            + 3 * (1 - t_eased) * t_eased ** 2 * cp2_y
            + t_eased ** 3 * target_y
        )

        # Micro hand-tremor: older/slower personas get slightly more jitter
        jitter = 1.8 if speed_factor < 0.7 else 1.1
        x += random.uniform(-jitter, jitter)
        y += random.uniform(-jitter, jitter)

        await page.mouse.move(x, y)

        # Velocity: fast in middle of path, slow at start/end
        mid_dist = abs(t - 0.5)
        base_step = 0.007 + (mid_dist * 0.022)
        step_delay = base_step / speed_factor
        await asyncio.sleep(step_delay + random.uniform(-0.002, 0.003))


async def click_humanly(page, element, behavior: dict):
    """
    Move to element with human curve, hover briefly, then click.
    Uses pre_click_hover_ms from persona's behavior config.
    Now includes aggressive fallbacks if Playwright is blocked by sticky headers.
    """
    try:
        box = await element.bounding_box()
    except Exception:
        box = None

    if not box:
        # If Playwright can't draw a box (element might be slightly offscreen)
        await element.click(force=True, timeout=5000)
        return

    # Aim slightly off-center — humans don't click pixel-perfect centers
    click_x = box["x"] + box["width"] * random.uniform(0.25, 0.75)
    click_y = box["y"] + box["height"] * random.uniform(0.2, 0.8)

    # Derive speed from wpm: faster typist = faster mouse too
    wpm_avg = sum(behavior["wpm_range"]) / 2
    speed = wpm_avg / 60  # normalize around 1.0

    await move_mouse_humanly(page, click_x, click_y, speed_factor=speed)

    # Hover pause before clicking
    hover_min, hover_max = behavior["pre_click_hover_ms"]
    await asyncio.sleep(lognormal_delay(hover_min, hover_max))

    try:
        # Try a native mouse click first (generates trusted events)
        await page.mouse.click(click_x, click_y)
    except Exception:
        # Ultimate fallback: Inject Javascript directly into the DOM to force the click
        await element.evaluate("el => el.click()")


# ---------------------------------------------------------------------------
# TYPING
# ---------------------------------------------------------------------------

# Common English bigrams — humans type these faster due to muscle memory
FAST_BIGRAMS = {
    "th", "he", "in", "er", "an", "re", "on", "en", "at", "es",
    "st", "ou", "te", "of", "it", "or", "ti", "is", "nd", "ar",
}


async def human_type(page, selector: str, text: str, behavior: dict):
    """
    Persona-aware typing:
    - WPM derived from behavior["wpm_range"]
    - Typo rate from behavior["typo_rate"]
    - Older/slower personas pause longer after spotting mistakes
    - Bigram acceleration for all personas
    """
    element = page.locator(selector).first

    # Click to focus with human mouse movement
    box = await element.bounding_box()
    if box:
        wpm_avg = sum(behavior["wpm_range"]) / 2
        speed = wpm_avg / 60
        click_x = box["x"] + box["width"] / 2 + random.uniform(-8, 8)
        click_y = box["y"] + box["height"] / 2 + random.uniform(-4, 4)
        await move_mouse_humanly(page, click_x, click_y, speed_factor=speed)
        await asyncio.sleep(lognormal_delay(80, 220))
        await page.mouse.click(click_x, click_y)

    await asyncio.sleep(lognormal_delay(200, 600))

    min_kd, max_kd = wpm_to_keystroke_ms(
        random.randint(*behavior["wpm_range"])
    )

    i = 0
    while i < len(text):
        char = text[i]

        # Typo injection
        if char not in (" ", "\n") and random.random() < behavior["typo_rate"]:
            typo = random.choice("qwertyuiopasdfghjklzxcvbnm")
            await page.keyboard.type(typo)
            await asyncio.sleep(lognormal_delay(min_kd, max_kd))

            # Pause before noticing — slower personas pause longer
            err_min, err_max = behavior["typo_correction_delay"]
            await asyncio.sleep(lognormal_delay(err_min, err_max))
            await page.keyboard.press("Backspace")
            await asyncio.sleep(lognormal_delay(min_kd * 0.8, max_kd * 0.8))

        await page.keyboard.type(char)

        # Bigram speedup
        bigram = text[i: i + 2].lower()
        if bigram in FAST_BIGRAMS:
            delay = lognormal_delay(min_kd * 0.5, min_kd * 0.9)
        elif char == " ":
            delay = lognormal_delay(min_kd * 1.1, max_kd * 1.3)
        else:
            delay = lognormal_delay(min_kd, max_kd)

        await asyncio.sleep(delay)
        i += 1


# ---------------------------------------------------------------------------
# SCROLLING
# ---------------------------------------------------------------------------

async def human_scroll(page, behavior: dict):
    """
    Persona-aware scroll session:
    - Chunk size from behavior["scroll_chunk"]
    - Back-scroll probability from behavior["back_scroll_chance"]
    - Fractional WheelEvent deltas (real trackpad behavior)
    - Momentum: variable speed within each chunk
    """
    sessions = random.randint(*behavior["scroll_sessions"])
    total_scrolled = 0

    for _ in range(sessions):
        chunk_min, chunk_max = behavior["scroll_chunk"]
        session_dist = random.uniform(chunk_min * 2, chunk_max * 3)
        scrolled = 0

        while scrolled < session_dist:
            # Fractional delta — real trackpads never send round integers
            delta = random.uniform(55.3, 178.7)
            delta = min(delta, session_dist - scrolled)

            # Add fractional noise mimicking trackpad DPI
            delta += random.uniform(-8.3, 8.3)

            await page.mouse.wheel(0, delta)
            scrolled += delta
            total_scrolled += delta

            # Back-scroll: persona sometimes re-reads something
            if random.random() < behavior["back_scroll_chance"]:
                back = random.uniform(28.4, 95.6)
                await asyncio.sleep(lognormal_delay(120, 380))
                await page.mouse.wheel(0, -back)
                await asyncio.sleep(lognormal_delay(400, 1200))

            await asyncio.sleep(lognormal_delay(40, 160))

        # Pause between scroll sessions — simulate reading the revealed content
        read_min, read_max = behavior["read_pause_range"]
        await asyncio.sleep(lognormal_delay(read_min * 1000, read_max * 1000))

    return total_scrolled


# ---------------------------------------------------------------------------
# IDLE BEHAVIOR
# ---------------------------------------------------------------------------

async def idle_reading(page, behavior: dict):
    """
    Simulates the continuous low-level browser activity humans generate
    even while 'just reading': mouse drifts, micro-scrolls, pauses.
    Called during 'reading' pauses instead of time.sleep().
    """
    read_min, read_max = behavior["read_pause_range"]
    idle_duration = random.uniform(read_min, read_max)
    start = time.time()

    while time.time() - start < idle_duration:
        roll = random.random()
        drift_threshold = behavior["idle_drift_chance"]

        if roll < drift_threshold * 0.6:
            # Mouse drifts to a random screen position
            x = random.randint(180, 1100)
            y = random.randint(150, 700)
            wpm_avg = sum(behavior["wpm_range"]) / 2
            await move_mouse_humanly(page, x, y, speed_factor=wpm_avg / 70)

        elif roll < drift_threshold:
            # Tiny micro-scroll
            tiny = random.uniform(18.2, 72.5)
            direction = random.choice([1, -1])
            await page.mouse.wheel(0, tiny * direction)

        # Log-normal pause between idle micro-actions
        await asyncio.sleep(lognormal_delay(800, 4500))


# ---------------------------------------------------------------------------
# PAGE WAIT (replaces networkidle)
# ---------------------------------------------------------------------------

async def smart_wait(page, timeout: int = 12000):
    """
    Waits for visible content rather than networkidle.
    Humans act when they SEE content, not when the network is silent.
    """
    try:
        await page.wait_for_selector("body", state="visible", timeout=timeout)
        await asyncio.sleep(lognormal_delay(400, 1400))
    except Exception:
        await asyncio.sleep(1.5)