"""
profiles_config.py
------------------
Fetches active profiles dynamically from Supabase and pushes live 
telemetry (status, tasks, errors) back to the Command Center.

[UPGRADED]: 
- Fire-and-Forget Threading to prevent blocking the async event loop
- Exponential Backoff for DB resiliency
- Regional Timezone filtering
- ZOMBIE CLEANUP: Auto-resets profiles stuck in 'in_use'/'checking' from crashed runs
- ERROR RECOVERY: Auto-resets 'error' profiles after cooldown so they can retry
- Proper status lifecycle: google_logged_in ↔ in_use (with recovery paths)

[FIXED]: 
- Uses 'profiles' table (not 'bot_profiles')
- Uses SUPABASE_SERVICE_ROLE_KEY (not SUPABASE_KEY)
- Maps field names: mla_uuid -> profile_id, behavioral_metrics -> behavior, etc.
- Filters by status='google_logged_in' (only runs logged-in profiles)
- truststore SSL fix
"""
import os
import logging
import time
import threading
from pathlib import Path
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

# Fix SSL: Use Windows native certificate store
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

log = logging.getLogger(__name__)

# Table name in Supabase
PROFILES_TABLE = "profiles"

# Cleanup thresholds (in hours)
ZOMBIE_CLEANUP_HOURS = 2      # in_use / checking older than this → reset
ERROR_RECOVERY_HOURS = 6      # error older than this → reset for retry
PROXY_ERROR_RETRY_HOURS = 24  # proxy_error older than this → one retry (proxies sometimes come back)


def get_supabase_client() -> Client:
    url = os.getenv("SUPABASE_URL")
    # Support both key names for flexibility
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise ValueError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in .env")
    return create_client(url, key)


