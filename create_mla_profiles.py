import os
import requests
import time
from supabase import create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
MLA_API_PORT = 35000

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def load_google_accounts(filepath):
    """Loads Google accounts from a text file."""
    accounts = []
    try:
        with open(filepath, 'r') as f:
            for line in f:
                parts = line.strip().split(':')
                if len(parts) >= 3:
                    accounts.append({
                        'email': parts[0],
                        'password': parts[1],
                        'recovery': parts[2]
                    })
    except FileNotFoundError:
        print(f"Error: Could not find {filepath}.")
    return accounts

def create_multilogin_profile(profile_name, proxy_data):
    """
    Sends a POST request to Multilogin's local API to create a new profile.
    Uses 'mimic' (Chromium) and 'win' (Windows).
    """
    url = f"http://127.0.0.1:{MLA_API_PORT}/api/v2/profile"
    
    payload = {
        "name": profile_name,
        "browser": "mimic",
        "os": "win",
        "enableLock": True,
        "network": {
            "proxy": {
                "type": "HTTP",
                "host": proxy_data['proxy_ip'],
                "port": str(proxy_data['proxy_port']),
                "username": proxy_data['proxy_user'],
                "password": proxy_data['proxy_pass']
            }
        }
    }

    try:
        response = requests.post(url, json=payload)
        data = response.json()
        if response.status_code == 200 and 'uuid' in data:
            return data['uuid']
        else:
            print(f"MLA API Error: {data}")
            return None
    except Exception as e:
        print(f"Failed to connect to Multilogin API: {e}")
        return None

def main():
    accounts = load_google_accounts("google_accounts.txt")
    if not accounts:
        return

    # Fetch profiles that don't have an MLA UUID assigned yet
    response = supabase.table('profiles').select('*').is_('mla_uuid', 'null').execute()
    unassigned_profiles = response.data
    
    if not unassigned_profiles:
        print("All profiles in Supabase already have an mla_uuid assigned.")
        return

    print(f"Found {len(unassigned_profiles)} pending profiles. Creating in Multilogin...")

    for i, db_profile in enumerate(unassigned_profiles):
        if i >= len(accounts):
            print("Ran out of Google accounts before finishing all profiles!")
            break
            
        account = accounts[i]
        profile_name = db_profile['profile_id'] # e.g., PR-0001
        proxy_data = db_profile['network']
        
        print(f"Creating MLA profile for {profile_name}...")
        
        # 1. Create the profile in Multilogin
        mla_uuid = create_multilogin_profile(profile_name, proxy_data)
        
        if mla_uuid:
            # 2. Update Supabase with the new UUID and Google credentials
            supabase.table('profiles').update({
                'mla_uuid': mla_uuid,
                'google_email': account['email'],
                'google_password': account['password'],
                'google_recovery': account['recovery']
            }).eq('id', db_profile['id']).execute()
            
            print(f"Success: Linked {account['email']} to {profile_name} (UUID: {mla_uuid})")
        else:
            print(f"Failed to create Multilogin profile for {profile_name}.")
            
        # Brief pause to avoid overwhelming the local API
        time.sleep(1)

    print("Multilogin profile generation complete.")

if __name__ == "__main__":
    main()