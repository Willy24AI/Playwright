"""
deep_diagnostic.py
------------------
Tests multiple angles to figure out WHY Google is failing.

Hypothesis checks:
  A. Is YOUR network reaching Google directly?
  B. Does raw Python requests (no browser) reach Google through proxy?
  C. Does Playwright reach Google WITHOUT any proxy?
  D. Does Playwright reach Google WITH the proxy?
  E. Does the proxy still work for non-Google Google-like sites?

If A fails → your network/ISP is the issue
If A works, B fails → proxy-level Google block
If A works, B works, C works, D fails → Chromium+proxy combo issue
If A works, B works, C fails → Playwright/Chromium issue
"""

import asyncio
import requests
from playwright.async_api import async_playwright

PROXY_HOST = "9.142.203.168"  # One of your fresh proxies
PROXY_PORT = "6335"
USER = "bozvesah"
PASS = "e5n7zbamrk1z"

TESTS_PASSED = 0
TESTS_FAILED = 0


def log(label, ok, detail=""):
    global TESTS_PASSED, TESTS_FAILED
    icon = "✅" if ok else "❌"
    print(f"{icon} {label}  {detail}")
    if ok:
        TESTS_PASSED += 1
    else:
        TESTS_FAILED += 1


def test_a_direct_network():
    """Your Windows reaching Google directly — no proxy."""
    print("\n[A] Testing YOUR direct connection to Google (no proxy)...")
    try:
        r = requests.get("https://www.google.com", timeout=10)
        log(f"A1. Direct google.com", r.status_code == 200,
            f"HTTP {r.status_code}, {len(r.content)} bytes")
    except Exception as e:
        log("A1. Direct google.com", False, f"{type(e).__name__}: {str(e)[:80]}")

    try:
        r = requests.get("https://www.youtube.com", timeout=10)
        log(f"A2. Direct youtube.com", r.status_code == 200,
            f"HTTP {r.status_code}")
    except Exception as e:
        log("A2. Direct youtube.com", False, f"{type(e).__name__}: {str(e)[:80]}")


def test_b_python_via_proxy():
    """Python requests through proxy, targeting Google."""
    print("\n[B] Testing Python requests → proxy → Google...")
    proxy_url = f"http://{USER}:{PASS}@{PROXY_HOST}:{PROXY_PORT}"
    proxies = {"http": proxy_url, "https": proxy_url}

    try:
        r = requests.get("https://www.google.com", proxies=proxies, timeout=15)
        log(f"B1. Proxied google.com", r.status_code == 200,
            f"HTTP {r.status_code}, {len(r.content)} bytes")
    except Exception as e:
        log("B1. Proxied google.com", False, f"{type(e).__name__}: {str(e)[:80]}")

    try:
        r = requests.get("https://api.ipify.org", proxies=proxies, timeout=15)
        log(f"B2. Proxied api.ipify.org", r.status_code == 200,
            f"Egress IP: {r.text.strip()}")
    except Exception as e:
        log("B2. Proxied api.ipify.org", False, f"{type(e).__name__}: {str(e)[:80]}")


async def test_c_playwright_no_proxy():
    """Playwright Chromium with NO proxy — goes direct through your network."""
    print("\n[C] Testing Playwright without proxy → Google...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            resp = await page.goto("https://www.google.com", timeout=20000,
                                    wait_until="domcontentloaded")
            title = await page.title()
            log("C1. Playwright (no proxy) google.com",
                resp.status == 200,
                f"HTTP {resp.status}, title: '{title[:40]}'")
        except Exception as e:
            log("C1. Playwright (no proxy) google.com",
                False, f"{type(e).__name__}: {str(e)[:80]}")
        finally:
            await browser.close()


async def test_d_playwright_via_proxy():
    """Playwright Chromium WITH proxy → Google."""
    print("\n[D] Testing Playwright WITH proxy → Google...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            proxy={
                "server": f"http://{PROXY_HOST}:{PROXY_PORT}",
                "username": USER,
                "password": PASS,
            }
        )
        try:
            page = await browser.new_page()
            resp = await page.goto("https://www.google.com", timeout=20000,
                                    wait_until="domcontentloaded")
            title = await page.title()
            log("D1. Playwright (with proxy) google.com",
                resp.status == 200,
                f"HTTP {resp.status}, title: '{title[:40]}'")
        except Exception as e:
            log("D1. Playwright (with proxy) google.com",
                False, f"{type(e).__name__}: {str(e)[:80]}")
        finally:
            await browser.close()


async def test_e_other_heavy_sites():
    """Test proxy with OTHER heavy sites to see if it's Google-specific."""
    print("\n[E] Testing proxy with OTHER heavy sites (not Google)...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            proxy={
                "server": f"http://{PROXY_HOST}:{PROXY_PORT}",
                "username": USER,
                "password": PASS,
            }
        )
        urls = [
            "https://www.cnn.com",
            "https://www.reddit.com",
            "https://www.amazon.com",
            "https://duckduckgo.com",
            "https://www.bing.com",
        ]
        for url in urls:
            try:
                page = await browser.new_page()
                resp = await page.goto(url, timeout=15000,
                                        wait_until="domcontentloaded")
                log(f"E. {url}", resp.status < 400,
                    f"HTTP {resp.status}")
                await page.close()
            except Exception as e:
                log(f"E. {url}", False, f"{type(e).__name__}")
        await browser.close()


async def main():
    print("="*70)
    print("DEEP DIAGNOSTIC — Finding the REAL problem")
    print("="*70)

    test_a_direct_network()
    test_b_python_via_proxy()
    await test_c_playwright_no_proxy()
    await test_d_playwright_via_proxy()
    await test_e_other_heavy_sites()

    print("\n" + "="*70)
    print(f"RESULTS: {TESTS_PASSED} passed, {TESTS_FAILED} failed")
    print("="*70)
    print("""
INTERPRETATION KEY:
  A fails       → your network can't reach Google (ISP issue, DNS, etc.)
  A passes, B fails → proxy-level Google block confirmed
  A+B pass, C fails → Playwright itself is broken
  A+B+C pass, D fails → Playwright+proxy combo issue (common bug)
  D fails but E (other heavy sites) passes → Google-specific proxy block
  D fails AND E fails → proxy isn't handling heavy pages at all
    """)


if __name__ == "__main__":
    asyncio.run(main())