"""
google_signin.py - Google Account Login Orchestrator for Multilogin X

This script:
1. Fetches profiles from Supabase that need Google login
2. Opens each profile in Multilogin X via the Launcher API
3. Signs into Google with stored credentials
4. Handles challenges (recovery email, passkey intercept, nags)
5. Does a quick post-login warmup
6. Updates profile status in Supabase

Requirements:
- Multilogin X desktop app running and connected
- Profiles created with mla_uuid
- google_email, google_password, google_recovery in Supabase
- pip install truststore
"""

import os
import hashlib
import asyncio
import random
import re
import time
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

# Fix SSL: Use Windows native certificate store instead of Python's bundled OpenSSL.
# This resolves SSLV3_ALERT_BAD_RECORD_MAC errors when Multilogin X desktop app is running.
import truststore
truststore.inject_into_ssl()

import httpx
from supabase import create_client
from playwright.async_api import async_playwright

# ==========================================
# CONFIGURATION
# ==========================================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

MLX_EMAIL = os.getenv("MLX_EMAIL")
MLX_PASSWORD = os.getenv("MLX_PASSWORD")
MLX_FOLDER_ID = os.getenv("MLX_FOLDER_ID")

# Multilogin X Launcher API (local)
MLX_LAUNCHER = "https://launcher.mlx.yt:45001/api/v2"

# Performance Settings
MAX_CONCURRENT = 3               # Keep low for Google login
TOKEN_REFRESH_INTERVAL = 900     # 15 minutes
CAPTCHA_TIMEOUT = 120            # Seconds to wait for manual CAPTCHA solve
PROXY_WARMUP_DELAY = 5           # Seconds to wait for proxy to initialize after browser launch
NAVIGATION_RETRIES = 3           # Retry count for ERR_INVALID_AUTH_CREDENTIALS

if not all([SUPABASE_URL, SUPABASE_KEY, MLX_EMAIL, MLX_PASSWORD, MLX_FOLDER_ID]):
    raise ValueError("Missing credentials in .env")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==========================================
# TOKEN MANAGEMENT
# ==========================================
class TokenManager:
    def __init__(self):
        self.token = None
        self.last_refresh = 0
    
    def get_token(self) -> str:
        current_time = time.time()
        if self.token is None or (current_time - self.last_refresh) > TOKEN_REFRESH_INTERVAL:
            self._refresh_token()
        return self.token
    
    def _refresh_token(self):
        url = "https://api.multilogin.com/user/signin"
        payload = {
            "email": MLX_EMAIL,
            "password": hashlib.md5(MLX_PASSWORD.encode()).hexdigest()
        }
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        
        for attempt in range(1, 6):
            try:
                with httpx.Client(verify=False, trust_env=False, timeout=30) as client:
                    response = client.post(url, json=payload, headers=headers)
                    response.raise_for_status()
                    self.token = response.json()['data']['token']
                    self.last_refresh = time.time()
                    print(f"🔑 MLX Token refreshed")
                    return
            except Exception as e:
                print(f"⚠️ Token refresh {attempt}/5 failed: {e}")
                time.sleep(2)
        
        raise Exception("Failed to refresh MLX token")

token_manager = TokenManager()

# ==========================================
# HUMAN BEHAVIOR SIMULATION
# ==========================================
async def random_delay(min_sec=0.5, max_sec=1.5):
    await asyncio.sleep(random.uniform(min_sec, max_sec))

async def human_type(element, text):
    """Types character by character with random delays."""
    await element.focus()
    for char in text:
        await element.type(char, delay=random.randint(50, 150))

async def handle_nags(page):
    """Dismisses post-login 'Protect your account' nag screens."""
    nag_keywords = ["Not now", "Skip", "No thanks", "Remind me later", "Done", "I'll do it later"]
    
    for _ in range(3):
        await asyncio.sleep(2)
        for keyword in nag_keywords:
            try:
                nag_btn = page.get_by_role("button", name=re.compile(f"^{keyword}$", re.IGNORECASE))
                if await nag_btn.count() > 0 and await nag_btn.first.is_visible():
                    print(f"      ↪ Dismissing '{keyword}' nag...")
                    await nag_btn.first.click()
                    await page.wait_for_load_state("networkidle", timeout=10000)
            except:
                pass

async def handle_try_another_way(page):
    """Clicks 'Try another way' if Google asks for Passkey or Phone Tap."""
    try:
        alt_btn = page.locator("text=Try another way")
        if await alt_btn.count() > 0 and await alt_btn.first.is_visible():
            print("      ↪ Clicking 'Try another way'...")
            await alt_btn.first.click()
            await page.wait_for_load_state("networkidle", timeout=10000)
            return True
    except:
        pass
    return False

