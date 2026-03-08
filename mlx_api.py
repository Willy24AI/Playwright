"""
mlx_api.py
----------
Starts and stops Multilogin profiles.
Uses the exact same URL format and approach as the working multilogin.py script.
"""

import logging
import os
import time
from pathlib import Path

import requests
import urllib3
from dotenv import load_dotenv

# Suppress SSL warnings — same as multilogin.py
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ENV_PATH = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

log = logging.getLogger(__name__)

LOCAL_AGENT = "https://launcher.mlx.yt:45001"

# Seconds to wait after browser starts before Playwright connects
# Browser needs time to fully initialize its DevTools protocol
BROWSER_INIT_WAIT = 8


def start_profile(profile_id: str, token: str) -> str:
    """
    Starts a Multilogin profile and returns the CDP endpoint URL.
    Uses the exact same URL format as the working multilogin.py.
    """
    folder_id = os.getenv("MLX_FOLDER_ID", "").strip()
    if not folder_id:
        raise ValueError("MLX_FOLDER_ID not set in .env")

    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
    }

    # Stop first in case already running — same as multilogin.py
    stop_url = f"{LOCAL_AGENT}/api/v2/profile/f/{folder_id}/p/{profile_id}/stop"
    requests.get(stop_url, headers=headers, verify=False)
    log.info(f"  ⏳ [{profile_id[:8]}] Waiting for profile to stop...")
    time.sleep(5)

    # Start with exact same URL format as multilogin.py
    start_url = (
        f"{LOCAL_AGENT}/api/v2/profile/f/{folder_id}/p/{profile_id}"
        f"/start?automation_type=playwright&headless_mode=false"
    )

    log.info(f"  ▶ [{profile_id[:8]}] Starting profile...")

    for attempt in range(3):
        try:
            response = requests.get(
                start_url, headers=headers, verify=False, timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                profile_data = data.get("data", {})

                # Build URL from port — exact same as multilogin.py
                port = profile_data.get("port")
                if port:
                    ws_endpoint = f"http://127.0.0.1:{port}"
                else:
                    ws_endpoint = data.get("wsEndpoint") or data.get("value")

                if ws_endpoint:
                    log.info(f"  ✅ [{profile_id[:8]}] Started → {ws_endpoint}")
                    log.info(f"  ⏳ [{profile_id[:8]}] Waiting {BROWSER_INIT_WAIT}s for browser to fully initialize...")
                    time.sleep(BROWSER_INIT_WAIT)
                    return ws_endpoint
                else:
                    log.warning(f"  ⚠️ No endpoint in response: {data}")

            elif response.status_code == 401:
                raise PermissionError("Token expired — restart script")

            elif response.status_code == 429:
                log.warning(f"  ⏳ Rate limited, waiting 10s (attempt {attempt+1}/3)")
                time.sleep(10)

            elif response.status_code == 400:
                error_code = response.json().get("status", {}).get("error_code", "")
                if error_code == "PROFILE_ALREADY_RUNNING":
                    log.warning(f"  ⚠️ Profile already running, waiting 15s then retrying... (attempt {attempt+1}/3)")
                    time.sleep(15)
                else:
                    log.warning(f"  ⚠️ [{response.status_code}] {response.text} (attempt {attempt+1}/3)")
                    time.sleep(5)

            else:
                log.warning(
                    f"  ⚠️ [{response.status_code}] {response.text} (attempt {attempt+1}/3)"
                )
                time.sleep(5)

        except requests.RequestException as e:
            log.warning(f"  ⚠️ Request error (attempt {attempt+1}/3): {e}")
            time.sleep(5)

    raise RuntimeError(f"Failed to start profile {profile_id} after 3 attempts")


def stop_profile(profile_id: str, token: str):
    """Stops a profile cleanly — saves cookies back to Multilogin."""
    folder_id = os.getenv("MLX_FOLDER_ID", "").strip()
    if not folder_id:
        log.warning("  ⚠️ MLX_FOLDER_ID not set — cannot stop profile cleanly")
        return

    # Use same URL format as start_profile and working multilogin.py
    url = f"{LOCAL_AGENT}/api/v2/profile/f/{folder_id}/p/{profile_id}/stop"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
    }

    try:
        resp = requests.get(url, headers=headers, verify=False, timeout=15)
        if resp.status_code == 200:
            log.info(f"  ⏹ [{profile_id[:8]}] Stopped and saved.")
        elif resp.status_code == 404:
            # Profile already stopped — not an error
            log.info(f"  ⏹ [{profile_id[:8]}] Already stopped.")
        else:
            log.warning(f"  ⚠️ Stop [{resp.status_code}]: {resp.text}")
    except requests.RequestException as e:
        log.warning(f"  ⚠️ Could not stop {profile_id[:8]}: {e}")