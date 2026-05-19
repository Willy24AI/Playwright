"""
youtube_strike.py — production version

[v5.1 — SEARCH BOX LOCATOR FIX]:
- _first_visible_one_with_selector(): keeps which selector matched
- _clear_locator / _type_into_locator: typing helpers that work on a
  locator (not a hardcoded `input#search`)
- _nav_via_search and route_specific_video updated accordingly

[v6 — SIDEBAR-DISCOVERY ROUTE]:
- New route added for --latest-video runs: profile lands on the channel,
  watches an OLDER video briefly, then clicks the target video from the
  sidebar. This is the highest-signal path because it tells YouTube
  "your algorithm already surfaces this video well; do more of it."
- Three-way route split:
    SEARCH_ROUTE_PROBABILITY        = 0.40
    DIRECT_ROUTE_PROBABILITY        = 0.25
    SIDEBAR_DISCOVERY_PROBABILITY   = 0.35
- Sidebar route is only used when video_pick_mode is "newest" or
  "weighted" (we need to know which video to look for in the sidebar).
  For random channel-browse, it falls back to the old 75/25 split.
- New helpers: route_via_sidebar_discovery, _get_channel_newest_id,
  _find_target_in_sidebar.
- If target isn't in the sidebar (~40-60% of the time), bot falls back
  to "back to channel grid, click newest" — same outcome as before,
  just with one extra channel-video watched first.
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

try:
    from profiles_config import update_profile_status as _update_profile_status
except ImportError:
    _update_profile_status = None

log = logging.getLogger(__name__)

# ---- ROUTE PROBABILITIES (must sum to 1.0) ----
SEARCH_ROUTE_PROBABILITY        = 0.40
DIRECT_ROUTE_PROBABILITY        = 0.25
SIDEBAR_DISCOVERY_PROBABILITY   = 0.35
# Sanity check at import-time so a future edit doesn't silently break things.
assert abs((SEARCH_ROUTE_PROBABILITY + DIRECT_ROUTE_PROBABILITY +
            SIDEBAR_DISCOVERY_PROBABILITY) - 1.0) < 0.001

# ---- SOCIAL RATES (no maturation gates) ----
LIKE_RATE = 0.08
SUBSCRIBE_RATE = 0.02
COMMENT_RATE = 0.015

QUOTED_TITLE_PROBABILITY = 0.5
WEIGHTED_NEWEST_WEIGHTS = [0.80, 0.15, 0.05]

# ---- SIDEBAR-DISCOVERY tuning ----
# How long to watch the "decoy" older video before clicking the target
# from the sidebar. Short enough to be a quick browse, long enough to
# register as a real session-start signal.
SIDEBAR_DECOY_WATCH_RANGE = (30, 60)   # seconds
# Which position on the channel grid to pull the decoy from. Avoid
# position 1 because that IS the target in --latest-video mode.
SIDEBAR_DECOY_POSITION_RANGE = (3, 8)
# How many sidebar items to scan for the target before giving up.
SIDEBAR_SCAN_LIMIT = 8

HOMEPAGE_VIDEO_SELECTORS = [
    "ytd-rich-item-renderer ytd-thumbnail a#thumbnail",
    "yt-lockup-view-model a[href*='/watch?v=']",
    "ytd-rich-item-renderer a#video-title-link",
    "ytd-rich-item-renderer a#thumbnail",
    "a.yt-lockup-metadata-view-model-wiz__title",
    "ytd-rich-grid-media a#thumbnail",
]
CHANNEL_VIDEO_SELECTORS = [
    "ytd-rich-item-renderer ytd-thumbnail a#thumbnail",
    "yt-lockup-view-model a.yt-lockup-metadata-view-model-wiz__title",
    "yt-lockup-view-model a[href*='/watch?v=']",
    "ytd-rich-item-renderer a#video-title-link",
    "ytd-grid-video-renderer a#video-title",
    "ytd-rich-grid-media a#video-title-link",
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
    "ytd-searchbox",
    "#search-input",
]
SEARCH_RESULT_VIDEO_SELECTORS = [
    "ytd-video-renderer a#video-title",
    "ytd-video-renderer a#thumbnail",
    "a#video-title[href*='/watch?v=']",
    "a[href*='/watch?v=']",
]
# Selectors for the recommendation sidebar on a /watch page.
SIDEBAR_VIDEO_SELECTORS = [
    "ytd-compact-video-renderer a#thumbnail",
    "ytd-compact-video-renderer a.yt-simple-endpoint",
    "yt-lockup-view-model a[href*='/watch?v=']",
    "#secondary a[href*='/watch?v=']",
]

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

try:
    from __main__ import goto_with_proxy_retry as _proxy_goto
except ImportError:
    _proxy_goto = None

async def _safe_goto(page, url, pid=""):
    if _proxy_goto:
        return await _proxy_goto(page, url, pid=pid)
    return await page.goto(url, wait_until="domcontentloaded")


async def _first_visible_list(page, selectors, timeout_each=4000):
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

async def _first_visible_one_with_selector(page, selectors, timeout_each=4000):
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if await loc.is_visible(timeout=timeout_each):
                return loc, sel
        except Exception:
            continue
    return None, None

async def _first_visible_one(page, selectors, timeout_each=4000):
    loc, _ = await _first_visible_one_with_selector(page, selectors, timeout_each)
    return loc


async def _clear_locator(loc):
    try:
        await loc.click()
        await loc.page.keyboard.press("Control+a")
        await loc.page.keyboard.press("Backspace")
        await asyncio.sleep(random.uniform(0.3, 0.6))
    except Exception:
        pass

async def _type_into_locator(loc, text: str, behavior: dict):
    try:
        await loc.click()
    except Exception:
        pass
    await asyncio.sleep(random.uniform(0.2, 0.5))
    per_char_min = float(behavior.get("type_delay_min", 0.04))
    per_char_max = float(behavior.get("type_delay_max", 0.14))
    for ch in text:
        try:
            await loc.page.keyboard.type(ch)
        except Exception:
            await loc.page.keyboard.press(ch)
        await asyncio.sleep(random.uniform(per_char_min, per_char_max))


def _extract_handle(channel: str) -> str:
    c = channel.strip()
    m = re.search(r"@([A-Za-z0-9._-]+)", c)
    if m:
        return m.group(1)
    if c.startswith("http"):
        parts = [p for p in c.rstrip("/").split("/") if p and not p.startswith(("videos", "featured", "shorts", "streams", "community"))]
        return parts[-1].lstrip("@") if parts else c
    return c


_YT_VIDEO_ID_RE = re.compile(r"(?:v=|/shorts/|youtu\.be/)([A-Za-z0-9_-]{11})")

def _extract_video_id(url: str) -> str:
    if not url:
        return ""
    m = _YT_VIDEO_ID_RE.search(url)
    return m.group(1) if m else ""


def _is_google_challenge_url(url: str) -> bool:
    return any(hint in url for hint in GOOGLE_CHALLENGE_URL_HINTS)


def _mark_needs_reverify(pid: str, evidence_url: str):
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
        "button[aria-label*='Aceptar' i]",
        "button[aria-label*='Accepter' i]",
        "button[aria-label*='Accetta' i]",
        "button[aria-label*='Aceitar' i]",
        "button[aria-label*='Akzeptieren' i]",
        "button[aria-label*='Hyväksy' i]",
        "button[aria-label*='Godkänn' i]",
        "button[aria-label*='Accepter alle' i]",
        "button:has-text('Accept all')",
        "button:has-text('Alle akzeptieren')",
        "button:has-text('Aceptar todo')",
        "button:has-text('Tout accepter')",
        "button:has-text('Accetta tutto')",
        "button:has-text('Aceitar tudo')",
        "button:has-text('Hyväksy kaikki')",
        "button:has-text('Godkänn alla')",
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
    url = channel_url.rstrip("/")
    for suffix in ("/videos", "/featured", "/shorts", "/streams", "/community", "/playlists"):
        if url.endswith(suffix):
            return url
    return url + "/videos"


# ---------- channel routing ----------

async def _nav_via_search(page, pid, behavior, channel):
    term = _extract_handle(channel)
    log.info(f"    🔍 [{pid[:8]}] Search route: looking up '{term}'...")

    if not _is_on_search_capable_page(page.url):
        log.info(f"    🏠 [{pid[:8]}] Navigating to YouTube homepage for clean search bar...")
        try:
            await _safe_goto(page, "https://www.youtube.com", pid=pid)
            await handle_youtube_consent(page, behavior)
            await smart_wait(page, timeout=5000)
        except Exception as e:
            log.warning(f"    ⚠️ [{pid[:8]}] Homepage nav failed: {str(e)[:60]}")
            return False

    box, matched_sel = await _first_visible_one_with_selector(page, SEARCH_BOX_SELECTORS, timeout_each=8000)
    if not box:
        log.warning(f"    ⚠️ [{pid[:8]}] Search box not found after homepage nav.")
        log.warning(f"    🔬 [{pid[:8]}] Current URL: {page.url[:120]}")
        if _is_google_challenge_url(page.url):
            _mark_needs_reverify(pid, page.url)
        return False

    log.info(f"    ⌨️ [{pid[:8]}] Search box found via selector: {matched_sel}")

    await _clear_locator(box)
    await _type_into_locator(box, term, behavior)
    await asyncio.sleep(random.uniform(0.3, 0.7))
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


async def _get_channel_grid_videos(page, pid):
    """
    On a channel /videos page, return the visible video locators and a
    matching list of their video IDs (extracted from href). Used by
    sidebar-discovery to know which is the target and which is a decoy.
    """
    vids, matching_selector = await _first_visible_list(page, CHANNEL_VIDEO_SELECTORS, timeout_each=20000)
    if vids:
        log.info(f"    ✅ [{pid[:8]}] Grid: {len(vids)} videos via {matching_selector}")
    else:
        log.info(f"    🔄 [{pid[:8]}] Grid empty — generic watch-link hunt")
        try:
            await page.locator("a[href*='/watch?v=']").first.wait_for(state="visible", timeout=10000)
            all_links = await page.locator("a[href*='/watch?v=']").all()
            vids = all_links[:20]
            log.info(f"    ✅ [{pid[:8]}] Fallback found {len(vids)} watch links.")
        except Exception:
            vids = []

    ids = []
    for v in vids:
        try:
            href = await v.get_attribute("href")
            ids.append(_extract_video_id(href or ""))
        except Exception:
            ids.append("")
    return vids, ids


async def _get_channel_newest_id(page, pid):
    """Quick read of the newest video's ID on a channel /videos page."""
    _, ids = await _get_channel_grid_videos(page, pid)
    return ids[0] if ids else ""


