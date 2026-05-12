"""
proxy_health_sample.py
----------------------
Tests 20 random proxies from your Webshare list against google.com.
Gives you hard numbers to tell Webshare support:
  "X out of 20 proxies can reach google.com, Y out of 20 can reach example.com"

This data tells Gabriel exactly what Webshare needs to do for you.
"""

import asyncio
import random
from playwright.async_api import async_playwright

USER = "bozvesah"
PASS = "e5n7zbamrk1z"

# Load your 500 proxies and sample 20 at random
with open("webshare_proxies.txt", "r") as f:
    all_proxies = []
    for line in f:
        line = line.strip()
        if line:
            parts = line.split(":")
            if len(parts) >= 2:
                all_proxies.append((parts[0], parts[1]))

# Seed for reproducibility — same sample each run
random.seed(42)
sample = random.sample(all_proxies, 20)


async def test_proxy(host, port, url, timeout=15000):
    """Test if this proxy can reach this URL. Returns (ok, elapsed_seconds, status/error)."""
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
                resp = await page.goto(url, timeout=timeout, wait_until="domcontentloaded")
                elapsed = asyncio.get_event_loop().time() - start
                status = resp.status if resp else "?"
                await browser.close()
                return (True, elapsed, f"HTTP {status}")
            except Exception as e:
                elapsed = asyncio.get_event_loop().time() - start
                err = type(e).__name__
                await browser.close()
                return (False, elapsed, err)
    except Exception as e:
        return (False, 0, f"BrowserErr: {type(e).__name__}")


async def main():
    print("="*72)
    print(f"Testing 20 random proxies against google.com and example.com")
    print(f"Each test gets 15 seconds max. Total time: ~10 minutes")
    print("="*72)

    google_ok = 0
    google_fail = 0
    example_ok = 0
    example_fail = 0

    for i, (host, port) in enumerate(sample, 1):
        print(f"\n[{i}/20] {host}:{port}")

        # Test google first
        ok, t, msg = await test_proxy(host, port, "https://www.google.com")
        if ok:
            print(f"   google.com:  ✅ {t:.1f}s  {msg}")
            google_ok += 1
        else:
            print(f"   google.com:  ❌ {t:.1f}s  {msg}")
            google_fail += 1

        # Test example.com to see if proxy is alive at all
        ok, t, msg = await test_proxy(host, port, "https://example.com")
        if ok:
            print(f"   example.com: ✅ {t:.1f}s  {msg}")
            example_ok += 1
        else:
            print(f"   example.com: ❌ {t:.1f}s  {msg}")
            example_fail += 1

    print("\n" + "="*72)
    print("SUMMARY")
    print("="*72)
    print(f"google.com:   {google_ok}/20 working  ({google_ok*5}% success rate)")
    print(f"example.com:  {example_ok}/20 working  ({example_ok*5}% success rate)")
    print()
    print("Send these numbers to Webshare support.")
    if google_ok == 0 and example_ok > 15:
        print("→ Clear pattern: proxies are ALIVE but Google specifically blocks them.")
        print("→ Ask Webshare to either swap your IPs or upgrade to Rotating Residential.")
    elif google_ok > 0 and google_ok < 10:
        print("→ Partial Google block. Some IPs still whitelisted.")
        print("→ Ask Webshare to replace the blocked ones.")
    elif google_ok > 15:
        print("→ Proxies mostly working fine. The issue is elsewhere.")


if __name__ == "__main__":
    asyncio.run(main())