async def quick_post_login_warmup(page):
    """Quick warmup after successful login to establish session cookies."""
    print("   → Quick post-login warmup...")
    
    warmup_sites = [
        "https://www.google.com",
        "https://www.youtube.com",
        "https://mail.google.com",
    ]
    
    for site in random.sample(warmup_sites, 2):
        try:
            await page.goto(site, wait_until="domcontentloaded", timeout=15000)
            await random_delay(2, 4)
            
            # Scroll a bit
            await page.mouse.wheel(0, random.randint(200, 400))
            await random_delay(1, 2)
        except:
            pass
    
    print("   ✓ Warmup complete")

async def navigate_with_retry(page, url, profile_name, max_retries=NAVIGATION_RETRIES):
    """Navigate to a URL with retries for proxy auth errors."""
    for attempt in range(1, max_retries + 1):
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            return True
        except Exception as e:
            error_msg = str(e)
            if "ERR_INVALID_AUTH_CREDENTIALS" in error_msg:
                if attempt < max_retries:
                    wait_time = attempt * 3  # 3s, 6s, 9s
                    print(f"   ⚠️ Proxy auth error (attempt {attempt}/{max_retries}), waiting {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    print(f"   ❌ Proxy auth failed after {max_retries} attempts")
                    return False
            elif "ERR_PROXY_CONNECTION_FAILED" in error_msg or "ERR_TUNNEL_CONNECTION_FAILED" in error_msg:
                print(f"   ❌ Proxy connection failed completely")
                return False
            else:
                raise  # Re-raise non-proxy errors
    return False

async def click_next_button(page):
    """Click the Next button on Google sign-in pages using multiple strategies."""
    # Strategy 1: Click button with text "Next"
    try:
        next_btn = page.get_by_role("button", name="Next")
        if await next_btn.count() > 0 and await next_btn.first.is_visible():
            await next_btn.first.click()
            return True
    except:
        pass
    
    # Strategy 2: Click by ID (Google's identifierNext / passwordNext)
    for btn_id in ["identifierNext", "passwordNext"]:
        try:
            btn = page.locator(f"#{btn_id}")
            if await btn.count() > 0 and await btn.first.is_visible():
                await btn.first.click()
                return True
        except:
            pass
    
    # Strategy 3: Press Enter as fallback
    await page.keyboard.press("Enter")
    return True

# ==========================================
# GOOGLE LOGIN LOGIC
# ==========================================
async def login_to_google(page, email: str, password: str, recovery: str, profile_name: str) -> str:
    """
    Perform Google login with human-like behavior.
    
    Returns status: "logged_in", "pva_locked", "captcha_locked", "proxy_error", "error"
    """
    
    # ==========================================
    # ZONE 1: Email Entry
    # ==========================================
    print("   → Navigating to Google Sign-In...")
    
    nav_ok = await navigate_with_retry(page, "https://accounts.google.com/signin", profile_name)
    if not nav_ok:
        return "proxy_error"
    
    await random_delay(1, 2)
    
    # Check if already logged in
    if "myaccount.google.com" in page.url:
        print("   ✓ Already logged in!")
        return "logged_in"
    
    # Find and fill email
    try:
        await page.wait_for_selector('input[type="email"]', state="visible", timeout=10000)
    except:
        # Maybe already past email screen or different flow
        pass
    
    email_input = await page.query_selector('input[type="email"]')
    if not email_input:
        email_input = await page.query_selector('#identifierId')
    
    if email_input:
        print("   → Entering email...")
        await human_type(email_input, email)
        await random_delay(0.5, 1.0)
        
        # Click Next button (more reliable than just pressing Enter)
        await click_next_button(page)
        
        # Wait for the page to leave the email screen.
        # Instead of networkidle (unreliable), wait for password field OR error/challenge.
        print("   → Waiting for password screen...")
        password_appeared = False
        for wait_attempt in range(3):
            try:
                # Wait for password field to appear (Google animates this transition)
                await page.wait_for_selector('input[type="password"]', state="visible", timeout=15000)
                password_appeared = True
                break
            except:
                # Check if something else happened instead of password screen
                current_url = page.url
                
                # Already logged in?
                if "myaccount.google.com" in current_url:
                    print("   ✓ Already logged in!")
                    return "logged_in"
                
                # Security challenge?
                if "challenge" in current_url or "speedbump" in current_url:
                    print("   ⚠️ Challenge detected after email")
                    break
                
                # Check for CAPTCHA
                page_content = await page.content()
                has_captcha = any(marker in page_content.lower() for marker in [
                    "recaptcha", "captcha-form", "g-recaptcha", "rc-anchor",
                    "solve this puzzle", "verify you are a human"
                ])
                if has_captcha:
                    print(f"   ⚠️ CAPTCHA Detected! You have {CAPTCHA_TIMEOUT}s to solve it manually...")
                    try:
                        await page.wait_for_selector('input[type="password"]', timeout=CAPTCHA_TIMEOUT * 1000)
                        password_appeared = True
                    except:
                        print("   ❌ CAPTCHA timeout")
                        return "captcha_locked"
                    break
                
                # Check if email was rejected
                try:
                    error_el = page.locator("text=Couldn't find your Google Account")
                    if await error_el.count() > 0 and await error_el.first.is_visible():
                        print("   ❌ Google Account not found")
                        return "error"
                except:
                    pass
                
                # Still on identifier page - maybe Next didn't register, try again
                if "identifier" in current_url and wait_attempt < 2:
                    print(f"   ⚠️ Still on email page, retrying Next click (attempt {wait_attempt + 2}/3)...")
                    await click_next_button(page)
                    await random_delay(1, 2)
                    continue
                
                # Give up
                if "identifier" in current_url:
                    print("   ❌ Stuck on email page after 3 attempts")
                    return "error"
                
                print(f"   ⚠️ Unexpected state after email, URL: {current_url[:60]}")
                break
    else:
        print("   ⚠️ Could not find email input")
        return "error"
    
    await random_delay(1, 2)
    
    # Handle Passkey/Phone intercept (may appear before password)
    if not password_appeared:
        await handle_try_another_way(page)
        
        # Click "Enter your password" if shown
        try:
            pwd_option = page.locator("text='Enter your password'")
            if await pwd_option.count() > 0:
                await pwd_option.first.click()
                await page.wait_for_load_state("networkidle", timeout=10000)
        except:
            pass
        
        # One more try for password field
        try:
            await page.wait_for_selector('input[type="password"]', state="visible", timeout=10000)
            password_appeared = True
        except:
            if "challenge" in page.url or "speedbump" in page.url:
                print("   ❌ Security challenge before password")
                return "pva_locked"
            print("   ❌ Password field not found")
            return "error"
    
    # ==========================================
    # ZONE 2: Password Entry
    # ==========================================
    
    password_input = await page.query_selector('input[type="password"]')
    if password_input:
        print("   → Entering password...")
        await human_type(password_input, password)
        await random_delay(0.5, 1.0)
        
        # Click Next button
        await click_next_button(page)
        
        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except:
            pass
    else:
        return "error"
    
    await random_delay(2, 4)
    
    # ==========================================
    # ZONE 3: Verification Challenges
    # ==========================================
    current_url = page.url
    
    if "challenge" in current_url or "speedbump" in current_url:
        print("   ⚠️ Verification challenge triggered")
        
        # Try to get past phone/passkey requirement
        await handle_try_another_way(page)
        await random_delay(1, 2)
        
        # Look for recovery email option
        try:
            recovery_option = page.get_by_text(re.compile("Confirm your recovery email", re.IGNORECASE))
            if await recovery_option.count() > 0 and recovery:
                print("      ↪ Using recovery email...")
                await recovery_option.first.click()
                await page.wait_for_load_state("networkidle", timeout=10000)
                
                # Enter recovery email
                await page.wait_for_selector('input[type="email"]', state="visible", timeout=10000)
                rec_input = await page.query_selector('input[type="email"]')
                if rec_input:
                    await human_type(rec_input, recovery)
                    await page.keyboard.press("Enter")
                    await page.wait_for_load_state("networkidle", timeout=15000)
                    await random_delay(2, 3)
            else:
                print("   ❌ Recovery email option not available - Hard PVA lock")
                return "pva_locked"
        except Exception as e:
            print(f"   ❌ Challenge handling failed: {str(e)[:50]}")
            return "pva_locked"
    
    # ==========================================
    # ZONE 4: Post-Login Handling
    # ==========================================
    await handle_nags(page)
    await random_delay(2, 3)
    
    # Final status check
    current_url = page.url
    
    if any(x in current_url for x in ["myaccount.google.com", "mail.google.com", "google.com/search"]):
        print("   ✅ Login successful!")
        return "logged_in"
    elif "challenge" in current_url or "speedbump" in current_url or "rejected" in current_url:
        print("   ❌ Still stuck in challenge")
        return "pva_locked"
    elif "accounts.google.com" in current_url and "signin" not in current_url:
        # Probably logged in but on a different Google page
        print("   ✅ Login appears successful")
        return "logged_in"
    else:
        print(f"   ⚠️ Unknown state, URL: {current_url[:60]}")
        # If no active challenge, assume success
        return "logged_in"

# ==========================================
# PROFILE PROCESSING
# ==========================================
async def process_profile(profile_data, worker_id):
    """Process a single profile: login to Google."""
    
    mla_uuid = profile_data.get('mla_uuid')
    db_id = profile_data.get('id')
    profile_name = profile_data.get('profile_id', 'Unknown')
    email = profile_data.get('google_email')
    password = profile_data.get('google_password')
    recovery = profile_data.get('google_recovery', '')
    
    if not mla_uuid or not email or not password:
        print(f"[{profile_name}] ❌ Missing credentials")
        supabase.table('profiles').update({'status': 'error'}).eq('id', db_id).execute()
        return
    
    token = token_manager.get_token()
    
    # Stagger start
    await asyncio.sleep(worker_id * 3)
    
    # MLX API endpoints
    start_url = f"{MLX_LAUNCHER}/profile/f/{MLX_FOLDER_ID}/p/{mla_uuid}/start?automation_type=playwright&headless_mode=false"
    stop_url = f"{MLX_LAUNCHER}/profile/f/{MLX_FOLDER_ID}/p/{mla_uuid}/stop"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    
    browser = None
    final_status = "error"
    
    try:
        print(f"\n{'='*50}")
        print(f"[Worker {worker_id}] {profile_name} ({email})")
        print(f"{'='*50}")
        
        # Start Multilogin profile
        async with httpx.AsyncClient(verify=False, trust_env=False, timeout=60) as client:
            resp = await client.get(start_url, headers=headers)
        
        if resp.status_code != 200:
            error_text = resp.text[:120]
            if "GET_DIRECT_CONNECTION_IP_ERROR" in error_text:
                print(f"[{profile_name}] ⚠️ Proxy not available - skipping")
                final_status = "proxy_error"
            else:
                print(f"[{profile_name}] ❌ Failed to start: {error_text}")
                final_status = "error"
            supabase.table('profiles').update({
                'status': final_status,
                'last_used_at': datetime.now(timezone.utc).isoformat()
            }).eq('id', db_id).execute()
            return
        
        port = resp.json().get("data", {}).get("port")
        if not port:
            print(f"[{profile_name}] ❌ No CDP port returned")
            supabase.table('profiles').update({'status': 'error'}).eq('id', db_id).execute()
            return
        
        print(f"[{profile_name}] 🚀 Browser started on port {port}")
        
        # Wait for proxy to fully initialize before connecting
        print(f"[{profile_name}] ⏳ Waiting {PROXY_WARMUP_DELAY}s for proxy to initialize...")
        await asyncio.sleep(PROXY_WARMUP_DELAY)
        
        # Connect Playwright
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
            context = browser.contexts[0]
            context.set_default_timeout(30000)
            
            page = context.pages[0] if context.pages else await context.new_page()
            
            # Perform login
            login_result = await login_to_google(page, email, password, recovery, profile_name)
            
            if login_result == "logged_in":
                # Do quick warmup after successful login
                await quick_post_login_warmup(page)
                final_status = "available"  # Ready for use
            elif login_result == "pva_locked":
                final_status = "pva_locked"
            elif login_result == "captcha_locked":
                final_status = "captcha_locked"
            elif login_result == "proxy_error":
                final_status = "proxy_error"
            else:
                final_status = "error"
            
            await browser.close()
            browser = None
    
    except Exception as e:
        print(f"[{profile_name}] ❌ Error: {str(e)[:80]}")
        final_status = "error"
    
    finally:
        if browser:
            try:
                await browser.close()
            except:
                pass
        
        # Stop Multilogin profile
        try:
            async with httpx.AsyncClient(verify=False, timeout=15) as client:
                await client.get(stop_url, headers=headers)
            print(f"[{profile_name}] 🛑 Profile stopped, status: {final_status}")
        except:
            pass
        
        # Update database
        supabase.table('profiles').update({
            'status': final_status,
            'last_used_at': datetime.now(timezone.utc).isoformat()
        }).eq('id', db_id).execute()

# ==========================================
# ATOMIC PROFILE LOCKING
# ==========================================
async def get_and_lock_profile(remaining_count):
    """Atomically get and lock an available profile for login."""
    if remaining_count is not None and remaining_count <= 0:
        return None
        
    try:
        # Get profiles that need login (available but not yet logged in)
        response = supabase.table('profiles')\
            .select('*')\
            .eq('status', 'available')\
            .not_.is_('mla_uuid', 'null')\
            .not_.is_('google_email', 'null')\
            .limit(1)\
            .execute()
        
        if not response.data:
            return None
        
        profile = response.data[0]
        
        # Atomic lock
        update_response = supabase.table('profiles')\
            .update({'status': 'in_use'})\
            .eq('id', profile['id'])\
            .eq('status', 'available')\
            .execute()
        
        if update_response.data and len(update_response.data) > 0:
            return profile
        return None
        
    except Exception as e:
        print(f"⚠️ Lock error: {e}")
        return None

# ==========================================
# WORKER
# ==========================================
# Shared counter for TEST_LIMIT
processed_count = 0
processed_lock = asyncio.Lock()

async def worker(worker_id, semaphore, test_limit=None):
    """Worker that processes profiles."""
    global processed_count
    
    while True:
        # Check if we've hit the test limit
        if test_limit is not None:
            async with processed_lock:
                if processed_count >= test_limit:
                    print(f"[Worker {worker_id}] ✅ Test limit ({test_limit}) reached. Done.")
                    break
        
        async with semaphore:
            profile = await get_and_lock_profile(None)
            
            if not profile:
                await asyncio.sleep(1)
                
                # Check if any profiles left
                check = supabase.table('profiles')\
                    .select('id')\
                    .eq('status', 'available')\
                    .not_.is_('mla_uuid', 'null')\
                    .not_.is_('google_email', 'null')\
                    .limit(1)\
                    .execute()
                
                if not check.data:
                    print(f"[Worker {worker_id}] ✅ No more profiles. Done.")
                    break
                continue
            
            # Increment counter
            async with processed_lock:
                if test_limit is not None and processed_count >= test_limit:
                    # Release the profile back
                    supabase.table('profiles').update({'status': 'available'}).eq('id', profile['id']).execute()
                    break
                processed_count += 1
                current = processed_count
            
            print(f"[Worker {worker_id}] Processing {current}/{test_limit if test_limit else '∞'}")
            await process_profile(profile, worker_id)
            await asyncio.sleep(random.uniform(3, 6))  # Random delay between profiles

# ==========================================
# MAIN
# ==========================================
async def main():
    import warnings
    warnings.filterwarnings("ignore", message="Unverified HTTPS request")
    
    print("\n" + "="*50)
    print("🔑 GOOGLE LOGIN ORCHESTRATOR")
    print("="*50)
    print(f"✓ Multilogin X Launcher API")
    print(f"✓ Human-like typing & behavior")
    print(f"✓ Challenge handling (recovery email)")
    print(f"✓ Post-login warmup")
    print(f"✓ Proxy warmup: {PROXY_WARMUP_DELAY}s delay")
    print(f"✓ Navigation retries: {NAVIGATION_RETRIES}")
    print(f"✓ Max {MAX_CONCURRENT} concurrent browsers")
    print("="*50 + "\n")
    
    # Authenticate
    try:
        token_manager.get_token()
        print("✅ Authenticated with Multilogin X\n")
    except Exception as e:
        print(f"❌ Auth failed: {e}")
        return
    
    # ==========================================
    # TEST MODE: Limit to 10 profiles
    # ==========================================
    TEST_LIMIT = None  # Set to None for all profiles
    
    # Count profiles
    count = supabase.table('profiles')\
        .select('id', count='exact')\
        .eq('status', 'available')\
        .not_.is_('mla_uuid', 'null')\
        .not_.is_('google_email', 'null')\
        .execute()
    
    total = count.count if hasattr(count, 'count') else len(count.data)
    print(f"📊 {total} profiles ready for Google login\n")
    
    if total == 0:
        print("No profiles to process.")
        return
    
    # Run workers
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    tasks = [asyncio.create_task(worker(i, semaphore, TEST_LIMIT)) for i in range(MAX_CONCURRENT)]
    await asyncio.gather(*tasks, return_exceptions=True)
    
    print("\n" + "="*50)
    print(f"🎉 GOOGLE LOGIN COMPLETE! Processed {processed_count} profiles.")
    print("="*50)

if __name__ == "__main__":
    # NOTE: Do NOT use WindowsSelectorEventLoopPolicy — it breaks Playwright's
    # connect_over_cdp() on Windows because SelectorEventLoop doesn't support
    # subprocess_exec. The default ProactorEventLoop works for both httpx and Playwright.
    asyncio.run(main())