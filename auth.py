"""
auth.py
-------
Thread-safe Multilogin authentication for swarm use.

v2 changes:
  - Fresh `requests.Session` per login attempt. Reusing sessions after
    an SSL error is what causes SSLV3_ALERT_BAD_RECORD_MAC to cascade.
  - Longer coalesce window (60s). A burst of 50 forced refreshes gets
    ONE login, even if they arrive over 30+ seconds.
  - Exponential backoff tuned higher for SSL errors specifically.
  - Connection: close header to avoid HTTP keep-alive TLS reuse bugs.
"""

import hashlib
import json
import logging
import os
import base64
import threading
import time
from pathlib import Path

import requests
from dotenv import load_dotenv, set_key

ENV_PATH = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

log = logging.getLogger(__name__)

MLX_BASE = "https://api.multilogin.com"

# Thread-safe cache
_token_lock = threading.Lock()
_cached_token: str | None = None
_cached_at: float = 0.0

# 60s coalesce: a burst of forced refreshes within this window reuses the
# same token instead of each triggering a new login. Tokens are valid for
# hours, so this is always safe.
_REFRESH_COALESCE_WINDOW = 60.0


def _md5(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()


def _is_token_valid(token: str) -> bool:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return False
        padding = "=" * (-len(parts[1]) % 4)
        decoded = json.loads(base64.b64decode(parts[1] + padding))
        return (decoded.get("exp", 0) - time.time()) > 300
    except Exception:
        return False


def _do_login() -> str:
    """Network login. Only ever called under _token_lock."""
    email = os.getenv("MLX_EMAIL", "").strip()
    password = os.getenv("MLX_PASSWORD", "").strip()

    if not email or not password:
        raise ValueError(
            f"MLX_EMAIL and MLX_PASSWORD missing. .env path: {ENV_PATH}"
        )

    payload = {"email": email, "password": _md5(password)}
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Connection": "close",  # avoid HTTP keep-alive TLS reuse bugs
    }

    last_err: Exception | None = None
    max_attempts = 6

    for attempt in range(1, max_attempts + 1):
        # FRESH session per attempt — this is the key fix for cascading
        # BAD_RECORD_MAC errors. The old code retried on the same session,
        # which kept the broken TLS connection alive.
        session = requests.Session()
        try:
            response = session.post(
                f"{MLX_BASE}/user/signin",
                json=payload,
                headers=headers,
                verify=False,
                timeout=30,
            )

            if response.status_code == 429:
                wait = min(5 * attempt, 30)
                log.warning(f"⏳ Auth 429. Backing off {wait}s (attempt {attempt}/{max_attempts})")
                time.sleep(wait)
                continue

            if response.status_code != 200:
                raise ConnectionError(
                    f"Multilogin login failed [{response.status_code}]: {response.text[:200]}"
                )

            token = response.json()["data"]["token"]
            log.info("✅ Logged in successfully")

            try:
                set_key(str(ENV_PATH), "MLX_TOKEN", token)
            except Exception as e:
                log.warning(f"Could not save token to .env: {e}")

            return token

        except (requests.exceptions.SSLError, requests.exceptions.ConnectionError) as e:
            last_err = e
            err_str = str(e)[:100]
            is_ssl = "SSL" in err_str or "BAD_RECORD_MAC" in err_str
            # SSL errors need longer waits — the TLS pool needs to clear.
            wait = (4 if is_ssl else 2) * attempt
            log.warning(
                f"⚠️ Auth attempt {attempt}/{max_attempts} failed "
                f"({'SSL' if is_ssl else 'network'}): {err_str}"
            )
            if attempt < max_attempts:
                time.sleep(wait)

        except Exception as e:
            err = str(e)
            if any(k in err for k in ["BAD_RECORD_MAC", "SSL", "disconnected"]):
                last_err = e
                log.warning(f"⚠️ Auth attempt {attempt}/{max_attempts} SSL error: {err[:100]}")
                if attempt < max_attempts:
                    time.sleep(4 * attempt)
                    continue
            raise

        finally:
            try:
                session.close()
            except Exception:
                pass

    raise ConnectionError(f"Failed to authenticate after {max_attempts} attempts: {last_err}")


def get_token(force: bool = False) -> str:
    """
    Thread-safe token getter.

    - Normal call: returns cached if valid.
    - force=True: used after a 401. Still coalesced — a burst of forced
      calls within 60s gets the same freshly-issued token, not 50 logins.
    """
    global _cached_token, _cached_at

    with _token_lock:
        now = time.time()

        # Coalesce window: if we refreshed recently, reuse the result.
        if _cached_token and (now - _cached_at) < _REFRESH_COALESCE_WINDOW:
            return _cached_token

        if not force and _cached_token and _is_token_valid(_cached_token):
            return _cached_token

        if not force:
            load_dotenv(dotenv_path=ENV_PATH, override=True)
            saved = os.getenv("MLX_TOKEN", "").strip()
            if saved and _is_token_valid(saved):
                log.info("🔑 Using saved token from .env")
                _cached_token = saved
                _cached_at = now
                return saved

        log.info("🔄 Logging in to Multilogin...")
        token = _do_login()
        _cached_token = token
        _cached_at = time.time()
        return token