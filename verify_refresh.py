"""
verify_refresh.py
-----------------
Run this IMMEDIATELY after Webshare refreshes your proxies.

Step 1: Re-download your proxy list from Webshare
  (Go to Webshare dashboard → Static Residential → Proxy List → Download button
   OR use API URL you already have)

Step 2: Save new list as webshare_proxies_NEW.txt in this folder

Step 3: Run this script — it tests 10 random NEW proxies against google.com
  If most pass → refresh worked, you have clean IPs
  If most fail → same block persists (Webshare's entire ASN is flagged)
"""

import asyncio
import random
from playwright.async_api import async_playwright

USER = "bozvesah"
PASS = "e5n7zbamrk1z"
PROXY_FILE = "webshare_proxies_NEW.txt"  # Save the fresh list with this name

# Load proxies
try:
    with open(PROXY_FILE, "r") as f:
        all_proxies = []
        for line in f:
            parts = line.strip().split(":")
            if len(parts) >= 2:
                all_proxies.append((parts[0], parts[1]))
except FileNotFoundError:
    print(f"❌ {PROXY_FILE} not found!")
    print("   Download fresh list from Webshare dashboard first.")
    exit(1)

print(f"✅ Loaded {len(all_proxies)} proxies from {PROXY_FILE}")

# Sample 10 random
random.seed()
sample = random.sample(all_proxies, min(10, len(all_proxies)))


async def test(host, port):
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                proxy={
                    "server": f"http://{host}:{port}",
                    "username": USER,
                    "password": PASS,
                }
            )
            context = await browser.new_context()
            page = await context.new_page()
            start = asyncio.get_event_loop().time()
            try:
                resp = await page.goto("https://www.google.com", timeout=15000,
                                        wait_until="domcontentloaded")
                elapsed = asyncio.get_event_loop().time() - start
                status = resp.status if resp else "?"
                title = await page.title()
                await browser.close()
                return (True, elapsed, status, title[:40])
            except Exception as e:
                elapsed = asyncio.get_event_loop().time() - start
                await browser.close()
                return (False, elapsed, None, type(e).__name__)
    except Exception as e:
        return (False, 0, None, f"BrowserErr: {type(e).__name__}")


async def main():
    print(f"\nTesting 10 random NEW proxies against google.com...")
    print("="*60)

    passed = 0
    failed = 0

    for i, (host, port) in enumerate(sample, 1):
        ok, t, status, detail = await test(host, port)
        if ok:
            print(f"[{i:2d}] {host}:{port:<6}  ✅ {t:.1f}s  HTTP {status}  {detail}")
            passed += 1
        else:
            print(f"[{i:2d}] {host}:{port:<6}  ❌ {t:.1f}s  {detail}")
            failed += 1

    print("="*60)
    rate = passed * 10
    print(f"SUCCESS RATE: {passed}/10 = {rate}%")
    print()
    if passed >= 8:
        print("🎉 GREAT — fresh proxies work with Google.")
        print("   You have a clean slate. NOW is the time to change your strategy.")
    elif passed >= 4:
        print("⚠️ MIXED — some work, some don't. Partial block still present.")
        print("   May need to ask Webshare for another refresh, or change ASN.")
    else:
        print("❌ STILL BLOCKED — even fresh IPs are flagged.")
        print("   Problem is Webshare's ASN-wide block at Google's end.")
        print("   Rotating Residential or different provider needed.")


if __name__ == "__main__":
    asyncio.run(main())