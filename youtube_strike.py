"""
youtube_strike.py — production version

Latest changes:
- Force /videos suffix on direct channel URL nav (avoids /featured page
  where markup is different and Shorts row hijacks the top)
- Updated CHANNEL_VIDEO_SELECTORS to match YouTube's new "lockup" markup
  (yt-lockup-view-model) alongside older variants
- Generic /watch?v= fallback when structured selectors fail
- Multilingual consent banner selectors
- Full diagnostic dump (URL/title/body/screenshot) on total failure
- 20s timeout per structured selector for slow proxies

[v2 fixes — observed live failures]:
- _nav_via_search now ALWAYS navigates to YouTube root before searching
  if we're currently on a /watch or /shorts page.
- Seed warmup is now DIRECT-route-only.
- Wider search-box selector list with longer per-selector timeout.

[v3 — account health detection]:
- When the video grid can't be found, we now check whether the page URL
  contains accounts.google.com or 'uplevelingstep'. If so, the profile
  has been challenged by Google and needs manual reverification — we
  log a clear warning and mark the profile in the DB so the next run
  can skip it until a human fixes it.
"""

import asyncio
import logging
import os
import random
import re
from playwright.async_api import Page

from behavior_engine import (
    move_mouse_humanly, smart_wait, human_scroll,
    human_type, lognormal_delay, click_humanly, idle_reading
)
from llm_helper import generate_contextual_comment

# Used to mark profiles that get hit with a Google account challenge.
# Wrapped in try/except so the module still imports if the DB layer changes.
try:
    from profiles_config import update_profile_status as _update_profile_status
except ImportError:
    _update_profile_status = None

log = logging.getLogger(__name__)

SEARCH_ROUTE_PROBABILITY = 0.75

HOMEPAGE_VIDEO_SELECTORS = [
    "ytd-rich-item-renderer ytd-thumbnail a#thumbnail",
    "yt-lockup-view-model a[href*='/watch?v=']",
    "ytd-rich-item-renderer a#video-title-link",
    "ytd-rich-item-renderer a#thumbnail",
    "a.yt-lockup-metadata-view-model-wiz__title",
    "ytd-rich-grid-media a#thumbnail",
]
CHANNEL_VIDEO_SELECTORS = [
    # New lockup markup (YouTube 2024-2025 rollout)
    "ytd-rich-item-renderer ytd-thumbnail a#thumbnail",
    "yt-lockup-view-model a.yt-lockup-metadata-view-model-wiz__title",
    "yt-lockup-view-model a[href*='/watch?v=']",
    # Older markup (still served to some users in A/B test)
    "ytd-rich-item-renderer a#video-title-link",
    "ytd-grid-video-renderer a#video-title",
    "ytd-rich-grid-media a#video-title-link",
    # Lowest-common-denominator fallbacks
    "a#video-title-link",
    "a#video-title",
]
CHANNEL_RESULT_SELECTORS = [
    "ytd-channel-renderer a#main-link",
    "ytd-channel-renderer a.channel-link",
    "a.channel-link",
    "ytd-channel-renderer #main-link",
]
SEARCH_BOX_SELECTORS = [
    "input#search",
    "input[name='search_query']",
    "ytd-searchbox input",
    "ytd-masthead input#search",
    "#search-input input",
]

# URL fragments that indicate Google has challenged this account / device.
# When any of these appear in page.url after a failed YouTube navigation,
# we know the proxy is fine and YouTube is fine — the *account itself*
# has been flagged and a human needs to log in and reverify.
GOOGLE_CHALLENGE_URL_HINTS = (
    "accounts.google.com",
    "uplevelingstep",
    "signin/v2/challenge",
    "signin/challenge",
    "AccountChooser",
    "ServiceLogin",
)

try:
    from __main__ import shutdown_requested
except ImportError:
    shutdown_requested = False

def _is_shutdown():
    try:
        from __main__ import shutdown_requested
        return shutdown_requested
    except:
        return False

# Use main.py's proxy-retry helper for EVERY YouTube navigation.
try:
    from __main__ import goto_with_proxy_retry as _proxy_goto
