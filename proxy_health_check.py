"""
proxy_health_check.py
---------------------
Tests each profile's proxy (via MLX) SEQUENTIALLY with delays.
Now with proper token refresh — the previous version was getting 401s
because it reused a stale token.

Run: python proxy_health_check.py
"""

import os
import sys
import time
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

from auth import get_token

ENV_PATH = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

LOCAL_AGENT = "https://launcher.mlx.yt:45001"


def check_profile(profile_id: str, folder_id: str, token: str):
    """Returns (result_str, maybe_new_token)."""
    url = (
        f"{LOCAL_AGENT}/api/v2/profile/f/{folder_id}/p/{profile_id}"
        f"/start?automation_type=playwright&headless_mode=false"
    )
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
    stop_url = f"{LOCAL_AGENT}/api/v2/profile/f/{folder_id}/p/{profile_id}/stop"

    for attempt in range(2):  # allow one retry after token refresh
        try:
            r = requests.get(url, headers=headers, verify=False, timeout=60)

            # ---- 401: token is stale. Force-refresh and retry once.
            if r.status_code == 401:
                if attempt == 0:
                    print(f"    (token stale, refreshing...)")
                    token = get_token(force=True)
                    headers["Authorization"] = f"Bearer {token}"
                    time.sleep(1)
                    continue
                return ("auth_still_failing (check MLX credentials)", token)

            # ---- 200: profile launched. Stop it so we don't leave browsers open.
            if r.status_code == 200:
                try:
                    requests.get(stop_url, headers=headers, verify=False, timeout=15)
                except Exception:
                    pass
                return ("alive", token)

            # ---- 400: typed MLX error
            if r.status_code == 400:
                try:
                    body = r.json()
                    err_code = body.get("status", {}).get("error_code", "")
                    err_msg = body.get("status", {}).get("message", "")
                except Exception:
                    err_code = ""
                    err_msg = r.text[:80]

                if err_code == "GET_DIRECT_CONNECTION_IP_ERROR":
                    return ("proxy_dead", token)
                if err_code == "PROFILE_ALREADY_RUNNING":
                    try:
                        requests.get(stop_url, headers=headers, verify=False, timeout=15)
                    except Exception:
                        pass
                    return ("was_running (now stopped)", token)
                return (f"mlx_error: {err_code or err_msg[:60]}", token)

            # ---- 500 / other
            return (f"http_{r.status_code}: {r.text[:80]}", token)

        except requests.exceptions.Timeout:
            return ("timeout (>60s)", token)
        except Exception as e:
            return (f"exception: {str(e)[:80]}", token)

    return ("unknown", token)


def main():
    folder_id = os.getenv("MLX_FOLDER_ID", "").strip()
    if not folder_id:
        print("❌ MLX_FOLDER_ID not set in .env")
        return

    # Test profiles. Pass IDs as CLI args, or it uses this default list.
    if len(sys.argv) > 1:
        profiles = sys.argv[1:]
    else:
        profiles = [
            "PR-0009", "PR-0104", "PR-0134", "PR-0021", "PR-0034",
            "PR-0058", "PR-0033", "PR-0072", "PR-0083", "PR-0074",
            "PR-0046", "PR-0082", "PR-0063", "PR-0450", "PR-0054",
            "PR-0137", "PR-0491", "PR-0311", "PR-0059", "PR-0045",
        ]

    print(f"Getting fresh token...")
    token = get_token(force=True)   # always start with a fresh token
    print(f"Got token. Testing {len(profiles)} profiles sequentially (3s gap)...\n")

    counts = {}
    for pid in profiles:
        result, token = check_profile(pid, folder_id, token)
        icon = {
            "alive": "✅",
            "proxy_dead": "💀",
        }.get(result.split(" ")[0] if " " in result else result, "⚠️")
        print(f"  {icon} {pid}: {result}")
        key = result.split(":")[0].split(" ")[0]
        counts[key] = counts.get(key, 0) + 1
        time.sleep(3)

    total = len(profiles)
    print(f"\n--- Summary ---")
    for key, n in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {key}: {n}/{total} ({100*n//total}%)")

    alive = counts.get("alive", 0)
    dead = counts.get("proxy_dead", 0)

    print()
    if alive == total:
        print("🎉 All proxies alive when tested sequentially.")
        print("   Your swarm failures are 100% due to concurrent-launch rate limits.")
        print("   Drop MLX_MAX_CONCURRENT_LAUNCHES in .env to 3 or 4.")
    elif alive > total * 0.7:
        print("✅ Most proxies alive sequentially. Swarm failures are likely concurrency.")
        print("   Lower MLX_MAX_CONCURRENT_LAUNCHES to 3-4.")
    elif dead > total * 0.5:
        print("💀 Most proxies dead even sequentially.")
        print("   This is a provider-side issue. Check:")
        print("     - Proxy provider account: bandwidth, subscription, IP count")
        print("     - Proxy credentials in your MLX profiles")
        print("     - Provider status page")
    else:
        print("⚠️  Mixed results. Check individual errors above.")


if __name__ == "__main__":
    main()