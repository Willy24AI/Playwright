"fix_proxies.py - This script is designed to fix the proxy configuration for your Multilogin X profiles stored in Supabase. It reads a list of proxies from a file named 'webshare_proxies.txt', formats them into the required JSON structure, and updates each profile in the 'profiles' table with the correct proxy information. Additionally, it resets the 'mla_uuid' to None and sets the status to 'available' so that the profiles can be recreated with the new proxy settings. Make sure to have your Supabase credentials set in a .env file before running this script."

import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing Supabase credentials in .env")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
PROXY_FILE = "webshare_proxies.txt"

def load_proxies():
    """Reads the Webshare file and formats it into the exact JSON needed."""
    proxies = []
    try:
        with open(PROXY_FILE, 'r') as f:
            for line in f:
                parts = line.strip().split(':')
                if len(parts) >= 4:
                    proxies.append({
                        "proxy_ip": parts[0],
                        "proxy_port": int(parts[1]), # Ensures it passes to MLX as a number
                        "proxy_user": parts[2],
                        "proxy_pass": parts[3]
                    })
    except FileNotFoundError:
        print(f"❌ Could not find {PROXY_FILE}")
    return proxies

def main():
    proxies = load_proxies()
    if not proxies:
        return
        
    print(f"✅ Loaded {len(proxies)} perfectly formatted proxies from file.")
    
    # Fetch all profiles from Supabase
    print("Fetching profiles from Supabase...")
    response = supabase.table('profiles').select('id, profile_id').execute()
    profiles = response.data
    
    if not profiles:
        print("No profiles found in Supabase.")
        return
        
    print(f"Found {len(profiles)} profiles. Applying fixes...\n")
    
    success_count = 0
    for i, profile in enumerate(profiles):
        if i >= len(proxies):
            print("\n⚠️ Ran out of proxies! Stopping early.")
            break
            
        proxy_data = proxies[i]
        
        # 1. Overwrite network column with the correct JSON dict
        # 2. Erase the mla_uuid so the creation script knows it's brand new
        # 3. Reset status to 'available'
        supabase.table('profiles').update({
            'network': proxy_data,
            'mla_uuid': None,  
            'status': 'available' 
        }).eq('id', profile['id']).execute()
        
        success_count += 1
        
        # Print progress every 50 profiles so you know it's working
        if success_count % 50 == 0:
            print(f"⏳ Fixed {success_count} / {len(profiles)} profiles...")
            
    print(f"\n🎉 SUCCESS! Wiped old UUIDs and injected {success_count} formatted proxies.")
    print("👉 YOU CAN NOW RE-RUN create_mla_profiles.py")

if __name__ == "__main__":
    main()