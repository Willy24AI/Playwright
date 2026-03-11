"""
set_timezones.py
----------------
One-time utility script to assign regional timezones to your existing bots.
Splits the farm evenly across America, Europe, and Australia.
"""

import os
import random
from dotenv import load_dotenv
from supabase import create_client

# Load your Supabase credentials
load_dotenv()
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase = create_client(url, key)

# Define our three global proxy regions
REGIONS = [
    "America/New_York",
    "Europe/London",
    "Australia/Sydney"
]

def assign_timezones():
    print("📡 Fetching profiles from Supabase...")
    
    # NOTE: Change "bot_profiles" to "profiles" if you kept your SQL table name!
    TABLE_NAME = "bot_profiles" 
    
    response = supabase.table(TABLE_NAME).select("id, browser").execute()
    profiles = response.data
    
    if not profiles:
        print("❌ No profiles found in database.")
        return

    print(f"✅ Found {len(profiles)} profiles. Assigning timezones...")
    
    success_count = 0
    for p in profiles:
        profile_id = p["id"]
        browser_data = p["browser"]
        
        # Pick a random region for this bot
        assigned_tz = random.choice(REGIONS)
        
        # Inject the timezone into the existing browser JSON
        browser_data["timezone"] = assigned_tz
        
        # Push the updated JSON back to Supabase
        try:
            supabase.table(TABLE_NAME).update({"browser": browser_data}).eq("id", profile_id).execute()
            success_count += 1
            print(f"  -> Profile {profile_id[:8]}... assigned to {assigned_tz}")
        except Exception as e:
            print(f"  ❌ Failed to update {profile_id}: {e}")

    print(f"\n🎉 Successfully updated {success_count}/{len(profiles)} profiles!")
    print("You can now run your regional commands (e.g., python main.py -c 15 --region australia)")

if __name__ == "__main__":
    assign_timezones()