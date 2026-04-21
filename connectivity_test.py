"""
connectivity_test.py
--------------------
Isolates where the failure is:
  1. Can we reach api.multilogin.com at all?
  2. Can we actually log in and get a token?
  3. Can we reach the local MLX agent?
  4. Does the local agent accept our token?

Run: python connectivity_test.py
"""

import os
import socket
import ssl
import hashlib
import json
import base64
import time
from pathlib import Path

import requests
import urllib3
from dotenv import load_dotenv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    import truststore
    truststore.inject_into_ssl()
    print("✅ truststore loaded (using Windows cert store)")
except ImportError:
    print("⚠️ truststore not installed")

ENV_PATH = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)


def test_1_dns():
    print("\n[Test 1] DNS resolution for api.multilogin.com")
    try:
        ip = socket.gethostbyname("api.multilogin.com")
        print(f"  ✅ Resolves to: {ip}")
        return True
    except Exception as e:
        print(f"  ❌ DNS failed: {e}")
        return False


def test_2_tcp():
    print("\n[Test 2] TCP connection to api.multilogin.com:443")
    try:
        with socket.create_connection(("api.multilogin.com", 443), timeout=10) as s:
            print(f"  ✅ TCP connected")
        return True
    except Exception as e:
        print(f"  ❌ TCP failed: {e}")
        return False


def test_3_tls():
    print("\n[Test 3] TLS handshake to api.multilogin.com")
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection(("api.multilogin.com", 443), timeout=10) as s:
            with ctx.wrap_socket(s, server_hostname="api.multilogin.com") as ss:
                cipher = ss.cipher()
                print(f"  ✅ TLS OK — cipher: {cipher[0]}, version: {cipher[1]}")
        return True
    except Exception as e:
        print(f"  ❌ TLS failed: {e}")
        print(f"     This suggests antivirus/firewall SSL inspection.")
        return False


def test_4_simple_get():
    print("\n[Test 4] Plain HTTPS GET to api.multilogin.com (no auth)")
    try:
        r = requests.get("https://api.multilogin.com", verify=False, timeout=15)
        print(f"  ✅ HTTP response: {r.status_code}")
        return True
    except Exception as e:
        print(f"  ❌ Request failed: {str(e)[:120]}")
        return False


def test_5_login():
    print("\n[Test 5] Actual login (POST /user/signin)")
    email = os.getenv("MLX_EMAIL", "").strip()
    password = os.getenv("MLX_PASSWORD", "").strip()

    if not email or not password:
        print(f"  ❌ MLX_EMAIL or MLX_PASSWORD missing from .env")
        return None

    print(f"  Email: {email}")
    print(f"  Password length: {len(password)} chars")

    payload = {
        "email": email,
        "password": hashlib.md5(password.encode()).hexdigest(),
    }
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Connection": "close",
    }

    for attempt in range(1, 4):
        try:
            s = requests.Session()
            r = s.post(
                "https://api.multilogin.com/user/signin",
                json=payload,
                headers=headers,
                verify=False,
                timeout=30,
            )
            s.close()

            if r.status_code == 200:
                token = r.json().get("data", {}).get("token", "")
                if token:
                    print(f"  ✅ Login success, token length: {len(token)}")
                    # Decode exp
                    try:
                        parts = token.split(".")
                        padding = "=" * (-len(parts[1]) % 4)
                        decoded = json.loads(base64.b64decode(parts[1] + padding))
                        exp_in = decoded.get("exp", 0) - time.time()
                        print(f"     Token valid for: {exp_in/60:.0f} minutes")
                    except Exception:
                        pass
                    return token
                else:
                    print(f"  ❌ 200 OK but no token in response: {r.text[:200]}")
                    return None
            else:
                print(f"  ⚠️ HTTP {r.status_code}: {r.text[:200]}")
                if r.status_code in (401, 403):
                    print(f"     Credentials are being rejected. Check .env.")
                    return None

        except Exception as e:
            print(f"  ⚠️ Attempt {attempt}/3: {str(e)[:120]}")
            if attempt < 3:
                time.sleep(3)

    print(f"  ❌ Login failed after 3 attempts")
    return None


def test_6_local_agent():
    print("\n[Test 6] Local MLX agent (launcher.mlx.yt:45001)")
    # launcher.mlx.yt resolves to 127.0.0.1
    try:
        ip = socket.gethostbyname("launcher.mlx.yt")
        print(f"  launcher.mlx.yt → {ip} (should be 127.0.0.1)")
    except Exception as e:
        print(f"  ❌ launcher.mlx.yt DNS failed: {e}")
        return False

    try:
        r = requests.get("https://launcher.mlx.yt:45001/api/v1/status",
                         verify=False, timeout=5)
        print(f"  ✅ Local agent responded: HTTP {r.status_code}")
        return True
    except requests.exceptions.ConnectionError as e:
        print(f"  ❌ Local agent not reachable: {str(e)[:100]}")
        print(f"     The Multilogin X desktop app is not running or not listening.")
        return False
    except Exception as e:
        print(f"  ⚠️ {str(e)[:100]}")
        return False


def test_7_agent_with_token(token: str):
    print("\n[Test 7] Local agent accepts our token")
    folder_id = os.getenv("MLX_FOLDER_ID", "").strip()
    if not folder_id:
        print(f"  ❌ MLX_FOLDER_ID not set in .env")
        return

    # Hit a lightweight endpoint that requires auth
    url = f"https://launcher.mlx.yt:45001/api/v2/profile/f/{folder_id}/list"
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}

    try:
        r = requests.get(url, headers=headers, verify=False, timeout=15)
        print(f"  HTTP {r.status_code}")
        if r.status_code == 200:
            print(f"  ✅ Agent accepts token + folder_id")
        elif r.status_code == 401:
            print(f"  ❌ 401 — agent rejects the token")
            print(f"     Possible: token/folder mismatch, or MLX app signed in as different user")
        elif r.status_code == 404:
            print(f"  ⚠️ 404 — folder_id may be wrong")
            print(f"     Response: {r.text[:200]}")
        else:
            print(f"  Response: {r.text[:200]}")
    except Exception as e:
        print(f"  ❌ {str(e)[:120]}")


def main():
    print("=" * 60)
    print("Multilogin Connectivity Diagnostic")
    print("=" * 60)

    if not test_1_dns():
        return
    if not test_2_tcp():
        return
    tls_ok = test_3_tls()
    test_4_simple_get()

    token = test_5_login()

    agent_ok = test_6_local_agent()

    if token and agent_ok:
        test_7_agent_with_token(token)

    print("\n" + "=" * 60)
    print("Diagnosis")
    print("=" * 60)

    if not tls_ok:
        print("• TLS handshake failed → antivirus SSL inspection likely.")
        print("  Fix: disable 'HTTPS scanning' / 'SSL scanning' in your AV settings.")
    if not token:
        print("• Login failed → check MLX_EMAIL/MLX_PASSWORD in .env,")
        print("  or your network is blocking api.multilogin.com.")
    if not agent_ok:
        print("• Local agent not reachable → the Multilogin X desktop app")
        print("  is not running. Open it from the system tray / Start menu.")


if __name__ == "__main__":
    main()