except ImportError:
    _proxy_goto = None

async def _safe_goto(page, url, pid=""):
    if _proxy_goto:
        return await _proxy_goto(page, url, pid=pid)
    return await page.goto(url, wait_until="domcontentloaded")


async def _first_visible_list(page, selectors, timeout_each=4000):
    """
    Try each selector in turn. Return the .all() of the first one that
    matches at least one visible element, along with which selector won.
    """
    for sel in selectors:
        try:
            loc = page.locator(sel)
            await loc.first.wait_for(state="visible", timeout=timeout_each)
            items = await loc.all()
            if items:
                return items, sel
        except Exception:
            continue
    return [], None

async def _first_visible_one(page, selectors, timeout_each=4000):
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if await loc.is_visible(timeout=timeout_each):
                return loc
        except Exception:
            continue
    return None

def _extract_handle(channel: str) -> str:
    c = channel.strip()
    m = re.search(r"@([A-Za-z0-9._-]+)", c)
    if m:
        return m.group(1)
    if c.startswith("http"):
        parts = [p for p in c.rstrip("/").split("/") if p and not p.startswith(("videos", "featured", "shorts", "streams", "community"))]
        return parts[-1].lstrip("@") if parts else c
    return c


def _is_google_challenge_url(url: str) -> bool:
    """True if the URL indicates Google has redirected to an account challenge."""
    return any(hint in url for hint in GOOGLE_CHALLENGE_URL_HINTS)


def _mark_needs_reverify(pid: str, evidence_url: str):
    """
    Mark a profile as NEEDS_REVERIFY in the database so future runs can
    skip it until a human manually fixes the Google account challenge.
    Safe to call even if the DB module isn't importable — we just log.
    """
    log.warning(
        f"    🚨 [{pid[:8]}] Account challenged by Google — needs manual reverify. "
        f"Land on: {evidence_url[:120]}"
    )
    if _update_profile_status is not None:
        try:
            _update_profile_status(
                pid,
                status="NEEDS_REVERIFY",
                error_msg=f"Google account challenge: {evidence_url[:200]}"
            )
            log.warning(f"    📝 [{pid[:8]}] Marked NEEDS_REVERIFY in database.")
        except Exception as e:
            log.warning(f"    ⚠️ [{pid[:8]}] Could not mark NEEDS_REVERIFY in DB: {str(e)[:80]}")


async def _diagnostic_snapshot(page, pid: str, reason: str):
    """
    Capture diagnostic info when video discovery fails: URL, title,
    counts of likely-relevant elements, and a full-page screenshot.
    """
    try:
        os.makedirs("debug_shots", exist_ok=True)
        current_url = page.url
        try:
            title = await page.title()
        except Exception:
            title = "<title unavailable>"
        try:
            watch_count = await page.locator("a[href*='/watch?v=']").count()
        except Exception:
            watch_count = -1
        try:
            body_text = (await page.locator("body").inner_text())[:300]
        except Exception:
            body_text = "<body text unavailable>"
        shot_path = f"debug_shots/{pid}_no_grid.png"
        try:
            await page.screenshot(path=shot_path, full_page=True)
        except Exception as ss_err:
            shot_path = f"<screenshot failed: {ss_err}>"

        log.warning(
            f"    🔬 [{pid[:8]}] DIAGNOSTIC ({reason}):\n"
            f"        URL          : {current_url[:120]}\n"
            f"        Title        : '{title[:100]}'\n"
            f"        WatchLinks   : {watch_count}\n"
            f"        Body[:300]   : {body_text!r}\n"
            f"        Screenshot   : {shot_path}"
        )
    except Exception as diag_err:
        log.warning(f"    🔬 [{pid[:8]}] DIAGNOSTIC failed: {diag_err}")


def _is_on_search_capable_page(url: str) -> bool:
    """
    Returns False if the current URL is a /watch or /shorts page (where
    the standard masthead search box may not be reliably interactable).
    """
    if "youtube.com" not in url:
        return False
    if "/watch" in url:
        return False
    if "/shorts/" in url:
        return False
    return True


# ---------- helpers ----------

