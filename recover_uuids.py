"""
recover_uuids.py - Recover mla_uuid from existing Multilogin X profiles

This script:
1. Fetches all profiles from Multilogin X Cloud API (by folder)
2. Matches them by name (profile_id) to Supabase records
3. Updates Supabase with the mla_uuid so google_signin.py can find them

Run this INSTEAD of create_mla_profiles.py when profiles already exist in MLX
but Supabase has mla_uuid = NULL (e.g. after running fix_proxies.py).
"""

import os
import hashlib
import time
from dotenv import load_dotenv

load_dotenv()

import truststore
truststore.inject_into_ssl()

import httpx
from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
MLX_EMAIL = os.getenv("MLX_EMAIL")
MLX_PASSWORD = os.getenv("MLX_PASSWORD")
MLX_FOLDER_ID = os.getenv("MLX_FOLDER_ID")

MLX_CLOUD_API = "https://api.multilogin.com"

if not all([SUPABASE_URL, SUPABASE_KEY, MLX_EMAIL, MLX_PASSWORD, MLX_FOLDER_ID]):
    raise ValueError("Missing credentials in .env")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def mlx_post(url, token, payload, max_retries=5):
    """Make a POST request to MLX API with retries."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    for attempt in range(1, max_retries + 1):
        try:
            with httpx.Client(verify=False, timeout=30, trust_env=False) as client:
                resp = client.post(url, json=payload, headers=headers)
                if resp.status_code in (200, 201):
                    return resp.json()
                print(f"  ⚠️ API {resp.status_code}: {resp.text[:150]}")
                if resp.status_code in (400, 401, 403):
                    return None
        except Exception as e:
            print(f"  Network error (attempt {attempt}/{max_retries}): {str(e)[:60]}")
            time.sleep(2)
    return None


def get_token():
    """Get MLX auth token."""
    print("🔑 Authenticating with Multilogin X...")
    hashed = hashlib.md5(MLX_PASSWORD.strip().encode()).hexdigest()
    headers = {"Accept": "application/json", "Content-Type": "application/json"}

    for attempt in range(1, 6):
        try:
            with httpx.Client(verify=False, timeout=30, trust_env=False) as client:
                resp = client.post(f"{MLX_CLOUD_API}/user/signin",
                                   json={"email": MLX_EMAIL.strip(), "password": hashed},
                                   headers=headers)
                if resp.status_code == 200:
                    token = resp.json().get("data", {}).get("token")
                    if token:
                        print("✅ Authenticated!")
                        return token
                print(f"  ⚠️ Auth attempt {attempt}: {resp.text[:100]}")
        except Exception as e:
            print(f"  ⚠️ Auth attempt {attempt}: {str(e)[:60]}")
            time.sleep(2)
    return None


def fetch_mlx_profiles(token):
    """Fetch all profiles from MLX folder using profile/search endpoint."""
    all_profiles = []
    offset = 0
    limit = 100  # Profiles per page

    print(f"\n📥 Fetching profiles from MLX folder...")

    while True:
        payload = {
            "folder_id": MLX_FOLDER_ID,
            "search_text": "",       # Required field - empty string returns all
            "offset": offset,
            "limit": limit,
            "is_removed": False
        }

        data = mlx_post(f"{MLX_CLOUD_API}/profile/search", token, payload)

        if not data:
            break

        profiles = data.get("data", {}).get("profiles", [])
        if not profiles:
            break

        all_profiles.extend(profiles)
        print(f"  Fetched {len(all_profiles)} profiles so far...")

        if len(profiles) < limit:
            break  # Last page

        offset += limit
        time.sleep(1)  # Rate limit respect

    print(f"✅ Total MLX profiles fetched: {len(all_profiles)}")
    return all_profiles


def main():
    token = get_token()
    if not token:
        print("❌ Failed to authenticate")
        return

    # Step 1: Fetch all profiles from MLX
    mlx_profiles = fetch_mlx_profiles(token)

    if not mlx_profiles:
        print("❌ No profiles found in MLX. You need to run create_mla_profiles.py first.")
        return

    # Build lookup: profile name -> uuid
    mlx_lookup = {}
    for p in mlx_profiles:
        name = p.get("name", "")
        uuid = p.get("id")  # MLX uses "id" field for the UUID
        if name and uuid:
            mlx_lookup[name] = uuid

    print(f"\n📋 Built lookup with {len(mlx_lookup)} named profiles")

    # Show a sample for verification
    sample = list(mlx_lookup.items())[:3]
    for name, uuid in sample:
        print(f"  Example: {name} -> {uuid[:20]}...")

    # Step 2: Fetch Supabase profiles with null mla_uuid
    print("\n📥 Fetching Supabase profiles with mla_uuid = NULL...")
    response = supabase.table('profiles').select('id, profile_id').is_('mla_uuid', 'null').execute()
    sb_profiles = response.data

    if not sb_profiles:
        print("✅ All Supabase profiles already have mla_uuid!")
        return

    print(f"Found {len(sb_profiles)} profiles needing UUID recovery\n")

    # Step 3: Match and update
    matched = 0
    not_found = 0
    not_found_names = []

    for sp in sb_profiles:
        profile_id = sp.get('profile_id', '')
        db_id = sp['id']

        if profile_id in mlx_lookup:
            uuid = mlx_lookup[profile_id]
            supabase.table('profiles').update({
                'mla_uuid': uuid
            }).eq('id', db_id).execute()
            matched += 1

            if matched % 50 == 0:
                print(f"  ⏳ Matched {matched} / {len(sb_profiles)}...")
        else:
            not_found += 1
            if len(not_found_names) < 10:
                not_found_names.append(profile_id)

    print(f"\n{'='*50}")
    print(f"🎉 RECOVERY COMPLETE!")
    print(f"  ✅ Matched & updated: {matched}")
    print(f"  ❌ Not found in MLX: {not_found}")
    print(f"{'='*50}")

    if not_found > 0:
        print(f"\n⚠️ {not_found} profiles don't exist in MLX yet.")
        print(f"   Examples: {', '.join(not_found_names[:5])}")
        print("   Run create_mla_profiles.py to create them.")
    
    if matched > 0:
        print(f"\n👉 You can now run google_signin.py!")


if __name__ == "__main__":
    main()