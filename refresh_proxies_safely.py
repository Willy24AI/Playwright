"""
refresh_proxies_safely.py  [v4 — username field corrected]
--------------------------
FIX from v3: changed proxy field 'login' to 'username'.
Verified against:
  1. Multilogin's official GitHub: github.com/multilogin/quick_profile_proxy
  2. Multilogin docs at multilogin.com/help/updating-a-profile-with-postman
  Both use 'username', NOT 'login'. Support gave incorrect info.

Endpoint: POST https://api.multilogin.com/profile/partial_update
Body:    {
  "profile_id": "<mla_uuid>",
  "proxy": {
    "type": "http",
    "host": "<ip>",
    "port": <int>,
    "username": "<user>",
    "password": "<pass>"
  }
}

Order of operations per profile:
  1. POST to MLX
  2. If MLX succeeds, UPDATE Supabase
  3. If MLX fails, SKIP Supabase (prevents DB/MLX drift)

Usage:
  python refresh_proxies_safely.py --only PR-0011 --dry-run
  python refresh_proxies_safely.py --only PR-0011
  python refresh_proxies_safely.py --only PR-0011,PR-0211
  python refresh_proxies_safely.py
"""

import argparse
import logging
import os
import random
import sys
import time
from pathlib import Path

import requests
import urllib3
from dotenv import load_dotenv
from supabase import create_client

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ===== CONFIG =====
PROXY_FILE = "webshare_proxies_NEW.txt"
PROXY_USER = "bozvesah"
PROXY_PASS = "e5n7zbamrk1z"
PROXY_TYPE = "http"

MLX_API_BASE = "https://api.multilogin.com"
MLX_UPDATE_URL = f"{MLX_API_BASE}/profile/partial_update"
MLX_RATE_LIMIT_SLEEP = 1.5
MLX_SSL_RETRIES = 3
# ==================


def load_new_proxies() -> list:
    if not Path(PROXY_FILE).exists():
        log.error(f"{PROXY_FILE} not found in current directory!")
        sys.exit(1)
    proxies = []
    with open(PROXY_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(":")
            if len(parts) >= 2:
                proxies.append({"host": parts[0], "port": int(parts[1])})
    log.info(f"Loaded {len(proxies)} fresh proxies from {PROXY_FILE}")
    return proxies


def get_supabase_client():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
    if not url or not key:
        log.error("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in .env")
        sys.exit(1)
    return create_client(url, key)


def get_mlx_token() -> str:
    try:
        from auth import get_token
        return get_token(force=False)
    except ImportError:
        log.error("Could not import auth.py - needed for MLX token")
        sys.exit(1)


def fetch_target_profiles(supabase, only_ids=None) -> list:
    query = supabase.table("profiles").select(
        "id, profile_id, mla_uuid, network, status"
    ).not_.is_("mla_uuid", "null")
    if only_ids:
        query = query.in_("profile_id", only_ids)
    response = query.execute()
    profiles = response.data or []
    log.info(f"Found {len(profiles)} profiles with MLX UUIDs")
    return profiles


def assign_proxies_to_profiles(profiles: list, proxies: list) -> list:
    shuffled = proxies.copy()
    random.shuffle(shuffled)
    return [
        {"profile": p, "proxy": shuffled[i % len(shuffled)]}
        for i, p in enumerate(profiles)
    ]


def update_mlx(token, assignment, dry_run=False):
    """
    POST https://api.multilogin.com/profile/partial_update

    Body field names verified against Multilogin's own GitHub:
      github.com/multilogin/quick_profile_proxy/blob/main/main.py
    Uses 'profile_id' for ID and 'username' for proxy auth (NOT 'id' or 'login').
    """
    profile = assignment["profile"]
    proxy = assignment["proxy"]
    profile_name = profile["profile_id"]
    mla_uuid = profile["mla_uuid"]

    if dry_run:
        return (True, f"MLX: {profile_name} ({mla_uuid[:8]}) -> {proxy['host']}:{proxy['port']}", None)

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }
    body = {
        "profile_id": mla_uuid,
        "proxy": {
            "type": PROXY_TYPE,
            "host": proxy["host"],
            "port": proxy["port"],
            "username": PROXY_USER,   # <- CORRECT field name (not 'login')
            "password": PROXY_PASS,
        }
    }

    last_err = None
    for ssl_attempt in range(MLX_SSL_RETRIES):
        try:
            resp = requests.post(MLX_UPDATE_URL, json=body, headers=headers, verify=False, timeout=20)
            if resp.status_code == 200:
                return (True, f"MLX: {profile_name} -> {proxy['host']}:{proxy['port']}", None)
            elif resp.status_code == 401:
                return (False, f"MLX AUTH FAIL: {profile_name} - token expired", "AUTH")
            elif resp.status_code == 429:
                return (False, f"MLX RATE LIMIT: {profile_name}", "RATE")
            else:
                return (False, f"MLX FAIL [{resp.status_code}]: {profile_name} - {resp.text[:200]}", "OTHER")
        except requests.exceptions.SSLError as e:
            last_err = e
            if ssl_attempt < MLX_SSL_RETRIES - 1:
                wait = 2 * (ssl_attempt + 1)
                log.warning(f"    SSL error, retrying in {wait}s (attempt {ssl_attempt+1}/{MLX_SSL_RETRIES})...")
                time.sleep(wait)
                continue
            return (False, f"MLX SSL ERR: {profile_name} - {str(e)[:120]}", "SSL")
        except Exception as e:
            return (False, f"MLX ERR: {profile_name} - {type(e).__name__}: {str(e)[:80]}", "OTHER")

    return (False, f"MLX FAILED after {MLX_SSL_RETRIES} SSL retries: {profile_name}", "SSL")