def _pick_video(vids, mode: str, pid: str) -> object:
    if not vids:
        return None

    if mode == "newest" or len(vids) == 1:
        log.info(f"    📌 [{pid[:8]}] Pick: newest (position 1).")
        return vids[0]

    if mode == "weighted":
        pool = vids[:min(3, len(vids))]
        weights = WEIGHTED_NEWEST_WEIGHTS[:len(pool)]
        chosen = random.choices(pool, weights=weights, k=1)[0]
        idx = pool.index(chosen) + 1
        log.info(f"    🎯 [{pid[:8]}] Pick: weighted-newest (position {idx} of {len(pool)}).")
        return chosen

    pool = vids[:min(8, len(vids))]
    chosen = random.choice(pool)
    log.info(f"    🎲 [{pid[:8]}] Pick: random video (1 of {len(pool)}).")
    return chosen


async def route_channel_page(page, pid, behavior, channel, video_pick_mode: str = "random",
                              prefer_search: bool = True):
    log.info(f"    🛣️ [{pid[:8]}] Channel route ({'search-first' if prefer_search else 'direct-first'}, pick={video_pick_mode})")

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
        if _is_google_challenge_url(page.url):
            _mark_needs_reverify(pid, page.url)
        return False

    await idle_reading(page, {**behavior, "read_pause_range": (2, 5)})

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

    vids, _ = await _get_channel_grid_videos(page, pid)
    if not vids:
        await _diagnostic_snapshot(page, pid, reason="no video grid on channel page")
        if _is_google_challenge_url(page.url):
            _mark_needs_reverify(pid, page.url)
        return False

    target = _pick_video(vids, video_pick_mode, pid)
    if target is None:
        return False

    try:
        await target.scroll_into_view_if_needed()
        await asyncio.sleep(random.uniform(0.5, 1.5))
        await click_humanly(page, target, behavior)
    except Exception as e:
        log.warning(f"    ⚠️ [{pid[:8]}] Click failed: {str(e)[:60]}")
        return False
    return True


