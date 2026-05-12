
import asyncio
from playwright.async_api import async_playwright

USER = "bozvesah"
PASS = "e5n7zbamrk1z"

with open("webshare_proxies_NEW.txt", "r") as f:
    first_line = f.readline().strip()
    parts = first_line.split(":")
    HOST, PORT = parts[0], parts[1]

print(f"Testing FIRST proxy from NEW list: {HOST}:{PORT}")
print()

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            proxy={
                "server": f"http://{HOST}:{PORT}",
                "username": USER,
                "password": PASS,
            }
        )
        context = await browser.new_context()
        page = await context.new_page()

        for url in ["https://api.ipify.org", "https://www.google.com", "https://www.youtube.com"]:
            print(f"\n→ {url}")
            try:
                resp = await page.goto(url, timeout=20000, wait_until="domcontentloaded")
                title = await page.title()
                if "ipify" in url:
                    content = await page.content()
                    import re
                    m = re.search(r'\d+\.\d+\.\d+\.\d+', content)
                    egress = m.group(0) if m else "?"
                    print(f"   ✅ HTTP {resp.status}  Egress IP: {egress}")
                    print(f"   Expected: {HOST}  {'✅ MATCH' if egress == HOST else '⚠️ different'}")
                else:
                    print(f"   ✅ HTTP {resp.status}  Title: '{title[:60]}'")
            except Exception as e:
                print(f"   ❌ FAILED: {str(e)[:120]}")

        print("\nLeaving browser open 8 seconds...")
        await asyncio.sleep(8)
        await browser.close()

asyncio.run(test())
