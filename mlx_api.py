"""
mlx_api.py
----------
Starts and stops Multilogin profiles.
Upgraded with Dynamic CDP Polling to prevent ConnectionRefusedErrors 
under high-concurrency swarm loads, and safeguards against Zombie Processes.

[FIXED]:
- truststore SSL fix for Multilogin X desktop app compatibility
- Proxy warmup delay after port opens
- Better error categorization (proxy_error vs hard failure)
"""

import logging
import os
import time
import socket
from pathlib import Path

import requests
import urllib3
from dotenv import load_dotenv

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Fix SSL: Use Windows native certificate store
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

ENV_PATH = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

log = logging.getLogger(__name__)

LOCAL_AGENT = "https://launcher.mlx.yt:45001"
MAX_BOOT_WAIT = 30  # Maximum seconds to wait for the browser to open the CDP port
PROXY_WARMUP_DELAY = 3  # Extra seconds after port opens for proxy to fully initialize

def _is_port_open(port: int) -> bool:
    """Silently pings a localhost port to see if the DevTools protocol is ready."""
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
    Dynamically polls the port to ensure Playwright can connect safely.
    Includes proxy warmup delay after port opens.
    """
    folder_id = os.getenv("MLX_FOLDER_ID", "").strip()
    if not folder_id:
        raise ValueError("MLX_FOLDER_ID not set in .env")

    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
    }

    # 1. Clean Slate: Stop first in case of a previous crash (Zombie Process)
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

    for attempt in range(3):
        try:
            response = requests.get(start_url, headers=headers, verify=False, timeout=30)

            if response.status_code == 200:
                data = response.json()
                profile_data = data.get("data", {})
                port = profile_data.get("port")

                if port:
                    ws_endpoint = f"http://127.0.0.1:{port}"
                    log.info(f"    ⚙️ [{profile_id[:8]}] MLX returned port {port}. Waiting for DevTools to bind...")
                    
                    # 2. Dynamic Polling: Wait for the port to open
                    start_wait = time.time()
                    while time.time() - start_wait < MAX_BOOT_WAIT:
                        if _is_port_open(int(port)):
                            boot_time = time.time() - start_wait
                            log.info(f"    ✅ [{profile_id[:8]}] Browser DevTools active after {boot_time:.1f}s.")
                            
                            # 3. Proxy Warmup: Give the proxy a moment to fully initialize
                            # This prevents ERR_INVALID_AUTH_CREDENTIALS on first navigation
                            log.info(f"    ⏳ [{profile_id[:8]}] Proxy warmup ({PROXY_WARMUP_DELAY}s)...")
                            time.sleep(PROXY_WARMUP_DELAY)
                            
                            log.info(f"    🚀 [{profile_id[:8]}] Handing off to Playwright.")
                            return ws_endpoint
                        time.sleep(1)
                        
                    raise TimeoutError(f"Browser launched, but port {port} never opened.")

                else:
                    log.warning(f"    ⚠️ No port in MLX response: {data}")

            elif response.status_code == 401:
                raise PermissionError("Token expired — restart script")

            elif response.status_code == 429:
                log.warning(f"    ⏳ MLX API Rate limited, waiting 10s (attempt {attempt+1}/3)")
                time.sleep(10)

            elif response.status_code == 400:
                error_code = response.json().get("status", {}).get("error_code", "")
                if error_code == "PROFILE_ALREADY_RUNNING":
                    log.warning(f"    ⚠️ MLX states profile is already running. Forcing stop and retry... (attempt {attempt+1}/3)")
                    requests.get(stop_url, headers=headers, verify=False, timeout=10)
                    time.sleep(5)
                elif error_code == "GET_DIRECT_CONNECTION_IP_ERROR":
                    # Proxy is dead/misconfigured — don't retry, skip this profile
                    raise ConnectionError(f"PROXY_ERROR: Profile {profile_id[:8]} has a dead proxy")
                else:
                    log.warning(f"    ⚠️ [{response.status_code}] {response.text} (attempt {attempt+1}/3)")
                    time.sleep(5)
            else:
                log.warning(f"    ⚠️ [{response.status_code}] {response.text} (attempt {attempt+1}/3)")
                time.sleep(5)

        except (ConnectionError, PermissionError, TimeoutError):
            raise  # Don't retry these — they're definitive

        except requests.RequestException as e:
            log.warning(f"    ⚠️ MLX Request error (attempt {attempt+1}/3): {e}")
            time.sleep(5)

    raise RuntimeError(f"Failed to start profile {profile_id} after 3 attempts. Check MLX Agent.")


def stop_profile(profile_id: str, token: str):
    """
    Stops a profile cleanly — saves cookies back to Multilogin.
    IMPORTANT: Call this BEFORE browser.close() to ensure cookies are saved.
    """
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
            log.info(f"    ⏹ [{profile_id[:8]}] Profile stopped & cookies saved to cloud.")
        elif resp.status_code == 404:
            log.info(f"    ⏹ [{profile_id[:8]}] Profile already stopped.")
        else:
            log.warning(f"    ⚠️ Stop Error [{resp.status_code}]: {resp.text}")
    except requests.RequestException as e:
        log.warning(f"    ⚠️ Could not communicate with MLX to stop {profile_id[:8]}: {e}")