# ---------- SIDEBAR DISCOVERY ROUTE (v6) ----------

async def _find_target_in_sidebar(page, pid, target_id: str):
    """
    Scan the watch-page sidebar for a link whose href contains target_id.
    Returns the matching locator or None if not present.
    """
    if not target_id:
        return None

    for sel in SIDEBAR_VIDEO_SELECTORS:
        try:
            await page.locator(sel).first.wait_for(state="visible", timeout=4000)
            items = await page.locator(sel).all()
            for item in items[:SIDEBAR_SCAN_LIMIT]:
                try:
                    href = await item.get_attribute("href")
                    if href and target_id in href:
                        log.info(f"    🎯 [{pid[:8]}] Found target in sidebar.")
                        return item
                except Exception:
                    continue
        except Exception:
            continue

    return None


async def route_via_sidebar_discovery(page, pid, behavior, channel,
                                       video_pick_mode: str = "weighted"):
    """
    High-signal route: land on channel, briefly watch an OLDER video,
    then click the target from the recommendation sidebar. This feeds
    YouTube's "the algorithm surfaces this video well" signal — the
    strongest input for further recommendation expansion.

    If the target isn't in the sidebar (~40-60% of the time), we fall
    back to going back to the channel grid and picking the target
    normally. Result is the same view, just with one extra channel-video
    watched first, which is itself a useful signal.
    """
    log.info(f"    🧲 [{pid[:8]}] Sidebar-discovery route (pick={video_pick_mode})")

    # Step 1: land on channel grid. Use search 50/50 vs direct.
    prefer_search = random.random() < 0.5
    if prefer_search:
        on_channel = await _nav_via_search(page, pid, behavior, channel)
        if not on_channel:
            on_channel = await _nav_direct(page, pid, behavior, channel)
    else:
        on_channel = await _nav_direct(page, pid, behavior, channel)
        if not on_channel:
            on_channel = await _nav_via_search(page, pid, behavior, channel)

    if not on_channel:
        log.warning(f"    ⚠️ [{pid[:8]}] Could not reach channel for sidebar-discovery.")
        if _is_google_challenge_url(page.url):
            _mark_needs_reverify(pid, page.url)
        return False

    await idle_reading(page, {**behavior, "read_pause_range": (2, 5)})

    if "/videos" not in page.url:
        videos_tab = await _first_visible_one(page, [
            "yt-tab-shape:has-text('Videos')",
            "div.yt-tab-shape-wiz__tab:has-text('Videos')",
            "tp-yt-paper-tab:has-text('Videos')",
            "a:has-text('Videos')",
        ], timeout_each=3000)
        if videos_tab:
            await click_humanly(page, videos_tab, behavior)
            await page.wait_for_timeout(3000)

    # Step 2: read the grid. The newest video's ID is our target_id.
    vids, ids = await _get_channel_grid_videos(page, pid)
    if not vids:
        await _diagnostic_snapshot(page, pid, reason="sidebar-discovery: empty grid")
        if _is_google_challenge_url(page.url):
            _mark_needs_reverify(pid, page.url)
        return False

    target_id = ids[0] if ids else ""
    if not target_id:
        log.warning(f"    ⚠️ [{pid[:8]}] Couldn't read target ID from grid — falling back to direct pick.")
        target = _pick_video(vids, video_pick_mode, pid)
        if target is None:
            return False
        await target.scroll_into_view_if_needed()
        await asyncio.sleep(random.uniform(0.5, 1.5))
        await click_humanly(page, target, behavior)
        return True

    log.info(f"    🆔 [{pid[:8]}] Target id from grid: {target_id}")

    # Step 3: pick a DECOY older video (position 3-8). Skip if too few videos.
    if len(vids) < SIDEBAR_DECOY_POSITION_RANGE[0]:
        log.info(f"    ℹ️ [{pid[:8]}] Channel has only {len(vids)} videos — too few for decoy; clicking target directly.")
        target = _pick_video(vids, video_pick_mode, pid)
        if target is None:
            return False
        await target.scroll_into_view_if_needed()
        await asyncio.sleep(random.uniform(0.5, 1.5))
        await click_humanly(page, target, behavior)
        return True

    decoy_max = min(SIDEBAR_DECOY_POSITION_RANGE[1], len(vids))
    decoy_pos = random.randint(SIDEBAR_DECOY_POSITION_RANGE[0], decoy_max) - 1  # 0-indexed
    decoy = vids[decoy_pos]
    log.info(f"    🪤 [{pid[:8]}] Decoy: position {decoy_pos+1} on grid.")

    try:
        await decoy.scroll_into_view_if_needed()
        await asyncio.sleep(random.uniform(0.5, 1.5))
        await click_humanly(page, decoy, behavior)
    except Exception as e:
        log.warning(f"    ⚠️ [{pid[:8]}] Decoy click failed: {str(e)[:60]} — direct pick fallback.")
        # Re-fetch grid in case the page state changed
        vids, _ = await _get_channel_grid_videos(page, pid)
        if not vids:
            return False
        target = _pick_video(vids, video_pick_mode, pid)
        if target is None:
            return False
        await target.scroll_into_view_if_needed()
        await asyncio.sleep(random.uniform(0.5, 1.5))
        await click_humanly(page, target, behavior)
        return True

    # Step 4: briefly watch the decoy
    await smart_wait(page, timeout=8000)
    decoy_watch = random.uniform(*SIDEBAR_DECOY_WATCH_RANGE)
    log.info(f"    🍿 [{pid[:8]}] Decoy watch: {decoy_watch:.0f}s")
    elapsed = 0
    while elapsed < decoy_watch:
        if _is_shutdown():
            break
        chunk = min(10, decoy_watch - elapsed)
        await asyncio.sleep(chunk)
        elapsed += chunk
        # Light ad handling so we don't get stuck on a 30s ad
        if elapsed % 20 < chunk:
            await handle_ads(page, behavior, pid)

    if _is_shutdown():
        return False

    # Step 5: look for the target in the sidebar
    log.info(f"    🔎 [{pid[:8]}] Scanning sidebar for target {target_id}...")
    sidebar_target = await _find_target_in_sidebar(page, pid, target_id)

    if sidebar_target:
        # HIGH-SIGNAL PATH: target was in the sidebar, click it.
        try:
            await sidebar_target.scroll_into_view_if_needed()
            await asyncio.sleep(random.uniform(0.5, 1.5))
            await click_humanly(page, sidebar_target, behavior)
            await smart_wait(page, timeout=5000)
            log.info(f"    ✨ [{pid[:8]}] Sidebar-discovery: HIGH-SIGNAL click on target.")
            return True
        except Exception as e:
            log.warning(f"    ⚠️ [{pid[:8]}] Sidebar click failed: {str(e)[:60]}")

    # Step 6: fallback — go back to channel and click the target
    log.info(f"    ↩️ [{pid[:8]}] Target not in sidebar — back to channel grid for direct pick.")
    try:
        await _safe_goto(page, _force_videos_suffix(channel) if channel.startswith("http") else f"https://www.youtube.com/@{_extract_handle(channel)}/videos", pid=pid)
        await smart_wait(page, timeout=5000)
    except Exception as e:
        log.warning(f"    ⚠️ [{pid[:8]}] Back-to-channel nav failed: {str(e)[:60]}")
        return False

    vids, _ = await _get_channel_grid_videos(page, pid)
    if not vids:
        return False

    target = _pick_video(vids, video_pick_mode, pid)
    if target is None:
        return False
    try:
        await target.scroll_into_view_if_needed()
        await asyncio.sleep(random.uniform(0.5, 1.5))
        await click_humanly(page, target, behavior)
    except Exception as e:
        log.warning(f"    ⚠️ [{pid[:8]}] Fallback target click failed: {str(e)[:60]}")
        return False
    return True


