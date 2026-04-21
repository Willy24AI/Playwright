"""
list_folders.py
---------------
Lists all workspaces/folders visible to your Multilogin account,
so you can find the correct MLX_FOLDER_ID to put in .env.
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


def main():
    token = get_token(force=True)
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}

    # Try the cloud API's workspace listing
    print("Fetching workspaces from Multilogin cloud...\n")

    endpoints = [
        "https://api.multilogin.com/workspace/workspaces_list",
        "https://api.multilogin.com/workspace/list",
        "https://api.multilogin.com/user/workspaces",
    ]

    for url in endpoints:
        try:
            r = requests.get(url, headers=headers, verify=False, timeout=15)
            if r.status_code == 200:
                data = r.json()
                print(f"✅ {url}")
                print(f"   Raw response:\n   {data}\n")

                # Try to extract workspaces from common response shapes
                items = (
                    data.get("data", {}).get("workspaces")
                    or data.get("data", {}).get("items")
                    or data.get("data")
                    or data.get("workspaces")
                    or []
                )
                if isinstance(items, list) and items:
                    print("Workspaces / Folders found:")
                    for item in items:
                        if isinstance(item, dict):
                            wid = item.get("id") or item.get("uuid") or item.get("workspace_id")
                            name = item.get("name") or item.get("workspace_name") or "(no name)"
                            print(f"  • {wid}   {name}")
                return
            else:
                print(f"  {url} → HTTP {r.status_code}")
        except Exception as e:
            print(f"  {url} → {str(e)[:80]}")

    print("\nCouldn't auto-list workspaces. Use Option B (browser method) instead.")


if __name__ == "__main__":
    main()