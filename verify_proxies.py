"""
verify_proxies.py
-----------------
Verifies the 5 Oxylabs proxies on your Multilogin profiles — in two phases.

PHASE 1  (config check):  POST https://api.multilogin.com/profile/metas
         Confirms what proxy is STORED on each MLX profile. Fast, no browser
         launch. Answers: "did the partial_update actually save?"

PHASE 2  (routing check): launches each profile, connects over CDP, visits an
         IP-info page. Confirms the proxy ACTUALLY ROUTES and the live exit
         IP / country matches Oxylabs. Answers: "does the proxy really work?"

Cross-checks both against the known Oxylabs Dedicated ISP proxy list.

Run this from the SAME folder as auth.py / mlx_api.py / .env (the folder your
other scripts live in), with the same venv active.

Usage:
  python verify_proxies.py                          # both phases (recommended)
  python verify_proxies.py --config-only            # phase 1 only, fast
  python verify_proxies.py --only PR-0100,PR-0105   # check a subset
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import requests
import urllib3
from dotenv import load_dotenv
from supabase import create_client
import os

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

# Reuse the same proven modules your other scripts use
from auth import get_token

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ===== CONFIG =====
MLX_METAS_URL = "https://api.multilogin.com/profile/metas"
IP_CHECK_URL = "https://ipinfo.io/json"   # returns JSON: {"ip","city","region","country",...}
DEFAULT_PROFILES = ["PR-0100", "PR-0105", "PR-0104", "PR-0103", "PR-0311"]

# Known Oxylabs Dedicated ISP proxy list (from your dashboard).
# Keyed by "host:port" -> (country_name, iso_code, assigned_ip)
OXYLABS_EXPECTED = {
    "disp.oxylabs.io:8001": ("Denmark",       "DK", "205.188.212.35"),
    "disp.oxylabs.io:8002": ("Norway",        "NO", "205.188.156.0"),
    "disp.oxylabs.io:8003": ("Norway",        "NO", "205.188.157.10"),
    "disp.oxylabs.io:8004": ("United States", "US", "92.71.89.30"),
    "disp.oxylabs.io:8005": ("United States", "US", "92.71.90.29"),
}
# ==================


def get_supabase_client():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
    if not url or not key:
        log.error("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in .env")
        sys.exit(1)
    return create_client(url, key)


def fetch_profiles(supabase, only_ids):
    """Pull id, profile_id, mla_uuid, network for the target profiles."""
    query = supabase.table("profiles").select(
        "id, profile_id, mla_uuid, network"
    ).not_.is_("mla_uuid", "null").in_("profile_id", only_ids)
    response = query.execute()
    profiles = response.data or []
    log.info(f"Found {len(profiles)} of {len(only_ids)} requested profiles with MLX UUIDs")

    found_labels = {p["profile_id"] for p in profiles}
    missing = [pid for pid in only_ids if pid not in found_labels]
    if missing:
        log.warning(f"Not found / no mla_uuid: {', '.join(missing)}")
    return profiles


def verdict_for(configured_hostport, live_ip, live_country):
    """Compare a profile's configured proxy + live result against Oxylabs list."""
    expected = OXYLABS_EXPECTED.get(configured_hostport)
    if not expected:
        return "?? configured proxy is not in the known Oxylabs list"
    exp_country_name, exp_iso, exp_ip = expected

    if live_ip is None:
        return f"-- could not verify routing (expected {exp_iso} / {exp_ip})"

    if live_ip == exp_ip:
        return f"OK  exit IP matches ({exp_iso} / {exp_ip})"
    if live_country and live_country.upper() == exp_iso:
        return (f"~~ country matches ({exp_iso}) but IP differs "
                f"(live {live_ip} vs expected {exp_ip})")
    return (f"XX MISMATCH — live {live_country}/{live_ip} "
            f"vs expected {exp_iso}/{exp_ip}")


