"""
mlx_api.py
----------
Starts and stops Multilogin profiles.

[HARDENED v3]:
  - Launch stagger increased from 0.1-0.5s to 1.5-3.0s to prevent burst
    401s that trigger auth cascade.
  - MLX_MAX_CONCURRENT_LAUNCHES lowered from 6 to 3 by default.
  - Thread-safe token refresh coalescing (lives in auth.py).
  - Proxy-dead path (GET_DIRECT_CONNECTION_IP_ERROR) raises immediately.
  - On 401, calls auth.get_token(force=True) which is coalesced.
"""

import logging
import os
import random
import socket
import threading
import time
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

ENV_PATH = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

log = logging.getLogger(__name__)

LOCAL_AGENT = "https://launcher.mlx.yt:45001"
MAX_BOOT_WAIT = 30
PROXY_WARMUP_DELAY = 3

# ---- Launch throttle --------------------------------------------------------
# Multilogin's cloud auth endpoint doesn't tolerate burst traffic well.
# Lowering to 3 concurrent + larger stagger eliminates 401 cascade.
_MAX_CONCURRENT = int(os.getenv("MLX_MAX_CONCURRENT_LAUNCHES", "3"))
_launch_sem = threading.Semaphore(_MAX_CONCURRENT)

# Stagger range (seconds) — increase if you still see 429s in auth
_STAGGER_MIN = float(os.getenv("MLX_LAUNCH_STAGGER_MIN", "1.5"))
_STAGGER_MAX = float(os.getenv("MLX_LAUNCH_STAGGER_MAX", "3.0"))


def _is_port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        try:
            s.connect(("127.0.0.1", port))
            return True
        except (socket.timeout, ConnectionRefusedError):
            return False


def start_profile(profile_id: str, token: str) -> str:
    """
    Starts a Multilogin profile and returns the CDP endpoint URL.
    """
    folder_id = os.getenv("MLX_FOLDER_ID", "").strip()
    if not folder_id:
        raise ValueError("MLX_FOLDER_ID not set in .env")

    # Throttle concurrent launches + substantial jitter so bursts don't hit MLX at once.
    # This is the KEY fix for the auth cascade: spreading launches over time means
    # token refreshes don't pile up and trigger 429s.
    with _launch_sem:
        time.sleep(random.uniform(_STAGGER_MIN, _STAGGER_MAX))
        return _start_profile_inner(profile_id, token, folder_id)


