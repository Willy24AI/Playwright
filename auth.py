"""
auth.py
-------
Handles Multilogin authentication.
Uses the exact same login pattern as the working multilogin.py script.
"""

import hashlib
import json
import logging
import os
import base64
import time
from pathlib import Path

import requests
from dotenv import load_dotenv, set_key

# Load .env from the same folder as this file
ENV_PATH = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

# Fix SSL: Use Windows native certificate store instead of Python's bundled OpenSSL.
# This resolves SSLV3_ALERT_BAD_RECORD_MAC errors when Multilogin X desktop app is running.
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass  # truststore not installed, will use default SSL

log = logging.getLogger(__name__)

MLX_BASE = "https://api.multilogin.com"


def _md5(text: str) -> str:
    """Multilogin requires MD5-hashed password."""
    return hashlib.md5(text.encode()).hexdigest()


def _is_token_valid(token: str) -> bool:
    """Check if saved token still has more than 5 minutes left."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return False
        padding = "=" * (-len(parts[1]) % 4)
        decoded = json.loads(base64.b64decode(parts[1] + padding))
        return (decoded.get("exp", 0) - time.time()) > 300
    except Exception:
        return False


def get_token() -> str:
    """
    Returns a valid Bearer token.
    - Uses saved token from .env if still valid
    - Otherwise logs in fresh using email + MD5 password
    - Retries up to 5 times on SSL/network errors
    """
    saved = os.getenv("MLX_TOKEN", "").strip()
    if saved and _is_token_valid(saved):
        log.info("🔑 Using saved token from .env")
        return saved

    log.info("🔄 Token missing or expired — logging in to Multilogin...")

    email = os.getenv("MLX_EMAIL", "").strip()
    password = os.getenv("MLX_PASSWORD", "").strip()

    log.info(f"   Email found: {'✅' if email else '❌ MISSING'}")
    log.info(f"   Password found: {'✅' if password else '❌ MISSING'}")

    if not email or not password:
        raise ValueError(
            f"MLX_EMAIL and MLX_PASSWORD not found in .env\n"
            f"  .env path checked: {ENV_PATH}\n"
            f"  File exists: {ENV_PATH.exists()}"
        )

    payload = {
        "email": email,
        "password": _md5(password),
    }
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    # Retry loop for SSL/network errors
    for attempt in range(1, 6):
        try:
            response = requests.post(
                f"{MLX_BASE}/user/signin",
                json=payload,
                headers=headers,
                verify=False,
                timeout=30,
            )

            if response.status_code != 200:
                raise ConnectionError(
                    f"Multilogin login failed [{response.status_code}]: {response.text}"
                )

            token = response.json()["data"]["token"]
            log.info("✅ Logged in successfully")

            # Save token back to .env for next run
            try:
                set_key(str(ENV_PATH), "MLX_TOKEN", token)
                log.info("✅ Token saved to .env")
            except Exception as e:
                log.warning(f"Could not save token to .env: {e}")

            return token

        except (requests.exceptions.SSLError, requests.exceptions.ConnectionError) as e:
            log.warning(f"⚠️ Auth attempt {attempt}/5 failed: {str(e)[:60]}")
            if attempt < 5:
                time.sleep(2)
            else:
                raise ConnectionError(f"Failed to authenticate after 5 attempts: {e}")

        except Exception as e:
            err = str(e)
            if any(k in err for k in ["BAD_RECORD_MAC", "SSL", "disconnected"]):
                log.warning(f"⚠️ Auth attempt {attempt}/5 SSL error: {err[:60]}")
                if attempt < 5:
                    time.sleep(2)
                    continue
            raise