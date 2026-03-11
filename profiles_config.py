"""
profiles_config.py
------------------
Fetches active profiles dynamically from Supabase and pushes live 
telemetry (status, tasks, errors) back to the Command Center.
Ready to scale to 10,000+ profiles.
"""
import os
import logging
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

def fetch_active_profiles(selected_ids=None) -> list:
    """
    Fetches profiles from the database. 
    If selected_ids is provided, it only fetches those specific profiles.
    Otherwise, it fetches all profiles where is_active = True.
    """
    supabase = get_supabase_client()
    log.info("📡 Fetching profiles from Supabase...")
    
    try:
        query = supabase.table("bot_profiles").select("*")
        
        if selected_ids:
            # If user passed --profile sarah_nyc
            query = query.in_("id", selected_ids)
        else:
            # Default: run all active profiles
            query = query.eq("is_active", True)
            
        response = query.execute()
        profiles = response.data
        
        # Ensure the 'profile_id' key maps correctly for legacy code compatibility
        # We copy it rather than 'pop' to prevent KeyErrors in main.py
        for p in profiles:
            if "mlx_profile_id" in p:
                p["profile_id"] = p.get("mlx_profile_id")
                
        log.info(f"✅ Loaded {len(profiles)} active profiles from database.")
        return profiles
        
    except Exception as e:
        log.error(f"❌ Failed to fetch profiles from Supabase: {e}")
        return []

def update_profile_status(profile_id: str, status: str, tasks: list = None, error_msg: str = None):
    """
    Pushes live telemetry to Supabase.
    Statuses: 'IDLE', 'RUNNING', 'SUCCESS', 'FAILED'
    """
    supabase = get_supabase_client()
    payload = {"status": status}
    
    if tasks is not None:
        payload["last_tasks"] = tasks
        
    # If error_msg is provided, update it. If status is SUCCESS, clear the error log.
    if error_msg:
        payload["error_log"] = error_msg
    elif status == "SUCCESS":
        payload["error_log"] = None

    try:
        supabase.table("bot_profiles").update(payload).eq("id", profile_id).execute()
    except Exception as e:
        log.warning(f"⚠️ Could not update Supabase status for {profile_id}: {e}")

def update_last_run(profile_id: str):
    """Updates the last_run timestamp for a profile."""
    supabase = get_supabase_client()
    try:
        # Using timezone-aware UTC datetime is safer for Postgres
        now_iso = datetime.now(timezone.utc).isoformat()
        supabase.table("bot_profiles").update(
            {"last_run": now_iso}
        ).eq("id", profile_id).execute()
    except Exception as e:
        log.warning(f"⚠️ Could not update last_run for {profile_id}: {e}")