def with_retries(max_retries=3, backoff_factor=1.5):
    """Decorator to retry flaky database network calls automatically."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            attempt = 0
            last_error = None
            while attempt < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    attempt += 1
                    last_error = e
                    wait_time = backoff_factor ** attempt
                    log.debug(f"DB Error in {func.__name__}: {e}. Retrying in {wait_time:.1f}s...")
                    time.sleep(wait_time)
            log.warning(f"⚠️ Supabase operation {func.__name__} failed after {max_retries} attempts. Last error: {last_error}")
            return None
        return wrapper
    return decorator


def _map_profile(p: dict) -> dict:
    """
    Maps the 'profiles' table fields to the format main.py expects.
    
    profiles table          ->  main.py expects
    ─────────────────────────────────────────────
    id                      ->  id (unchanged)
    profile_id              ->  id (persona name like PR-0001)
    mla_uuid                ->  profile_id (MLX browser profile UUID)
    behavioral_metrics      ->  behavior
    demographics            ->  persona (contains interests, etc.)
    location                ->  location (unchanged)
    network                 ->  network (unchanged)
    status                  ->  status (unchanged)
    google_email            ->  google_email (unchanged)
    """
    return {
        # Core identifiers
        "id": p.get("profile_id", p.get("id")),  # main.py uses this for logging
        "db_id": p.get("id"),                      # actual Supabase row ID
        "profile_id": p.get("mla_uuid"),           # MLX browser profile UUID
        
        # Behavior engine config
        "behavior": p.get("behavioral_metrics") or {
            "wpm_range": [45, 75],
            "typo_rate": 0.03,
            "scroll_sessions": [3, 6],
            "scroll_chunk": [150, 400],
            "back_scroll_chance": 0.07,
            "read_pause_range": [3, 8],
            "pre_click_hover_ms": [150, 450],
            "result_position_weights": [0.4, 0.3, 0.2, 0.1],
        },
        
        # Persona info (for LLM search generation, interest-based browsing)
        "persona": {
            "name": p.get("profile_id", "Unknown"),
            "interests": (p.get("demographics") or {}).get("interests", []),
            "location": p.get("location") or {},
        },
        
        # Browser config (defaults since profiles table doesn't have this)
        "browser": {
            "viewport": {"width": 1920, "height": 1080},
            "locale": "en-US",
            "timezone": (p.get("location") or {}).get("timezone", "America/New_York"),
        },
        
        # Pass through useful fields
        "google_email": p.get("google_email"),
        "location": p.get("location") or {},
        "demographics": p.get("demographics") or {},
        "network": p.get("network") or {},
        "status": p.get("status"),
    }


# ==========================================
# STUCK-STATE RECOVERY (runs before every fetch)
# ==========================================

@with_retries(max_retries=2)
def _cleanup_stuck_profiles(supabase: Client):
    """
    Three-stage recovery for profiles stuck in bad states.
    Runs automatically before each fetch so the pipeline self-heals.
    
    Stage 1: ZOMBIES (in_use/checking) — crashed mid-run, reset immediately after 2h
    Stage 2: ERRORS — give them another chance after 6h cooldown
    Stage 3: PROXY ERRORS — proxies sometimes recover; retry after 24h
    """
    now = datetime.now(timezone.utc)
    
    # Stage 1: Zombies from crashed runs
    zombie_cutoff = (now - timedelta(hours=ZOMBIE_CLEANUP_HOURS)).isoformat()
    try:
        result = supabase.table(PROFILES_TABLE)\
            .update({"status": "google_logged_in"})\
            .in_("status", ["in_use", "checking"])\
            .lt("last_used_at", zombie_cutoff)\
            .execute()
        zombie_count = len(result.data) if result.data else 0
        if zombie_count > 0:
            log.info(f"🧟 Zombie cleanup: reset {zombie_count} stuck profiles (in_use/checking > {ZOMBIE_CLEANUP_HOURS}h)")
    except Exception as e:
        log.debug(f"Zombie cleanup skipped: {e}")
    
    # Stage 2: Error recovery — auth cascade victims deserve another shot
    error_cutoff = (now - timedelta(hours=ERROR_RECOVERY_HOURS)).isoformat()
    try:
        result = supabase.table(PROFILES_TABLE)\
            .update({"status": "google_logged_in"})\
            .eq("status", "error")\
            .lt("last_used_at", error_cutoff)\
            .execute()
        error_count = len(result.data) if result.data else 0
        if error_count > 0:
            log.info(f"♻️ Error recovery: reset {error_count} profiles for retry (error > {ERROR_RECOVERY_HOURS}h)")
    except Exception as e:
        log.debug(f"Error recovery skipped: {e}")
    
    # Stage 3: Proxy error retry — proxies sometimes come back online
    proxy_cutoff = (now - timedelta(hours=PROXY_ERROR_RETRY_HOURS)).isoformat()
    try:
        result = supabase.table(PROFILES_TABLE)\
            .update({"status": "google_logged_in"})\
            .eq("status", "proxy_error")\
            .lt("last_used_at", proxy_cutoff)\
            .execute()
        proxy_count = len(result.data) if result.data else 0
        if proxy_count > 0:
            log.info(f"🔌 Proxy retry: reset {proxy_count} profiles (proxy_error > {PROXY_ERROR_RETRY_HOURS}h)")
    except Exception as e:
        log.debug(f"Proxy retry skipped: {e}")


@with_retries(max_retries=3)
def fetch_active_profiles(selected_ids=None, region=None) -> list:
    """
    Fetches profiles from Supabase 'profiles' table.
    
    Runs self-healing cleanup first to recover zombies and timed-out errors,
    then fetches profiles ready to run (status='google_logged_in' by default).
    
    Args:
        selected_ids: Optional list of profile_id names (e.g., ['PR-0001', 'PR-0002'])
        region: Optional region filter (matches against timezone, state, or country)
    """
    supabase = get_supabase_client()
    
    # Run stuck-state cleanup FIRST so we don't miss recovered profiles
    _cleanup_stuck_profiles(supabase)
    
    log.info("📡 Fetching profiles from Supabase...")
    
    query = supabase.table(PROFILES_TABLE).select("*")
    
    if selected_ids:
        # Allow filtering by profile_id names (e.g., PR-0001, PR-0002)
        # When explicit IDs are given, don't filter by status — user knows what they want
        query = query.in_("profile_id", selected_ids)
    else:
        # Only run profiles that are logged into Google
        query = query.eq("status", "google_logged_in")
    
    # Must have MLX profile UUID
    query = query.not_.is_("mla_uuid", "null")
    
    response = query.execute()
    raw_profiles = response.data
    
    if not raw_profiles:
        log.warning("⚠️ No profiles found matching criteria.")
        return []
    
    # Map to the format main.py expects
    profiles = [_map_profile(p) for p in raw_profiles]
    
    # Filter out profiles without MLX UUID
    profiles = [p for p in profiles if p.get("profile_id")]
    
    # When explicit IDs were given, also filter out terminal states
    # (pva_locked profiles shouldn't run even if user names them explicitly)
    if selected_ids:
        runnable = [p for p in profiles if p.get("status") not in ("pva_locked",)]
        skipped = len(profiles) - len(runnable)
        if skipped > 0:
            log.info(f"⏭️ Skipped {skipped} profiles in terminal states (pva_locked).")
        profiles = runnable
    
    # --- REGIONAL FILTERING ---
    if region:
        region_target = region.lower()
        filtered = []
        for p in profiles:
            # Check timezone in browser config
            tz = p.get("browser", {}).get("timezone", "").lower()
            # Also check location data
            loc_state = (p.get("location") or {}).get("state", "").lower()
            loc_country = (p.get("location") or {}).get("country", "").lower()
            
            if region_target in tz or region_target in loc_state or region_target in loc_country:
                filtered.append(p)
        
        profiles = filtered
        log.info(f"🌍 Applied region filter '{region.upper()}'. {len(profiles)} profiles matched.")
    else:
        log.info(f"✅ Loaded {len(profiles)} active profiles from database (Global).")
        
    return profiles


# ==========================================
# FIRE-AND-FORGET TELEMETRY
# ==========================================

def _sync_update_status(profile_name: str, payload: dict):
    """Internal synchronous function to execute the DB update."""
    @with_retries(max_retries=3)
    def _do_update():
        supabase = get_supabase_client()
        supabase.table(PROFILES_TABLE).update(payload).eq("profile_id", profile_name).execute()
    _do_update()


def update_profile_status(profile_id: str, status: str, tasks: list = None, error_msg: str = None):
    """
    Pushes live telemetry to Supabase in a BACKGROUND THREAD.
    
    Status lifecycle:
        google_logged_in → in_use (RUNNING)
        in_use → google_logged_in (SUCCESS)
        in_use → error (FAILED — recoverable after 6h)
        in_use → proxy_error (PROXY_ERROR — recoverable after 24h)
    
    Note: profile_id here is the display name (e.g., PR-0001), 
    which maps to 'profile_id' column in the profiles table.
    """
    # Map main.py status names to our status conventions
    status_map = {
        "RUNNING": "in_use",
        "SUCCESS": "google_logged_in",  # Keep as logged in after successful run
        "FAILED": "error",
        "PROXY_ERROR": "proxy_error",
    }
    
    db_status = status_map.get(status, status.lower())
    
    payload = {
        "status": db_status,
        "last_used_at": datetime.now(timezone.utc).isoformat(),
    }

    thread = threading.Thread(target=_sync_update_status, args=(profile_id, payload), daemon=True)
    thread.start()


def _sync_update_last_run(profile_name: str):
    """Internal synchronous function for timestamp updates."""
    @with_retries(max_retries=3)
    def _do_update():
        supabase = get_supabase_client()
        now_iso = datetime.now(timezone.utc).isoformat()
        supabase.table(PROFILES_TABLE).update({
            "last_used_at": now_iso
        }).eq("profile_id", profile_name).execute()
    _do_update()


def update_last_run(profile_id: str):
    """Updates the last_used_at timestamp in a BACKGROUND THREAD."""
    thread = threading.Thread(target=_sync_update_last_run, args=(profile_id,), daemon=True)
    thread.start()


# ==========================================
# MANUAL RECOVERY UTILITIES (optional helpers)
# ==========================================

def force_reset_all_errors():
    """
    Emergency recovery: reset ALL error/stuck profiles to google_logged_in.
    Call this manually if you want to retry everything at once.
    
    Usage:
        from profiles_config import force_reset_all_errors
        force_reset_all_errors()
    """
    supabase = get_supabase_client()
    result = supabase.table(PROFILES_TABLE)\
        .update({"status": "google_logged_in"})\
        .in_("status", ["in_use", "checking", "error"])\
        .execute()
    count = len(result.data) if result.data else 0
    log.info(f"🔄 Force reset complete: {count} profiles returned to google_logged_in")
    return count


def force_reset_proxy_errors():
    """
    Manually retry ALL proxy_error profiles.
    Only useful after you've verified your proxies are actually working again.
    """
    supabase = get_supabase_client()
    result = supabase.table(PROFILES_TABLE)\
        .update({"status": "google_logged_in"})\
        .eq("status", "proxy_error")\
        .execute()
    count = len(result.data) if result.data else 0
    log.info(f"🔌 Force proxy reset: {count} profiles returned to google_logged_in")
    return count