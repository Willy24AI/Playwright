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

# Load .env from the same folder as this file — same approach as multilogin.py
ENV_PATH = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

log = logging.getLogger(__name__)

MLX_BASE = "https://api.multilogin.com"


def _md5(text: str) -> str:
    """Multilogin requires MD5-hashed password — same as multilogin.py."""
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
    """
    saved = os.getenv("MLX_TOKEN", "").strip()
    if saved and _is_token_valid(saved):
        log.info("🔑 Using saved token from .env")
        return saved

    log.info("🔄 Token missing or expired — logging in to Multilogin...")

    # Read credentials directly — same as multilogin.py hardcoded approach
    email = os.getenv("MLX_EMAIL", "").strip()
    password = os.getenv("MLX_PASSWORD", "").strip()

    # Debug: print what we got (remove after confirming it works)
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

    response = requests.post(
        f"{MLX_BASE}/user/signin",
        json=payload,
        headers=headers,
        timeout=15,
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