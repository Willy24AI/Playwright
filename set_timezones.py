"""
set_timezones.py
----------------
One-time utility script to assign regional timezones to your existing bots.
[UPGRADED]: Uses Pagination to fetch 10,000+ profiles safely, expands timezone entropy, 
and uses ThreadPoolExecutor for massive concurrent database updates.
"""

import os
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
from supabase import create_client, Client

# Load your Supabase credentials
load_dotenv()
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
if not url or not key:
    raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY in .env")

supabase: Client = create_client(url, key)
TABLE_NAME = "bot_profiles"

# Expanded entropy: More diverse timezones across the 3 main regions.
# Because profiles_config.py uses substring matching (e.g., 'america' in tz),
# this still perfectly supports your command line args!
REGIONS = [
    "America/New_York", "America/Chicago", "America/Los_Angeles",
    "Europe/London", "Europe/Berlin", "Europe/Paris",
    "Australia/Sydney", "Australia/Melbourne", "Australia/Perth"
]

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
                    time.sleep(backoff_factor ** attempt)
            return None
        return wrapper
    return decorator

def fetch_all_profiles() -> list:
    """Uses pagination to bypass Supabase's 1000-row limit for massive datasets."""
    print("📡 Fetching profiles from Supabase (Handling Pagination)...")
    all_profiles = []
    limit = 1000
    offset = 0
    
    while True:
        # Fetch in chunks of 1000
        res = supabase.table(TABLE_NAME).select("id, browser").range(offset, offset + limit - 1).execute()
        data = res.data
        if not data:
            break
            
        all_profiles.extend(data)
        
        # If we received fewer than the limit, we've hit the end of the database
        if len(data) < limit:
            break
            
        offset += limit
        
    return all_profiles

@with_retries(max_retries=3)
def update_single_profile(profile_id: str, browser_data: dict, assigned_tz: str):
    """Updates a single profile. Wrapped in retry logic for network resilience."""
    if not isinstance(browser_data, dict):
        browser_data = {}
        
    browser_data["timezone"] = assigned_tz
    supabase.table(TABLE_NAME).update({"browser": browser_data}).eq("id", profile_id).execute()
    return profile_id, assigned_tz

def assign_timezones():
    profiles = fetch_all_profiles()
    
    if not profiles:
        print("❌ No profiles found in database.")
        return

    print(f"✅ Found {len(profiles)} profiles. Assigning timezones using ThreadPool concurrency...")
    
    success_count = 0
    
    # Use ThreadPoolExecutor to update 20 profiles simultaneously
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = []
        for p in profiles:
            profile_id = p["id"]
            browser_data = p.get("browser", {})
            assigned_tz = random.choice(REGIONS)
            
            # Submit the update task to the background thread pool
            futures.append(executor.submit(update_single_profile, profile_id, browser_data, assigned_tz))
            
        # Process results as they complete
        for future in as_completed(futures):
            result = future.result()
            if result:
                profile_id, tz = result
                print(f"    -> Profile {profile_id[:8]}... assigned to {tz}")
                success_count += 1
            else:
                print(f"    ❌ Failed to update a profile after 3 attempts.")

    print(f"\n🎉 Successfully updated {success_count}/{len(profiles)} profiles!")
    print("You can now run your regional commands (e.g., python main.py -c 15 --region australia)")

if __name__ == "__main__":
    assign_timezones()