"""
protocol_test.py
----------------
Tests whether your Webshare proxy responds to HTTP, SOCKS5, or both.
Use this to figure out which protocol MLX should be configured with.

Requires: pip install requests requests[socks]
"""

import requests

# The proxy MLX reports for PR-0011 (confirmed in your Webshare list)
PROXY = "9.142.203.168:6335"
USER = "bozvesah"
PASS = "e5n7zbamrk1z"

# Also test the proxy the database has for PR-0011
PROXY2 = "45.56.179.53:9257"


def test(host_port, scheme):
    """Test one proxy with one protocol scheme."""
    proxy_url = f"{scheme}://{USER}:{PASS}@{host_port}"
    try:
        r = requests.get(
            "https://api.ipify.org",
            proxies={"http": proxy_url, "https": proxy_url},
            timeout=12,
        )
        return f"  ✅ {scheme.upper():8s}  OK  Egress IP: {r.text.strip()}"
    except requests.exceptions.ProxyError as e:
        return f"  ❌ {scheme.upper():8s}  ProxyError: {str(e)[:100]}"
    except requests.exceptions.ConnectTimeout:
        return f"  ❌ {scheme.upper():8s}  Connection timeout (proxy ignoring the protocol)"
    except requests.exceptions.ReadTimeout:
        return f"  ❌ {scheme.upper():8s}  Read timeout"
    except Exception as e:
        return f"  ❌ {scheme.upper():8s}  {type(e).__name__}: {str(e)[:90]}"


def full_test(host_port, label):
    print(f"\n=== {label}: {host_port} ===")
    print(test(host_port, "http"))
    print(test(host_port, "https"))
    print(test(host_port, "socks5"))
    print(test(host_port, "socks5h"))


if __name__ == "__main__":
    full_test(PROXY,  "MLX-configured proxy")
    full_test(PROXY2, "DB-configured proxy")
    print()
    print("KEY:")
    print("  ✅ = protocol works for real traffic (not just connection test)")
    print("  ❌ = this protocol won't work; don't configure MLX with it")