# ----------------------------------------------------------------------
# PHASE 1 — config check via /profile/metas
# ----------------------------------------------------------------------
def phase1_config_check(token, profiles):
    uuid_to_label = {p["mla_uuid"]: p["profile_id"] for p in profiles}
    ids = list(uuid_to_label.keys())

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }
    body = {"ids": ids}

    log.info("PHASE 1: querying /profile/metas for stored proxy config...")
    try:
        resp = requests.post(MLX_METAS_URL, json=body, headers=headers,
                             verify=False, timeout=30)
    except Exception as e:
        log.error(f"  /profile/metas call failed: {type(e).__name__}: {str(e)[:120]}")
        return {}

    if resp.status_code != 200:
        log.error(f"  /profile/metas returned {resp.status_code}: {resp.text[:200]}")
        return {}

    try:
        data = resp.json()
        profiles_data = data.get("data", {}).get("profiles", [])
    except Exception as e:
        log.error(f"  Could not parse /profile/metas response: {e}")
        return {}

    results = {}
    for pf in profiles_data:
        uuid = pf.get("id")
        label = uuid_to_label.get(uuid, uuid)
        proxy = (pf.get("parameters") or {}).get("proxy") or {}
        host = proxy.get("host", "?")
        port = proxy.get("port", "?")
        results[label] = {
            "host": host,
            "port": port,
            "hostport": f"{host}:{port}",
            "username": proxy.get("username", "?"),
            "type": proxy.get("type", "?"),
        }

    log.info("")
    log.info("=" * 78)
    log.info("PHASE 1 RESULTS — proxy stored on each MLX profile")
    log.info("=" * 78)
    for label in (p["profile_id"] for p in profiles):
        r = results.get(label)
        if not r:
            log.warning(f"  {label:10s}  no proxy data returned by /profile/metas")
            continue
        known = "  (known Oxylabs)" if r["hostport"] in OXYLABS_EXPECTED else "  (NOT in Oxylabs list)"
        log.info(f"  {label:10s}  {r['type']:6s} {r['hostport']:28s} user={r['username']}{known}")
    log.info("=" * 78)
    return results


# ----------------------------------------------------------------------
# PHASE 2 — routing check: launch profile, read live exit IP
# ----------------------------------------------------------------------
def phase2_routing_check(token, profiles):
    from playwright.sync_api import sync_playwright
    from mlx_api import start_profile, stop_profile

    results = {}
    log.info("")
    log.info("PHASE 2: launching each profile to read its live exit IP...")
    log.info("(this opens each browser briefly — leave it alone while it runs)")

    for p in profiles:
        label = p["profile_id"]
        uuid = p["mla_uuid"]
        log.info("")
        log.info(f"  [{label}] launching...")

        ws_url = None
        try:
            ws_url = start_profile(uuid, token)
        except Exception as e:
            log.error(f"  [{label}] start_profile failed: {type(e).__name__}: {str(e)[:120]}")
            results[label] = {"error": f"launch failed: {str(e)[:80]}"}
            continue

        try:
            with sync_playwright() as pw:
                browser = pw.chromium.connect_over_cdp(ws_url, timeout=20000)
                ctx = browser.contexts[0] if browser.contexts else browser.new_context()
                page = ctx.pages[0] if ctx.pages else ctx.new_page()

                # The proxy credentials are injected by MLX slightly AFTER the
                # browser process starts. Hitting the network too early surfaces
                # as ERR_INVALID_AUTH_CREDENTIALS even though the config is fine.
                # So: retry the IP check with backoff, giving the proxy time to
                # finish coming up.
                raw = None
                last_err = None
                for goto_attempt in range(5):
                    try:
                        page.goto(IP_CHECK_URL, wait_until="domcontentloaded", timeout=25000)
                        raw = page.evaluate("() => document.body.innerText")
                        break
                    except Exception as ge:
                        last_err = ge
                        wait = 4 + goto_attempt * 3   # 4s, 7s, 10s, 13s
                        log.info(f"  [{label}] proxy not ready yet "
                                 f"({str(ge)[:50]}...) — waiting {wait}s "
                                 f"(attempt {goto_attempt+1}/5)")
                        time.sleep(wait)

                if raw is None:
                    results[label] = {"error": f"all goto attempts failed: {str(last_err)[:100]}"}
                    log.error(f"  [{label}] still failing after 5 attempts")
                    try:
                        browser.close()
                    except Exception:
                        pass
                    try:
                        stop_profile(uuid, token)
                    except Exception:
                        pass
                    time.sleep(2)
                    continue

                try:
                    info = json.loads(raw)
                    results[label] = {
                        "ip": info.get("ip"),
                        "country": info.get("country"),
                        "city": info.get("city"),
                        "region": info.get("region"),
                        "org": info.get("org"),
                    }
                    log.info(f"  [{label}] live IP: {info.get('ip')}  "
                             f"{info.get('country')}  "
                             f"{info.get('city', '')}/{info.get('region', '')}  "
                             f"{info.get('org', '')}")
                except json.JSONDecodeError:
                    results[label] = {"error": "could not parse IP page",
                                      "raw": raw[:150]}
                    log.warning(f"  [{label}] unexpected IP page content: {raw[:120]}")
                try:
                    browser.close()
                except Exception:
                    pass
        except Exception as e:
            results[label] = {"error": str(e)[:120]}
            log.error(f"  [{label}] routing check failed: {type(e).__name__}: {str(e)[:120]}")
        finally:
            try:
                stop_profile(uuid, token)
            except Exception as e:
                log.warning(f"  [{label}] stop_profile failed: {str(e)[:80]}")
            time.sleep(2)

    return results


