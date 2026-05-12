"""quick_check.py - 3-angle test to find what is breaking"""
import requests
import random

USER = "bozvesah"
PASS = "e5n7zbamrk1z"

# Test 1: First proxy from list (same as clean_test)
PROXY1 = "138.226.89.245:7433"

# Test 2: Random different proxy from list
with open("webshare_proxies_NEW.txt") as f:
    lines = [l.strip() for l in f if l.strip()]
parts = random.choice(lines).split(":")
PROXY2 = f"{parts[0]}:{parts[1]}"


def test_proxy(host_port, label):
    print(f"\n=== {label}: {host_port} ===")
    proxy_url = f"http://{USER}:{PASS}@{host_port}"
    for target in ["http://httpbin.org/ip", "https://api.ipify.org"]:
        try:
            r = requests.get(
                target,
                proxies={"http": proxy_url, "https": proxy_url},
                timeout=15,
            )
            print(f"  ✅ {target}")
            print(f"     HTTP {r.status_code}: {r.text.strip()[:120]}")
        except requests.exceptions.ProxyError as e:
            print(f"  ❌ {target}")
            print(f"     ProxyError: {str(e)[:200]}")
        except Exception as e:
            print(f"  ❌ {target}")
            print(f"     {type(e).__name__}: {str(e)[:150]}")


# Direct (no proxy) baseline
print("=== BASELINE: NO PROXY (your direct connection) ===")
try:
    r = requests.get("https://api.ipify.org", timeout=10)
    print(f"  ✅ Your real IP: {r.text.strip()}")
except Exception as e:
    print(f"  ❌ {type(e).__name__}: {e}")

test_proxy(PROXY1, "Proxy 1 (first in list)")
test_proxy(PROXY2, "Proxy 2 (random)")

print("\n" + "="*60)
print("INTERPRETATION:")
print("  Direct works + BOTH proxies fail → Webshare auth/propagation issue")
print("  Direct works + Proxy 1 fails, Proxy 2 works → just unlucky pick")
print("  Direct fails → your local network/firewall issue")
print("  407 errors → credentials wrong")
print("  502 errors → Webshare backend issue")