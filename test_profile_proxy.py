"""
test_profile_proxy.py
---------------------
Tests a specific profile's proxy using its exact credentials from the DB.

This is the critical diagnostic: if this succeeds but MLX says the proxy
is dead, the problem is how MLX is configured. If this fails, the
credentials in your DB don't match the live proxy.

Usage:
    python test_profile_proxy.py PR-0011
"""

import sys
import requests
import urllib3
from profiles_config import get_supabase_client

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def test_proxy(profile_id: str):
    supabase = get_supabase_client()
    r = supabase.table("profiles")\
        .select("profile_id, mla_uuid, network, status")\
        .eq("profile_id", profile_id)\
        .execute()

    if not r.data:
        print(f"❌ Profile {profile_id} not found")
        return

    p = r.data[0]
    net = p.get("network") or {}
    ip = net.get("proxy_ip")
    port = net.get("proxy_port")
    user = net.get("proxy_user")
    pw = net.get("proxy_pass")

    print(f"Profile:   {p['profile_id']}")
    print(f"MLX UUID:  {p.get('mla_uuid')}")
    print(f"Status:    {p.get('status')}")
    print(f"Proxy:     {ip}:{port}")
    print(f"Auth:      {user} / {pw}")
    print()

    if not all([ip, port, user, pw]):
        print("❌ Incomplete proxy credentials in DB")
        return

    proxy_url = f"http://{user}:{pw}@{ip}:{port}"
    proxies = {"http": proxy_url, "https": proxy_url}

    # Test 1: what's our egress IP through this proxy?
    print("[Test 1] GET https://api.ipify.org through proxy")
    try:
        resp = requests.get(
            "https://api.ipify.org?format=json",
            proxies=proxies,
            verify=False,
            timeout=15,
        )
        if resp.status_code == 200:
            egress_ip = resp.json().get("ip")
            print(f"  ✅ Proxy works! Egress IP: {egress_ip}")
            if egress_ip == ip:
                print(f"     (matches proxy IP — direct connection)")
            else:
                print(f"     (routed through proxy — different from {ip})")
        else:
            print(f"  ❌ HTTP {resp.status_code}: {resp.text[:120]}")
    except requests.exceptions.ProxyError as e:
        err = str(e)
        if "407" in err:
            print(f"  ❌ 407 Proxy Authentication Required")
            print(f"     Credentials are WRONG — username/password rejected")
        elif "Cannot connect" in err or "timed out" in err.lower():
            print(f"  ❌ Proxy unreachable: {err[:120]}")
            print(f"     Proxy IP/port may be dead")
        else:
            print(f"  ❌ Proxy error: {err[:200]}")
    except Exception as e:
        print(f"  ❌ {type(e).__name__}: {str(e)[:200]}")

    # Test 2: check if Google is reachable (MLX does this on launch)
    print()
    print("[Test 2] GET https://www.google.com through proxy")
    try:
        resp = requests.get(
            "https://www.google.com",
            proxies=proxies,
            verify=False,
            timeout=15,
        )
        print(f"  ✅ HTTP {resp.status_code}")
    except Exception as e:
        print(f"  ❌ {type(e).__name__}: {str(e)[:200]}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_profile_proxy.py PR-0011")
        sys.exit(1)
    test_proxy(sys.argv[1])