# ---------- TARGETED-VIDEO routing (search by title) ----------

async def route_specific_video(page, pid, behavior, video_url: str, video_title: str) -> bool:
    target_id = _extract_video_id(video_url)
    if not target_id:
        log.warning(f"    ⚠️ [{pid[:8]}] Could not parse video ID from URL: {video_url}")
        return False

    log.info(f"    🎯 [{pid[:8]}] Targeted video: id={target_id}, title='{video_title[:60]}...'")

    use_quotes = random.random() < QUOTED_TITLE_PROBABILITY
    query = f'"{video_title}"' if use_quotes else video_title
    log.info(f"    ⌨️ [{pid[:8]}] Search query: {'QUOTED' if use_quotes else 'PLAIN'}")

    if not _is_on_search_capable_page(page.url):
        log.info(f"    🏠 [{pid[:8]}] Navigating to YouTube homepage for clean search bar...")
        try:
            await _safe_goto(page, "https://www.youtube.com", pid=pid)
            await handle_youtube_consent(page, behavior)
            await smart_wait(page, timeout=5000)
        except Exception as e:
            log.warning(f"    ⚠️ [{pid[:8]}] Homepage nav failed: {str(e)[:60]}")
            return await _fallback_direct_watch(page, pid, behavior, video_url)

    box, matched_sel = await _first_visible_one_with_selector(page, SEARCH_BOX_SELECTORS, timeout_each=8000)
    if not box:
        log.warning(f"    ⚠️ [{pid[:8]}] Search box not found.")
        if _is_google_challenge_url(page.url):
            _mark_needs_reverify(pid, page.url)
        return await _fallback_direct_watch(page, pid, behavior, video_url)

    log.info(f"    ⌨️ [{pid[:8]}] Search box found via selector: {matched_sel}")

    try:
        await _clear_locator(box)
        await _type_into_locator(box, query, behavior)
        await asyncio.sleep(random.uniform(0.3, 0.7))
        await page.keyboard.press("Enter")
        await smart_wait(page, timeout=8000)
    except Exception as e:
        log.warning(f"    ⚠️ [{pid[:8]}] Search typing failed: {str(e)[:60]}")
        return await _fallback_direct_watch(page, pid, behavior, video_url)

    log.info(f"    🔎 [{pid[:8]}] Scanning results for target ID {target_id}...")
    matching_link = None

    for sel in SEARCH_RESULT_VIDEO_SELECTORS:
        try:
            await page.locator(sel).first.wait_for(state="visible", timeout=6000)
            links = await page.locator(sel).all()
            if not links:
                continue
            for link in links[:15]:
                try:
                    href = await link.get_attribute("href")
                    if not href:
                        continue
                    if target_id in href:
                        matching_link = link
                        log.info(f"    🎯 [{pid[:8]}] Found target in search results.")
                        break
                except Exception:
                    continue
            if matching_link:
                break
        except Exception:
            continue

    if matching_link:
        try:
            await matching_link.scroll_into_view_if_needed()
            await asyncio.sleep(random.uniform(0.5, 1.5))
            await click_humanly(page, matching_link, behavior)
            await smart_wait(page, timeout=5000)
            return True
        except Exception as e:
            log.warning(f"    ⚠️ [{pid[:8]}] Click on matched result failed: {str(e)[:60]}")

    log.info(f"    ↪️ [{pid[:8]}] Target not found in search results — falling back to direct watch URL.")
    return await _fallback_direct_watch(page, pid, behavior, video_url)