async def handle_youtube_consent(page, behavior):
    await page.wait_for_timeout(3000)
    selectors = [
        "button[aria-label*='Accept' i]",
        "button[aria-label*='Aceptar' i]",       # Spanish
        "button[aria-label*='Accepter' i]",      # French
        "button[aria-label*='Accetta' i]",       # Italian
        "button[aria-label*='Aceitar' i]",       # Portuguese
        "button[aria-label*='Akzeptieren' i]",   # German
        "button:has-text('Accept all')",
        "button:has-text('Alle akzeptieren')",
        "button:has-text('Aceptar todo')",
        "button:has-text('Tout accepter')",
        "button:has-text('Accetta tutto')",
        "button:has-text('Aceitar tudo')",
        "ytd-button-renderer:has-text('Accept all')",
        ".ytd-consent-bump-v2-renderer button",
    ]
    for sel in selectors:
        try:
            btn = page.locator(sel).first
            if await btn.is_visible(timeout=2000):
                await btn.click(force=True)
                log.info("    🍪 Cleared YouTube consent banner.")
                await page.wait_for_timeout(3000)
                return
        except Exception:
            pass

async def handle_ads(page, behavior, pid):
    try:
        skip_btn = page.locator(".ytp-ad-skip-button, .ytp-ad-skip-button-modern, .ytp-skip-ad-button").first
        if await skip_btn.is_visible(timeout=1500):
            if random.random() < 0.80:
                await asyncio.sleep(random.uniform(2.0, 5.0))
                await click_humanly(page, skip_btn, behavior)
                log.info(f"    ⏭️ [{pid[:8]}] Skipped ad.")
            else:
                log.info(f"    💰 [{pid[:8]}] Watching full ad.")
    except Exception:
        pass

async def clear_search_box(page, selector):
    try:
        el = page.locator(selector).first
        if await el.is_visible(timeout=2000):
            await el.click()
            await page.keyboard.press("Control+a")
            await page.keyboard.press("Backspace")
            await asyncio.sleep(random.uniform(0.3, 0.6))
    except:
        pass

async def force_360p(page, profile_id, behavior):
    try:
        player = page.locator("#movie_player").first
        if await player.is_visible(timeout=3000):
            box = await player.bounding_box()
            if box:
                await move_mouse_humanly(page, box["x"] + box["width"]*0.5, box["y"] + box["height"]*0.5)
            await asyncio.sleep(random.uniform(0.5, 1.0))
            gear = page.locator("button.ytp-settings-button").first
            if await gear.is_visible():
                await click_humanly(page, gear, behavior)
                await asyncio.sleep(random.uniform(0.5, 1.2))
                qm = page.locator("div.ytp-panel-menu >> text='Quality'").first
                if await qm.is_visible():
                    await click_humanly(page, qm, behavior)
                    await asyncio.sleep(random.uniform(0.5, 1.2))
                    r360 = page.locator("div.ytp-menuitem-label >> text='360p'").first
                    if await r360.is_visible():
                        await click_humanly(page, r360, behavior)
                        log.info(f"    ⚙️ [{profile_id[:8]}] Set 360p.")
    except Exception:
        pass


def _force_videos_suffix(channel_url: str) -> str:
    """
    Ensure a channel URL ends with /videos so YouTube doesn't drop us on
    /featured (different markup, Shorts row at top hides the grid).
    """
    url = channel_url.rstrip("/")
    for suffix in ("/videos", "/featured", "/shorts", "/streams", "/community", "/playlists"):
        if url.endswith(suffix):
            return url
    return url + "/videos"


# ---------- channel routing ----------

