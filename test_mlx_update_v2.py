"""
test_mlx_update_v2.py
---------------------
Probes MLX endpoints for profile partial update.
Tries BOTH the local agent and cloud API across multiple URL patterns.

The local agent is at https://launcher.mlx.yt:45001 (same place start/stop work).
The cloud API is at https://api.multilogin.com.

Usage: python test_mlx_update_v2.py PR-0011
"""

import sys
import json
import os
import requests
import urllib3
from pathlib import Path
from dotenv import load_dotenv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

from auth import get_token
from supabase import create_client


def get_supabase():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
    return create_client(url, key)


def fetch_profile(profile_id):
    supabase = get_supabase()
    resp = supabase.table("profiles").select("*").eq("profile_id", profile_id).execute()
    if not resp.data:
        print(f"❌ No profile found with profile_id={profile_id}")
        sys.exit(1)
    return resp.data[0]


def try_endpoint(method, url, headers, body, label):
    print(f"\n--- {label} ---")
    print(f"   {method} {url}")
    try:
        kwargs = dict(headers=headers, verify=False, timeout=20)
        if body is not None:
            kwargs["json"] = body
        if method == "POST":
            r = requests.post(url, **kwargs)
        elif method == "PATCH":
            r = requests.patch(url, **kwargs)
        elif method == "PUT":
            r = requests.put(url, **kwargs)
        elif method == "GET":
            r = requests.get(url, **kwargs)

        print(f"   Status: {r.status_code}")
        body_preview = r.text[:400]
        try:
            j = r.json()
            body_preview = json.dumps(j, indent=2)[:400]
        except Exception:
            pass
        print(f"   Body: {body_preview}")
        return r.status_code, body_preview
    except Exception as e:
        print(f"   ERROR: {type(e).__name__}: {str(e)[:200]}")
        return None, str(e)[:200]


def main():
    if len(sys.argv) < 2:
        print("Usage: python test_mlx_update_v2.py PR-0011")
        sys.exit(1)

    profile_id_name = sys.argv[1]
    profile = fetch_profile(profile_id_name)
    mla_uuid = profile["mla_uuid"]
    folder_id = os.getenv("MLX_FOLDER_ID", "3700112d-138c-4ee4-87a0-54cef39d4d0f")

    print(f"Profile name: {profile_id_name}")
    print(f"MLX UUID: {mla_uuid}")
    print(f"Folder ID: {folder_id}")

    token = get_token()
    print(f"Token: {token[:50]}...")
    print(f"Token length: {len(token)}")

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }

    # Try just READING a profile first — proves the endpoint and auth work
    test_body_minimal = {"notes": "MLX API test"}

    print("\n" + "=" * 70)
    print("PHASE 1: Try GET requests to find which endpoint EXISTS")
    print("=" * 70)

    get_candidates = [
        # Local agent (where start/stop work)
        ("GET", f"https://launcher.mlx.yt:45001/api/v2/profile/f/{folder_id}/p/{mla_uuid}",
         "LOCAL: GET /api/v2/profile/f/{folder}/p/{uuid}"),
        ("GET", f"https://launcher.mlx.yt:45001/api/v2/profile/{mla_uuid}",
         "LOCAL: GET /api/v2/profile/{uuid}"),
        # Cloud API
        ("GET", f"https://api.multilogin.com/profile/{mla_uuid}",
         "CLOUD: GET /profile/{uuid}"),
        ("GET", f"https://api.multilogin.com/api/v2/profile/{mla_uuid}",
         "CLOUD: GET /api/v2/profile/{uuid}"),
        ("GET", f"https://api.multilogin.com/v1/profile/{mla_uuid}",
         "CLOUD: GET /v1/profile/{uuid}"),
    ]

    for method, url, label in get_candidates:
        try_endpoint(method, url, headers, None, label)

    print("\n" + "=" * 70)
    print("PHASE 2: Try update endpoints with notes-only payload")
    print("=" * 70)

    update_candidates = [
        # LOCAL agent variations (most likely correct based on docs)
        ("POST", f"https://launcher.mlx.yt:45001/api/v2/profile/f/{folder_id}/p/{mla_uuid}",
         "LOCAL POST: /api/v2/profile/f/{folder}/p/{uuid}"),
        ("PATCH", f"https://launcher.mlx.yt:45001/api/v2/profile/f/{folder_id}/p/{mla_uuid}",
         "LOCAL PATCH: /api/v2/profile/f/{folder}/p/{uuid}"),
        ("POST", f"https://launcher.mlx.yt:45001/api/v2/profile/partial/{mla_uuid}",
         "LOCAL POST: /api/v2/profile/partial/{uuid}"),
        ("POST", f"https://launcher.mlx.yt:45001/api/v2/profile/update/{mla_uuid}",
         "LOCAL POST: /api/v2/profile/update/{uuid}"),
        # CLOUD variations
        ("POST", f"https://api.multilogin.com/api/v2/profile/{mla_uuid}",
         "CLOUD POST: /api/v2/profile/{uuid}"),
        ("POST", f"https://api.multilogin.com/profile/{mla_uuid}/partial",
         "CLOUD POST: /profile/{uuid}/partial"),
    ]

    for method, url, label in update_candidates:
        try_endpoint(method, url, headers, test_body_minimal, label)


if __name__ == "__main__":
    main()