async def _fallback_direct_watch(page, pid, behavior, video_url: str) -> bool:
    log.info(f"    🌐 [{pid[:8]}] Direct watch nav: {video_url}")
    try:
        await _safe_goto(page, video_url, pid=pid)
        await handle_youtube_consent(page, behavior)
        await smart_wait(page, timeout=5000)
        if _is_google_challenge_url(page.url):
            _mark_needs_reverify(pid, page.url)
            return False
        return True
    except Exception as e:
        log.warning(f"    ⚠️ [{pid[:8]}] Direct watch nav failed: {str(e)[:80]}")
        return False


# ---------- seed warmup ----------

async def seed_warmup(page, pid, behavior):
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

            if _is_google_challenge_url(page.url):
                _mark_needs_reverify(pid, page.url)
                return

            vids, _ = await _first_visible_list(page, HOMEPAGE_VIDEO_SELECTORS, timeout_each=8000)
            if not vids:
                try:
                    await page.locator("a[href*='/watch?v=']").first.wait_for(state="visible", timeout=8000)
                    all_links = await page.locator("a[href*='/watch?v=']").all()
                    vids = all_links[:15]
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


# ---------- route chooser ----------

def _choose_strike_route(video_pick_mode: str):
    """
    Decide which route to use for this profile's strike.
    Sidebar-discovery requires knowing the target (newest/weighted modes).
    For random channel-browse, we still split 75/25 search/direct.
    Returns one of: "search", "direct", "sidebar".
    """
    if video_pick_mode == "random":
        # Old behavior — sidebar doesn't apply (no specific target)
        return "search" if random.random() < 0.75 else "direct"

    r = random.random()
    if r < SEARCH_ROUTE_PROBABILITY:
        return "search"
    if r < SEARCH_ROUTE_PROBABILITY + DIRECT_ROUTE_PROBABILITY:
        return "direct"
    return "sidebar"