async def _nav_via_search(page, pid, behavior, channel):
    """
    Search route: type the channel handle into YouTube's search bar,
    find the channel card in results, click it. Then ensure we land
    on /videos (some channel cards drop you on /featured).
    """
    term = _extract_handle(channel)
    log.info(f"    🔍 [{pid[:8]}] Search route: looking up '{term}'...")

    # CRITICAL: always make sure we're on a page with the standard search box.
    # /watch and /shorts pages have different markup that breaks the search
    # selectors. If we just came from seed_warmup, we're definitely on /watch.
    if not _is_on_search_capable_page(page.url):
        log.info(f"    🏠 [{pid[:8]}] Navigating to YouTube homepage for clean search bar...")
        try:
            await _safe_goto(page, "https://www.youtube.com", pid=pid)
            await handle_youtube_consent(page, behavior)
            await smart_wait(page, timeout=5000)
        except Exception as e:
            log.warning(f"    ⚠️ [{pid[:8]}] Homepage nav failed: {str(e)[:60]}")
            return False

    box = await _first_visible_one(page, SEARCH_BOX_SELECTORS, timeout_each=8000)
    if not box:
        log.warning(f"    ⚠️ [{pid[:8]}] Search box not found after homepage nav.")
        return False

    await click_humanly(page, box, behavior)
    await clear_search_box(page, "input#search")
    await human_type(page, "input#search", term, behavior)
    await page.keyboard.press("Enter")
    await smart_wait(page, timeout=8000)

    link = await _first_visible_one(page, CHANNEL_RESULT_SELECTORS, timeout_each=4000)
    if not link:
        log.warning(f"    ⚠️ [{pid[:8]}] Channel not in search results.")
        return False

    await link.scroll_into_view_if_needed()
    await asyncio.sleep(random.uniform(0.5, 1.5))
    await click_humanly(page, link, behavior)
    await smart_wait(page, timeout=5000)

    # We probably landed on /featured — navigate to /videos for the proper grid.
    if channel.startswith("http"):
        videos_url = _force_videos_suffix(channel)
        if videos_url != channel.rstrip("/"):
            current = page.url.rstrip("/")
            if not current.endswith("/videos"):
                log.info(f"    📺 [{pid[:8]}] Navigating to /videos for clean grid...")
                try:
                    await _safe_goto(page, videos_url, pid=pid)
                    await smart_wait(page, timeout=5000)
                except Exception as e:
                    log.info(f"    ℹ️ [{pid[:8]}] /videos nav failed (non-fatal): {str(e)[:60]}")

    return True


async def _nav_direct(page, pid, behavior, channel):
    """
    Direct route: navigate straight to the channel's /videos URL so the
    grid is the primary content (not behind a Shorts row on /featured).
    """
    if channel.startswith("http"):
        target_url = _force_videos_suffix(channel)
        log.info(f"    🌐 [{pid[:8]}] Direct route: {target_url}")
        try:
            await _safe_goto(page, target_url, pid=pid)
            await handle_youtube_consent(page, behavior)
            await smart_wait(page, timeout=5000)
            return True
        except Exception as e:
            log.warning(f"    ⚠️ [{pid[:8]}] Direct nav failed: {str(e)[:80]}")
            return False
    return await _nav_via_search(page, pid, behavior, channel)


