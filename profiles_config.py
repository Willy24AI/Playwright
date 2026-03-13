"""
profiles_config.py
------------------
Fetches active profiles dynamically from Supabase and pushes live 
telemetry (status, tasks, errors) back to the Command Center.

[UPGRADED]: Uses Fire-and-Forget Threading to prevent blocking the async event loop.
Includes Exponential Backoff for DB resiliency and Regional Timezone filtering.
Ready to scale to 10,000+ profiles.
"""
import os
import logging
import time
import threading
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv(dotenv_path=Path(__file__).parent / ".env")
log = logging.getLogger(__name__)

def get_supabase_client() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY in .env")
    return create_client(url, key)

def with_retries(max_retries=3, backoff_factor=1.5):
    """Decorator to retry flaky database network calls automatically."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            attempt = 0
            while attempt < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    attempt += 1
                    wait_time = backoff_factor ** attempt
                    log.debug(f"DB Error in {func.__name__}: {e}. Retrying in {wait_time:.1f}s...")
                    time.sleep(wait_time)
            log.warning(f"⚠️ Supabase operation {func.__name__} failed after {max_retries} attempts.")
            return None
        return wrapper
    return decorator

@with_retries(max_retries=3)
def fetch_active_profiles(selected_ids=None, region=None) -> list:
    """
    Fetches profiles from the database. 
    Filters by specific IDs or matches Regional Timezones.
    """
    supabase = get_supabase_client()
    log.info("📡 Fetching profiles from Supabase...")
    
    query = supabase.table("bot_profiles").select("*")
    
    if selected_ids:
        query = query.in_("id", selected_ids)
    else:
        query = query.eq("is_active", True)
        
    response = query.execute()
    profiles = response.data
    
    # Ensure the 'profile_id' key maps correctly for legacy code compatibility
    for p in profiles:
        if "mlx_profile_id" in p:
            p["profile_id"] = p.get("mlx_profile_id")
            
    # --- REGIONAL TIMEZONE FILTERING ---
    if region:
        region_target = region.lower()
        filtered_profiles = []
        for p in profiles:
            tz = p.get("browser", {}).get("timezone", "").lower()
            if region_target in tz:
                filtered_profiles.append(p)
        
        profiles = filtered_profiles
        log.info(f"🌍 Applied region filter '{region.upper()}'. {len(profiles)} profiles matched.")
    else:
        log.info(f"✅ Loaded {len(profiles)} active profiles from database (Global).")
        
    return profiles

# ==========================================
# FIRE-AND-FORGET TELEMETRY
# ==========================================

def _sync_update_status(profile_id: str, payload: dict):
    """Internal synchronous function to execute the DB update."""
    @with_retries(max_retries=3)
    def _do_update():
        supabase = get_supabase_client()
        supabase.table("bot_profiles").update(payload).eq("id", profile_id).execute()
    _do_update()

def update_profile_status(profile_id: str, status: str, tasks: list = None, error_msg: str = None):
    """
    Pushes live telemetry to Supabase in a BACKGROUND THREAD.
    This ensures Playwright's async event loop is never blocked by HTTP latency.
    """
    payload = {"status": status}
    
    if tasks is not None:
        payload["last_tasks"] = tasks
        
    if error_msg:
        payload["error_log"] = error_msg
    elif status == "SUCCESS":
        payload["error_log"] = None

    # Spin up a daemon thread so the main program doesn't wait for it to finish
    thread = threading.Thread(target=_sync_update_status, args=(profile_id, payload), daemon=True)
    thread.start()

def _sync_update_last_run(profile_id: str):
    """Internal synchronous function for timestamp updates."""
    @with_retries(max_retries=3)
    def _do_update():
        supabase = get_supabase_client()
        now_iso = datetime.now(timezone.utc).isoformat()
        supabase.table("bot_profiles").update({"last_run": now_iso}).eq("id", profile_id).execute()
    _do_update()

def update_last_run(profile_id: str):
    """Updates the last_run timestamp in a BACKGROUND THREAD."""
    thread = threading.Thread(target=_sync_update_last_run, args=(profile_id,), daemon=True)
    thread.start()