def _start_profile_inner(profile_id: str, token: str, folder_id: str) -> str:
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
    }

    # Clean slate: stop first in case of zombie
    stop_url = f"{LOCAL_AGENT}/api/v2/profile/f/{folder_id}/p/{profile_id}/stop"
    try:
        requests.get(stop_url, headers=headers, verify=False, timeout=10)
        time.sleep(2)
    except Exception:
        pass

    start_url = (
        f"{LOCAL_AGENT}/api/v2/profile/f/{folder_id}/p/{profile_id}"
        f"/start?automation_type=playwright&headless_mode=false"
    )

    log.info(f"    ▶ [{profile_id[:8]}] Requesting MLX Profile Launch...")

    refreshed_once = False  # only refresh the token ONCE per start_profile call

    for attempt in range(3):
        try:
            response = requests.get(start_url, headers=headers, verify=False, timeout=30)

            if response.status_code == 200:
                data = response.json()
                port = data.get("data", {}).get("port")

                if port:
                    ws_endpoint = f"http://127.0.0.1:{port}"
                    log.info(f"    ⚙️ [{profile_id[:8]}] MLX returned port {port}. Waiting for DevTools...")

                    start_wait = time.time()
                    while time.time() - start_wait < MAX_BOOT_WAIT:
                        if _is_port_open(int(port)):
                            boot_time = time.time() - start_wait
                            log.info(f"    ✅ [{profile_id[:8]}] DevTools active after {boot_time:.1f}s.")
                            log.info(f"    ⏳ [{profile_id[:8]}] Proxy warmup ({PROXY_WARMUP_DELAY}s)...")
                            time.sleep(PROXY_WARMUP_DELAY)
                            log.info(f"    🚀 [{profile_id[:8]}] Handing off to Playwright.")
                            return ws_endpoint
                        time.sleep(1)

                    raise TimeoutError(f"Browser launched, but port {port} never opened.")
                else:
                    log.warning(f"    ⚠️ No port in MLX response: {data}")

            elif response.status_code == 401:
                if refreshed_once:
                    raise PermissionError(
                        f"Auth still failing for {profile_id[:8]} after refresh"
                    )
                log.warning(f"    🔄 [{profile_id[:8]}] Token rejected. Forcing refresh...")
                try:
                    from auth import get_token
                    token = get_token(force=True)   # <- thread-safe, coalesced
                    headers["Authorization"] = f"Bearer {token}"
                    refreshed_once = True
                    log.info(f"    🔑 [{profile_id[:8]}] Token refreshed. Retrying...")
                    # Add small cushion after refresh so burst doesn't re-trigger
                    time.sleep(random.uniform(0.5, 1.5))
                    continue
                except Exception as refresh_err:
                    raise PermissionError(f"Token refresh failed: {refresh_err}")

            elif response.status_code == 429:
                # Back off longer on rate limits
                wait = 10 + (attempt * 5)
                log.warning(f"    ⏳ MLX rate limited, waiting {wait}s (attempt {attempt+1}/3)")
                time.sleep(wait)

            elif response.status_code == 400:
                try:
                    error_code = response.json().get("status", {}).get("error_code", "")
                except Exception:
                    error_code = ""

                if error_code == "PROFILE_ALREADY_RUNNING":
                    log.warning(f"    ⚠️ Profile already running. Forcing stop... (attempt {attempt+1}/3)")
                    requests.get(stop_url, headers=headers, verify=False, timeout=10)
                    time.sleep(5)
                elif error_code == "GET_DIRECT_CONNECTION_IP_ERROR":
                    # Dead proxy — don't retry, skip immediately.
                    raise ConnectionError(f"PROXY_ERROR: {profile_id[:8]} has a dead proxy")
                else:
                    log.warning(f"    ⚠️ [{response.status_code}] {response.text} (attempt {attempt+1}/3)")
                    time.sleep(5)
            else:
                log.warning(f"    ⚠️ [{response.status_code}] {response.text} (attempt {attempt+1}/3)")
                time.sleep(5)

        except (ConnectionError, PermissionError, TimeoutError):
            raise

        except requests.RequestException as e:
            log.warning(f"    ⚠️ MLX request error (attempt {attempt+1}/3): {e}")
            time.sleep(5)

    raise RuntimeError(f"Failed to start profile {profile_id} after 3 attempts. Check MLX Agent.")


def stop_profile(profile_id: str, token: str):
    """Stops a profile cleanly — saves cookies back to Multilogin."""
    folder_id = os.getenv("MLX_FOLDER_ID", "").strip()
    if not folder_id:
        log.warning("    ⚠️ MLX_FOLDER_ID not set — cannot stop profile cleanly")
        return

    url = f"{LOCAL_AGENT}/api/v2/profile/f/{folder_id}/p/{profile_id}/stop"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
    }

    try:
        resp = requests.get(url, headers=headers, verify=False, timeout=15)
        if resp.status_code == 200:
            log.info(f"    ⏹ [{profile_id[:8]}] Stopped & cookies saved.")
        elif resp.status_code == 404:
            log.info(f"    ⏹ [{profile_id[:8]}] Already stopped.")
        else:
            log.warning(f"    ⚠️ Stop Error [{resp.status_code}]: {resp.text}")
    except requests.RequestException as e:
        log.warning(f"    ⚠️ Could not reach MLX to stop {profile_id[:8]}: {e}")