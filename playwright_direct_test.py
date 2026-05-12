"""
playwright_direct_test.py
-------------------------
Tests Playwright + proxy DIRECTLY, bypassing MLX entirely.

This isolates the variable:
- protocol_test.py proved:  Python requests → proxy works
- your farm script fails:   MLX → Playwright → proxy fails
- this test tells us:       Playwright → proxy (no MLX) works or fails

If THIS works:    The bug is 100% in MLX's proxy forwarder
If THIS also fails: The bug is in Playwright + this proxy combo
"""

import asyncio
from playwright.async_api import async_playwright

# The PR-0011 proxy that Webshare confirmed is yours
PROXY_HOST = "9.142.203.168"
PROXY_PORT = "6335"
PROXY_USER = "bozvesah"
PROXY_PASS = "e5n7zbamrk1z"


async def test():
    proxy_config = {
        "server": f"http://{PROXY_HOST}:{PROXY_PORT}",
        "username": PROXY_USER,
        "password": PROXY_PASS,
    }

    print(f"Launching fresh Chromium with proxy {PROXY_HOST}:{PROXY_PORT}")
    print("(No MLX involved — pure Playwright)\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,  # So you can SEE what happens
            proxy=proxy_config,
        )
        context = await browser.new_context()
        page = await context.new_page()

        tests = [
            ("https://api.ipify.org", "What IP does the site see?"),
            ("https://www.google.com", "Does Google load?"),
            ("https://www.youtube.com", "Does YouTube load?"),
        ]

        for url, desc in tests:
            print(f"→ {desc}")
            print(f"   {url}")
            try:
                response = await page.goto(url, timeout=20000)
                status = response.status if response else "?"
                title = await page.title()
                print(f"   ✅ Status {status} | Title: '{title[:60]}'")
            except Exception as e:
                err = str(e)[:120]
                print(f"   ❌ FAILED: {err}")
            print()

        print("Leaving browser open for 10 seconds so you can look around...")
        await asyncio.sleep(10)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(test())