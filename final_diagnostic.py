"""
final_diagnostic.py
-------------------
THE definitive test. Runs 3 tests in sequence:

Test 1: Load google.com from a WARM PROXY (the one you just used)
Test 2: Load google.com from a COLD PROXY (one you haven't touched in days)
Test 3: Load a lightweight search page from the warm proxy

If Test 1 fails but Test 2 succeeds → proxy-level saturation from your recent usage
If Test 2 also fails → deeper issue (IP reputation, Google blocking your ASN, etc.)
If Test 3 works but Test 1 fails → it's page-weight / parallel-connection issue
"""

import asyncio
from playwright.async_api import async_playwright

USER = "bozvesah"
PASS = "e5n7zbamrk1z"

# The proxy you've been hammering for 2 days (PR-0011's proxy in MLX)
WARM_PROXY = ("9.142.203.168", "6335", "WARM — used extensively last 2 days")

# A proxy from the middle of your list that you haven't used at all
# Picking a random one from the downloaded list
COLD_PROXY = ("207.228.7.196", "7378", "COLD — probably unused")


async def load_site(proxy_tuple, url, label):
    host, port, desc = proxy_tuple
    print(f"\n{'='*60}")
    print(f"{label}")
    print(f"Proxy: {host}:{port}  ({desc})")
    print(f"URL: {url}")
    print('='*60)

    async with async_playwright() as p:
        try:
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

            # Track all requests/responses to see what's happening
            responses = []
            failures = []

            page.on("response", lambda r: responses.append((r.status, r.url[:60])))
            page.on("requestfailed", lambda r: failures.append((r.failure, r.url[:60])))

            try:
                start = asyncio.get_event_loop().time()
                resp = await page.goto(url, timeout=30000, wait_until="domcontentloaded")
                elapsed = asyncio.get_event_loop().time() - start
                status = resp.status if resp else "?"
                title = await page.title()
                print(f"✅ LOADED in {elapsed:.1f}s | Status {status}")
                print(f"   Title: '{title[:70]}'")
                print(f"   Requests completed: {len(responses)}  Failures: {len(failures)}")
                if failures[:3]:
                    print("   Sample failures:")
                    for f in failures[:3]:
                        print(f"     - {f[0]} on {f[1]}")
            except Exception as e:
                err = str(e)[:150]
                print(f"❌ FAILED: {err}")
                print(f"   Requests completed before failure: {len(responses)}")
                print(f"   Request failures: {len(failures)}")
                if responses[:5]:
                    print("   First few responses that DID succeed:")
                    for r in responses[:5]:
                        print(f"     {r[0]} {r[1]}")

            await browser.close()
        except Exception as e:
            print(f"❌ BROWSER ERROR: {str(e)[:150]}")


async def main():
    print("\n🔬 FINAL DIAGNOSTIC — three tests to isolate the issue")
    print("Please wait... each test takes up to 30 seconds\n")

    # Test 1: Warm proxy + heavy page (google)
    await load_site(WARM_PROXY, "https://www.google.com",
                    "TEST 1: WARM PROXY → GOOGLE.COM (heavy site)")

    # Test 2: Cold proxy + heavy page (google)
    await load_site(COLD_PROXY, "https://www.google.com",
                    "TEST 2: COLD PROXY → GOOGLE.COM (heavy site)")

    # Test 3: Warm proxy + light page
    await load_site(WARM_PROXY, "https://example.com",
                    "TEST 3: WARM PROXY → EXAMPLE.COM (light site)")

    print("\n" + "="*60)
    print("INTERPRETATION:")
    print("="*60)
    print("Test 1 FAIL + Test 2 PASS  → warm proxy is saturated. Rotate proxies.")
    print("Test 1 FAIL + Test 2 FAIL  → Google blocks your ASN or deeper issue.")
    print("Test 1 FAIL + Test 3 PASS  → heavy-page bandwidth throttling per proxy.")
    print("All FAIL  → something deeper (Chromium/Playwright/Windows stack).")
    print("All PASS  → the issue is specific to MLX's proxy forwarder.")


if __name__ == "__main__":
    asyncio.run(main())