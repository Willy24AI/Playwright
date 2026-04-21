"""
test_folder_id.py
-----------------
Tests whether MLX_FOLDER_ID in .env actually exists in your Multilogin account.
Tries several endpoint shapes because Multilogin's API paths vary between versions.
"""

import os
from pathlib import Path
import requests
import urllib3
from dotenv import load_dotenv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

from auth import get_token

ENV_PATH = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

LOCAL_AGENT = "https://launcher.mlx.yt:45001"
CLOUD = "https://api.multilogin.com"


def main():
    folder_id = os.getenv("MLX_FOLDER_ID", "").strip()
    print(f"MLX_FOLDER_ID in .env: {folder_id}\n")

    if not folder_id:
        print("❌ Not set")
        return

    token = get_token(force=True)
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}

    print("=" * 60)
    print("Testing folder against CLOUD API (api.multilogin.com)")
    print("=" * 60)

    cloud_endpoints = [
        f"{CLOUD}/profile/search?workspace_id={folder_id}&limit=1",
        f"{CLOUD}/workspace/folder_profiles?folder_id={folder_id}&limit=1",
        f"{CLOUD}/profile/list?folder_id={folder_id}",
        f"{CLOUD}/workspace/{folder_id}/folders",
        f"{CLOUD}/workspace/folders?workspace_id={folder_id}",
    ]

    for ep in cloud_endpoints:
        try:
            r = requests.get(ep, headers=headers, verify=False, timeout=15)
            short = ep.replace(CLOUD, "")
            print(f"  [{r.status_code}] {short}")
            if r.status_code == 200:
                txt = r.text[:300]
                print(f"         → {txt}")
        except Exception as e:
            print(f"  [ERR] {ep} — {str(e)[:80]}")

    print("\n" + "=" * 60)
    print("Testing folder against LOCAL agent (launcher.mlx.yt:45001)")
    print("=" * 60)

    agent_endpoints = [
        f"{LOCAL_AGENT}/api/v2/profile/f/{folder_id}/list",
        f"{LOCAL_AGENT}/api/v2/profile/f/{folder_id}/statuses",
        f"{LOCAL_AGENT}/api/v1/profile/f/{folder_id}/list",
        f"{LOCAL_AGENT}/api/v3/profile/f/{folder_id}/list",
    ]

    for ep in agent_endpoints:
        try:
            r = requests.get(ep, headers=headers, verify=False, timeout=10)
            short = ep.replace(LOCAL_AGENT, "")
            print(f"  [{r.status_code}] {short}")
            if r.status_code in (200, 400):
                txt = r.text[:300]
                print(f"         → {txt}")
        except Exception as e:
            print(f"  [ERR] {ep} — {str(e)[:80]}")

    # Also try asking the local agent what folders it knows about
    print("\n" + "=" * 60)
    print("Asking local agent what it knows")
    print("=" * 60)

    agent_meta = [
        f"{LOCAL_AGENT}/api/v1/workspace",
        f"{LOCAL_AGENT}/api/v2/workspace",
        f"{LOCAL_AGENT}/api/v2/folder/list",
        f"{LOCAL_AGENT}/api/v1/agent/status",
        f"{LOCAL_AGENT}/api/v2/agent/status",
        f"{LOCAL_AGENT}/health",
        f"{LOCAL_AGENT}/api/v2/health",
    ]

    for ep in agent_meta:
        try:
            r = requests.get(ep, headers=headers, verify=False, timeout=8)
            short = ep.replace(LOCAL_AGENT, "")
            print(f"  [{r.status_code}] {short}")
            if r.status_code == 200:
                txt = r.text[:400]
                print(f"         → {txt}")
        except Exception as e:
            print(f"  [ERR] {ep} — {str(e)[:60]}")

    print("\n" + "=" * 60)
    print("Testing one actual profile start (PR-0009)")
    print("=" * 60)

    # Grab the profile UUID from Supabase
    su_url = os.getenv("SUPABASE_URL", "").strip()
    su_key = (
        os.getenv("SUPABASE_KEY", "").strip()
        or os.getenv("SUPABASE_ANON_KEY", "").strip()
        or os.getenv("SUPABASE_SERVICE_KEY", "").strip()
    )

    profile_uuid = None
    if su_url and su_key:
        try:
            r = requests.get(
                f"{su_url}/rest/v1/profiles?select=*&profile_id=eq.PR-0009",
                headers={"apikey": su_key, "Authorization": f"Bearer {su_key}"},
                verify=False, timeout=10,
            )
            if r.status_code == 200 and r.json():
                row = r.json()[0]
                profile_uuid = row.get("mla_uuid") or row.get("mla_id")
                print(f"  PR-0009 mla_uuid from Supabase: {profile_uuid}")
        except Exception as e:
            print(f"  Supabase lookup failed: {e}")

    if profile_uuid:
        start_url = (
            f"{LOCAL_AGENT}/api/v2/profile/f/{folder_id}/p/{profile_uuid}"
            f"/start?automation_type=playwright&headless_mode=false"
        )
        try:
            r = requests.get(start_url, headers=headers, verify=False, timeout=45)
            print(f"  Start request: HTTP {r.status_code}")
            print(f"  Response: {r.text[:500]}")
            if r.status_code == 200:
                # stop it
                stop_url = f"{LOCAL_AGENT}/api/v2/profile/f/{folder_id}/p/{profile_uuid}/stop"
                requests.get(stop_url, headers=headers, verify=False, timeout=10)
                print(f"  ✅ Profile started and stopped cleanly — folder ID is CORRECT")
        except Exception as e:
            print(f"  Error: {e}")


if __name__ == "__main__":
    main()