async def route_channel_page(page, pid, behavior, channel, pick_random_video=True, prefer_search=True):
    log.info(f"    🛣️ [{pid[:8]}] Channel route ({'search-first' if prefer_search else 'direct-first'})")

    on_channel = False
    if prefer_search:
        on_channel = await _nav_via_search(page, pid, behavior, channel)
        if not on_channel:
            log.info(f"    ↪️ [{pid[:8]}] Falling back to direct URL.")
            on_channel = await _nav_direct(page, pid, behavior, channel)
    else:
        on_channel = await _nav_direct(page, pid, behavior, channel)
        if not on_channel:
            log.info(f"    ↪️ [{pid[:8]}] Falling back to search.")
            on_channel = await _nav_via_search(page, pid, behavior, channel)

    if not on_channel:
        log.warning(f"    ⚠️ [{pid[:8]}] Could not reach channel.")
        # Even before checking selectors, if we got redirected to a Google
        # challenge URL, mark the profile now so we don't waste more time.
        if _is_google_challenge_url(page.url):
            _mark_needs_reverify(pid, page.url)
        return False

    await idle_reading(page, {**behavior, "read_pause_range": (2, 5)})

    # If we somehow ended up off /videos, try clicking the Videos tab
    if "/videos" not in page.url:
        videos_tab = await _first_visible_one(page, [
            "yt-tab-shape:has-text('Videos')",
            "div.yt-tab-shape-wiz__tab:has-text('Videos')",
            "tp-yt-paper-tab:has-text('Videos')",
            "a:has-text('Videos')",
        ], timeout_each=3000)
        if videos_tab:
            log.info(f"    🎞️ [{pid[:8]}] Not on /videos — clicking Videos tab...")
            await click_humanly(page, videos_tab, behavior)
            await page.wait_for_timeout(3000)
        else:
            log.info(f"    ℹ️ [{pid[:8]}] Videos tab not found — proceeding with current view.")

    # ----- VIDEO GRID DISCOVERY -----
    log.info(f"    ⏳ [{pid[:8]}] Waiting for videos (structured selectors)...")
    vids, matching_selector = await _first_visible_list(page, CHANNEL_VIDEO_SELECTORS, timeout_each=20000)

    if vids:
        log.info(f"    ✅ [{pid[:8]}] Found {len(vids)} videos via selector: {matching_selector}")

    # Fallback: hunt for any /watch?v= link
    if not vids:
        log.info(f"    🔄 [{pid[:8]}] Structured selectors empty — trying generic watch-link hunt")
        try:
            await page.locator("a[href*='/watch?v=']").first.wait_for(state="visible", timeout=10000)
            all_links = await page.locator("a[href*='/watch?v=']").all()
            vids = all_links[:20]
            log.info(f"    ✅ [{pid[:8]}] Fallback found {len(vids)} watch links.")
        except Exception as e:
            log.info(f"    ⚠️ [{pid[:8]}] Fallback hunt also empty: {str(e)[:60]}")
            vids = []

    # Total failure — dump diagnostics AND check for account challenge
    if not vids:
        await _diagnostic_snapshot(page, pid, reason="no video grid on channel page")
        # If the failure was because Google challenged the account, mark it
        # in the DB so future runs can skip until a human manually reverifies.
        if _is_google_challenge_url(page.url):
            _mark_needs_reverify(pid, page.url)
        return False

    if pick_random_video and len(vids) > 1:
        pool = vids[:min(8, len(vids))]
        target = random.choice(pool)
        log.info(f"    🎲 [{pid[:8]}] Picked random video (1 of {len(pool)}).")
    else:
        target = vids[0]

    try:
        await target.scroll_into_view_if_needed()
        await asyncio.sleep(random.uniform(0.5, 1.5))
        await click_humanly(page, target, behavior)
    except Exception as e:
        log.warning(f"    ⚠️ [{pid[:8]}] Click failed: {str(e)[:60]}")
        return False
    return True


# ---------- seed warmup ----------

async def seed_warmup(page, pid, behavior):
    """
    Watches 1-2 random homepage videos before navigating to the target.
    Best for DIRECT route — gives the bot some session history before
    hitting the channel URL directly. Skip for SEARCH route since the
    bot will navigate to the homepage anyway as part of searching.
    """
    try:
        num = random.choice([1, 2])
        log.info(f"    🌱 [{pid[:8]}] Seed warmup: {num} video(s)...")
        for i in range(num):
            if _is_shutdown():
                return
            try:
                await _safe_goto(page, "https://www.youtube.com", pid=pid)
            except Exception as e:
                log.warning(f"    ⚠️ [{pid[:8]}] Seed nav failed: {str(e)[:60]}")
                return
            await handle_youtube_consent(page, behavior)
            await smart_wait(page, timeout=5000)

            # If seed warmup landed on a Google challenge, abort immediately
            # and mark the profile — no point watching seed videos when we
            # can already see the account is flagged.
            if _is_google_challenge_url(page.url):
                _mark_needs_reverify(pid, page.url)
                return

            vids, _ = await _first_visible_list(page, HOMEPAGE_VIDEO_SELECTORS, timeout_each=8000)

            if not vids:
                try:
                    await page.locator("a[href*='/watch?v=']").first.wait_for(state="visible", timeout=8000)
                    all_links = await page.locator("a[href*='/watch?v=']").all()
                    vids = all_links[:15]
                    log.info(f"    🔄 [{pid[:8]}] Seed fallback found {len(vids)} links.")
                except Exception:
                    vids = []

            if not vids:
                log.warning(f"    ⚠️ [{pid[:8]}] No homepage videos for seed warmup.")
                return

            seed = random.choice(vids[:10])
            try:
                await seed.scroll_into_view_if_needed()
                await asyncio.sleep(random.uniform(0.5, 1.5))
                await click_humanly(page, seed, behavior)
            except Exception:
                return
            await smart_wait(page, timeout=5000)

            watch = random.uniform(45, 75)
            log.info(f"    🍿 [{pid[:8]}] Seed {i+1}/{num}: {watch:.0f}s")
            await asyncio.sleep(min(12, watch))
            await handle_ads(page, behavior, pid)
            remaining = watch - 12
            while remaining > 0:
                if _is_shutdown():
                    return
                chunk = min(15, remaining)
                await asyncio.sleep(chunk)
                remaining -= chunk
        log.info(f"    ✅ [{pid[:8]}] Seed warmup done.")
    except Exception as e:
        log.warning(f"    ⚠️ [{pid[:8]}] Seed warmup non-fatal: {str(e)[:80]}")