# ----------------------------------------------------------------------
# FINAL CROSS-CHECK
# ----------------------------------------------------------------------
def final_report(profiles, config_results, routing_results):
    log.info("")
    log.info("=" * 78)
    log.info("FINAL VERIFICATION — configured vs. live vs. expected")
    log.info("=" * 78)

    all_ok = True
    for p in profiles:
        label = p["profile_id"]
        cfg = config_results.get(label)
        route = routing_results.get(label) if routing_results else None

        if not cfg:
            log.warning(f"  {label:10s}  no config data — cannot verify")
            all_ok = False
            continue

        hostport = cfg["hostport"]

        if route is None:
            # config-only mode
            expected = OXYLABS_EXPECTED.get(hostport)
            if expected:
                log.info(f"  {label:10s}  configured {hostport}  "
                         f"-> expects {expected[1]}/{expected[2]}  (routing not checked)")
            else:
                log.warning(f"  {label:10s}  configured {hostport}  NOT in Oxylabs list")
                all_ok = False
            continue

        if "error" in route:
            log.warning(f"  {label:10s}  configured {hostport}  "
                        f"-- routing check error: {route['error']}")
            all_ok = False
            continue

        v = verdict_for(hostport, route.get("ip"), route.get("country"))
        log.info(f"  {label:10s}  {hostport:28s}  {v}")
        if v.startswith("XX") or v.startswith("??"):
            all_ok = False

    log.info("=" * 78)
    if all_ok:
        log.info("All checked profiles verified OK.")
    else:
        log.info("Some profiles need attention — see lines above.")
    log.info("=" * 78)


def main():
    parser = argparse.ArgumentParser(description="Verify Oxylabs proxies on MLX profiles")
    parser.add_argument("--only", type=str, default=None,
                        help="Comma-separated profile IDs (default: the 5 known profiles)")
    parser.add_argument("--config-only", action="store_true",
                        help="Only run Phase 1 (fast, no browser launches)")
    args = parser.parse_args()

    if args.only:
        only_ids = [x.strip() for x in args.only.split(",") if x.strip()]
    else:
        only_ids = DEFAULT_PROFILES
    log.info(f"Target profiles: {', '.join(only_ids)}")

    # Reference table
    log.info("")
    log.info("Oxylabs reference (from your dashboard):")
    for hp, (cn, iso, ip) in sorted(OXYLABS_EXPECTED.items()):
        log.info(f"  {hp:28s}  {iso}  {cn:15s}  {ip}")
    log.info("")

    log.info("Connecting to Supabase...")
    supabase = get_supabase_client()
    profiles = fetch_profiles(supabase, only_ids)
    if not profiles:
        log.error("No profiles found. Aborting.")
        sys.exit(1)

    log.info("Getting MLX API token...")
    token = get_token()
    log.info("MLX token acquired")
    log.info("")

    config_results = phase1_config_check(token, profiles)

    routing_results = None
    if not args.config_only:
        routing_results = phase2_routing_check(token, profiles)
    else:
        log.info("")
        log.info("--config-only: skipping Phase 2 (routing check).")

    final_report(profiles, config_results, routing_results)


if __name__ == "__main__":
    main()