# ---------- core strike ----------

async def execute_target_strike(page, profile, target_keyword, target_channel, warm_day=15,
                                target_video_url: str = None, target_video_title: str = None,
                                video_pick_mode: str = "random"):
    pid = profile["id"]
    behavior = profile.get("behavior", {})

    targeted_video_mode = bool(target_video_url and target_video_title)

    if targeted_video_mode:
        log.info(f"    🎯 [{pid[:8]}] Targeted-video mode")
        keyword = target_video_title
    else:
        if isinstance(target_keyword, list):
            if "__browse_channel__" in target_keyword:
                keyword = target_channel
                log.info(f"    🔎 [{pid[:8]}] Channel mode (pick={video_pick_mode})")
            else:
                keyword = random.choice(target_keyword)
        else:
            keyword = target_keyword

    if targeted_video_mode:
        chosen_route = "targeted"
    else:
        chosen_route = _choose_strike_route(video_pick_mode)
    log.info(f"    🧭 [{pid[:8]}] Route: {chosen_route.upper()}")

    log.info(f"🎯 [{pid[:8]}] STRIKE: '{keyword}' (Day {warm_day})")

    try:
        if random.random() < 0.05:
            log.info(f"    🏃 [{pid[:8]}] Bailout — skipping strike.")
            return

        # Seed warmup logic — only for direct, non-targeted, non-sidebar
        # paths (sidebar route already includes a "decoy" watch).
        if chosen_route == "direct" and not targeted_video_mode and random.random() < 0.85:
            await seed_warmup(page, pid, behavior)
        elif chosen_route == "search" and not targeted_video_mode:
            log.info(f"    ⏭️ [{pid[:8]}] Skipping seed warmup (SEARCH route navigates home anyway).")
        elif chosen_route == "sidebar":
            log.info(f"    ⏭️ [{pid[:8]}] Skipping seed warmup (sidebar route watches a decoy on channel).")
        elif targeted_video_mode:
            log.info(f"    ⏭️ [{pid[:8]}] Skipping seed warmup (targeted-video search navigates home).")

        if _is_shutdown():
            return

        # === route to target ===
        if targeted_video_mode:
            found = await route_specific_video(page, pid, behavior,
                                                target_video_url, target_video_title)
        elif chosen_route == "sidebar":
            found = await route_via_sidebar_discovery(page, pid, behavior, target_channel,
                                                      video_pick_mode=video_pick_mode)
        else:
            prefer_search = (chosen_route == "search")
            found = await route_channel_page(page, pid, behavior, target_channel,
                                              video_pick_mode=video_pick_mode,
                                              prefer_search=prefer_search)
        if not found:
            log.warning(f"    ❌ [{pid[:8]}] Could not reach target video. Aborting strike.")
            return

        await smart_wait(page, timeout=8000)
        await force_360p(page, pid, behavior)
        await page.mouse.click(5, 5)
        await page.evaluate("window.focus()")

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

        # === social signals ===

        if random.random() < LIKE_RATE:
            try:
                like = page.locator("button[aria-label*='like this video' i]").first
                if await like.is_visible(timeout=2000):
                    await click_humanly(page, like, behavior)
                    log.info(f"    👍 [{pid[:8]}] Liked.")
                    await asyncio.sleep(random.uniform(1.0, 2.5))
            except Exception:
                pass

        if random.random() < SUBSCRIBE_RATE:
            try:
                sub = page.locator("#subscribe-button-shape button").first
                if await sub.is_visible(timeout=2000) and "Subscribed" not in await sub.inner_text():
                    await click_humanly(page, sub, behavior)
                    log.info(f"    🔔 [{pid[:8]}] Subscribed.")
                    await asyncio.sleep(random.uniform(1.5, 3.0))
            except Exception:
                pass

        if random.random() < COMMENT_RATE:
            try:
                log.info(f"    🧠 [{pid[:8]}] Generating contextual comment...")
                title_el = page.locator("h1.ytd-watch-metadata").first
                video_title_text = (
                    await title_el.inner_text()
                    if await title_el.is_visible(timeout=2000) else "Video"
                )
                desc_el = page.locator("ytd-text-inline-expander#description-inline-expander").first
                desc_text = (
                    await desc_el.inner_text()
                    if await desc_el.is_visible(timeout=2000) else ""
                )
                desc_text = desc_text[:500]

                await page.evaluate("window.scrollBy(0, 600)")
                await asyncio.sleep(random.uniform(2.0, 4.0))

                comment_box = page.locator("#simplebox-placeholder").first
                if await comment_box.is_visible(timeout=3000):
                    await click_humanly(page, comment_box, behavior)
                    await asyncio.sleep(random.uniform(1.0, 2.0))

                    comment_text = await generate_contextual_comment(
                        profile, video_title_text, desc_text
                    )
                    if comment_text:
                        comment_input = page.locator("#contenteditable-root").first
                        if await comment_input.is_visible(timeout=2000):
                            await _type_into_locator(comment_input, comment_text, behavior)
                            await asyncio.sleep(random.uniform(1.0, 2.0))
                            submit_btn = page.locator("#submit-button").first
                            if await submit_btn.is_visible(timeout=2000):
                                await click_humanly(page, submit_btn, behavior)
                                log.info(f"    💬 [{pid[:8]}] Left comment: '{comment_text[:60]}'")
                    else:
                        log.info(f"    ⚠️ [{pid[:8]}] LLM returned empty comment, skipping.")

                await page.evaluate("window.scrollTo(0, 0)")
            except Exception as e:
                log.debug(f"    Comment failed: {e}")

        # === post-watch handoff (sidebar) ===
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