# ---------- core strike ----------

async def execute_target_strike(page, profile, target_keyword, target_channel, warm_day=15):
    pid = profile["id"]
    behavior = profile.get("behavior", {})

    browse_mode = False
    if isinstance(target_keyword, list):
        if "__browse_channel__" in target_keyword:
            browse_mode = True
            keyword = target_channel
            log.info(f"    🔎 [{pid[:8]}] Browse-channel mode")
        else:
            keyword = random.choice(target_keyword)
    else:
        keyword = target_keyword

    prefer_search = random.random() < SEARCH_ROUTE_PROBABILITY
    log.info(f"    🧭 [{pid[:8]}] Route: {'SEARCH' if prefer_search else 'DIRECT'}")

    can_like = warm_day >= 10
    can_sub_comment = warm_day >= 25

    log.info(f"🎯 [{pid[:8]}] STRIKE: '{keyword}' -> {target_channel} (Day {warm_day})")

    try:
        if random.random() < 0.05:
            log.info(f"    🏃 [{pid[:8]}] Bailout — skipping strike.")
            return

        # Seed warmup is most useful for DIRECT route (builds session history
        # before hitting the target channel URL). For SEARCH route, the bot
        # navigates to the homepage anyway as part of searching, so the seed
        # warmup is redundant AND leaves the page on a /watch URL we have
        # to navigate away from. Skip it for search.
        if not prefer_search and random.random() < 0.85:
            await seed_warmup(page, pid, behavior)
        elif prefer_search:
            log.info(f"    ⏭️ [{pid[:8]}] Skipping seed warmup (SEARCH route navigates home anyway).")

        if _is_shutdown():
            return

        # === navigate to a video on the target channel ===
        found = await route_channel_page(page, pid, behavior, target_channel,
                                          pick_random_video=True, prefer_search=prefer_search)
        if not found:
            log.warning(f"    ❌ [{pid[:8]}] Could not reach target video. Aborting strike.")
            return

        await smart_wait(page, timeout=8000)
        await force_360p(page, pid, behavior)
        await page.mouse.click(5, 5)
        await page.evaluate("window.focus()")

        # === read duration FIRST, then compute plan ===
        duration_str = "5:00"
        try:
            dur = page.locator(".ytp-time-duration").first
            if await dur.is_visible(timeout=3000):
                duration_str = await dur.inner_text()
        except Exception:
            pass

        total_seconds = 300
        parts = duration_str.split(":")
        try:
            if len(parts) == 2:
                total_seconds = int(parts[0]) * 60 + int(parts[1])
            elif len(parts) == 3:
                total_seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        except ValueError:
            total_seconds = 300

        r = random.random()
        if r < 0.15:
            watch_pct = random.uniform(0.35, 0.55)
        elif r < 0.60:
            watch_pct = random.uniform(0.60, 0.82)
        elif r < 0.85:
            watch_pct = random.uniform(0.82, 0.95)
        else:
            watch_pct = 1.0

        target_watch_time = int(total_seconds * watch_pct)
        max_time = 600
        if target_watch_time > max_time:
            log.info(f"    ⏳ [{pid[:8]}] Capping {target_watch_time}s -> {max_time}s.")
            target_watch_time = max_time

        log.info(f"    ⏱️ [{pid[:8]}] Plan: {watch_pct*100:.1f}% ({target_watch_time}s of {total_seconds}s)")

        # === deep watch loop ===
        time_watched = 0
        rewind_spiked = False
        ad_check_interval = 45

        while time_watched < target_watch_time:
            if _is_shutdown():
                break
            chunk = random.randint(12, 30)
            await asyncio.sleep(chunk)
            time_watched += chunk

            if time_watched % ad_check_interval < chunk:
                await handle_ads(page, behavior, pid)

            roll = random.random()

            if not rewind_spiked and time_watched > (target_watch_time * 0.4) and random.random() < 0.35:
                log.info(f"    ⏪ [{pid[:8]}] Rewind spike.")
                await page.keyboard.press("j")
                await asyncio.sleep(0.5)
                await page.keyboard.press("j")
                time_watched -= 20
                rewind_spiked = True
                continue

            if roll < 0.04:
                await page.keyboard.press("k")
                await asyncio.sleep(random.uniform(10, 35))
                await page.keyboard.press("k")
            elif roll < 0.15:
                more = page.locator("tp-yt-paper-button#expand").first
                if await more.is_visible(timeout=1000):
                    await click_humanly(page, more, behavior)
            elif roll < 0.25:
                await page.evaluate("window.scrollBy(0, 600)")
                await asyncio.sleep(random.uniform(4, 10))
                await page.evaluate("window.scrollTo(0, 0)")
            elif roll < 0.30:
                await page.keyboard.press("c")
            elif roll < 0.35:
                await move_mouse_humanly(page, random.randint(100, 800), random.randint(100, 500))
            elif roll < 0.40:
                await page.mouse.wheel(0, random.uniform(-100, 100))

        # === social signals (gated) ===
        if can_like and random.random() < 0.15:
            try:
                like = page.locator("button[aria-label*='like this video' i]").first
                if await like.is_visible(timeout=2000):
                    await click_humanly(page, like, behavior)
                    log.info(f"    👍 [{pid[:8]}] Liked.")
                    await asyncio.sleep(random.uniform(1.0, 2.5))
            except Exception:
                pass

        if can_sub_comment and random.random() < 0.05:
            try:
                sub = page.locator("#subscribe-button-shape button").first
                if await sub.is_visible(timeout=2000) and "Subscribed" not in await sub.inner_text():
                    await click_humanly(page, sub, behavior)
                    log.info(f"    🔔 [{pid[:8]}] Subscribed.")
                    await asyncio.sleep(random.uniform(1.5, 3.0))
            except Exception:
                pass

        # === post-watch handoff ===
        if not _is_shutdown():
            try:
                side = await page.locator("ytd-compact-video-renderer a#thumbnail").all()
                if side:
                    pool = side[:min(5, len(side))]
                    weights = [0.35, 0.25, 0.20, 0.12, 0.08][:len(pool)]
                    nxt = random.choices(pool, weights=weights, k=1)[0]
                    await nxt.scroll_into_view_if_needed()
                    await asyncio.sleep(random.uniform(0.5, 1.5))
                    await click_humanly(page, nxt, behavior)
                    handoff = random.uniform(40, 90)
                    log.info(f"    📺 [{pid[:8]}] Handoff: {handoff:.0f}s")
                    watched = 0
                    while watched < handoff:
                        if _is_shutdown():
                            break
                        await asyncio.sleep(min(10, handoff - watched))
                        watched += 10
                        if watched % 30 < 10:
                            await handle_ads(page, behavior, pid)
            except Exception:
                pass

        log.info(f"    🏁 [{pid[:8]}] Strike complete.")

    except Exception as e:
        log.error(f"    ❌ [{pid[:8]}] Strike failed: {e}")