def update_supabase(supabase, assignment, dry_run=False):
    profile = assignment["profile"]
    proxy = assignment["proxy"]
    profile_name = profile["profile_id"]
    db_id = profile["id"]

    network_data = {
        "proxy_ip": proxy["host"],
        "proxy_port": proxy["port"],
        "proxy_user": PROXY_USER,
        "proxy_pass": PROXY_PASS,
    }

    if dry_run:
        old = profile.get("network") or {}
        old_ip = old.get("proxy_ip", "?")
        old_port = old.get("proxy_port", "?")
        return (True, f"DB: {profile_name}  {old_ip}:{old_port} -> {proxy['host']}:{proxy['port']}")

    try:
        supabase.table("profiles").update({"network": network_data}).eq("id", db_id).execute()
        return (True, f"DB: {profile_name} -> {proxy['host']}:{proxy['port']}")
    except Exception as e:
        return (False, f"DB FAIL: {profile_name} - {type(e).__name__}: {str(e)[:80]}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--only", type=str, default=None)
    parser.add_argument("--skip-db", action="store_true")
    parser.add_argument("--skip-mlx", action="store_true")
    args = parser.parse_args()

    only_ids = None
    if args.only:
        only_ids = [x.strip() for x in args.only.split(",") if x.strip()]
        log.info(f"Limiting to {len(only_ids)} profile(s): {', '.join(only_ids)}")

    if args.dry_run:
        log.info("DRY RUN MODE - no changes will be made")

    proxies = load_new_proxies()
    if len(proxies) < 10:
        log.error(f"Only {len(proxies)} proxies. Aborting - looks wrong.")
        sys.exit(1)

    log.info("Connecting to Supabase...")
    supabase = get_supabase_client()
    profiles = fetch_target_profiles(supabase, only_ids=only_ids)

    if not profiles:
        log.error("No profiles found.")
        sys.exit(1)

    if not args.dry_run and not only_ids and len(profiles) > 5:
        print()
        log.warning(f"About to update {len(profiles)} profiles in MLX and Supabase.")
        log.warning("Order: MLX first, then DB (only if MLX succeeds).")
        log.warning("mla_uuid and status are PRESERVED. Only proxy changes.")
        print()
        response = input("Type 'yes' to proceed: ").strip().lower()
        if response != "yes":
            log.info("Aborted.")
            sys.exit(0)

    mlx_token = None
    if not args.skip_mlx:
        log.info("Getting MLX API token...")
        mlx_token = get_mlx_token()
        log.info("MLX token acquired")

    assignments = assign_proxies_to_profiles(profiles, proxies)
    log.info(f"Assigned {len(assignments)} proxies (shuffled)")
    log.info("")
    log.info("=" * 70)

    mlx_ok = mlx_fail = db_ok = db_fail = db_skipped = 0
    failed = []
    token_refresh_count = 0

    for i, assignment in enumerate(assignments, 1):
        profile_name = assignment["profile"]["profile_id"]
        progress = f"[{i:3d}/{len(assignments)}]"

        # Step 1: MLX first
        mlx_succeeded = False
        if not args.skip_mlx:
            ok, msg, err_code = update_mlx(mlx_token, assignment, dry_run=args.dry_run)

            if not ok and err_code == "AUTH" and token_refresh_count < 3:
                log.info("    Refreshing MLX token...")
                mlx_token = get_mlx_token()
                token_refresh_count += 1
                ok, msg, err_code = update_mlx(mlx_token, assignment, dry_run=args.dry_run)
                if ok:
                    msg += " (after refresh)"

            if ok:
                mlx_ok += 1
                mlx_succeeded = True
                log.info(f"{progress} OK  {msg}")
            else:
                mlx_fail += 1
                log.warning(f"{progress} ERR {msg}")
                failed.append(profile_name)
        else:
            mlx_succeeded = True

        # Step 2: DB only if MLX succeeded
        if not args.skip_db:
            if mlx_succeeded:
                ok, msg = update_supabase(supabase, assignment, dry_run=args.dry_run)
                if ok:
                    db_ok += 1
                    log.info(f"{progress} OK  {msg}")
                else:
                    db_fail += 1
                    log.warning(f"{progress} ERR {msg}")
                    if profile_name not in failed:
                        failed.append(profile_name)
            else:
                db_skipped += 1
                log.info(f"{progress} -- DB skipped (MLX failed): {profile_name}")

        if not args.dry_run and not args.skip_mlx:
            time.sleep(MLX_RATE_LIMIT_SLEEP)

    log.info("")
    log.info("=" * 70)
    log.info("SUMMARY")
    log.info("=" * 70)
    if not args.skip_mlx:
        log.info(f"MLX API:    OK {mlx_ok}   FAIL {mlx_fail}")
    if not args.skip_db:
        log.info(f"Supabase:   OK {db_ok}   FAIL {db_fail}   SKIPPED {db_skipped}")
    if failed:
        log.warning(f"Failed ({len(failed)}): {', '.join(failed[:20])}")
        if len(failed) > 20:
            log.warning(f"   ... and {len(failed) - 20} more")
        log.info("")
        log.info("To retry failed profiles:")
        log.info(f"  python refresh_proxies_safely.py --only {','.join(failed[:10])}")

    if args.dry_run:
        log.info("")
        log.info("DRY RUN. To apply changes, run without --dry-run.")


if __name__ == "__main__":
    main()