"""
check_google_login.py - Check which profiles are logged into Google

This script:
1. Opens each profile with status 'available' (that has mla_uuid)
2. Visits myaccount.google.com to check if logged in
3. If logged in → marks as 'google_logged_in' in Supabase + adds tag in MLX
4. If not logged in → keeps as 'available' (you still need to log in manually)
5. Fast - about 15 seconds per profile, 5 at a time

Run this AFTER you've manually logged into profiles through the MLX desktop app.
"""

import os
import hashlib
import asyncio
import random
import time
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

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

MLX_LAUNCHER = "https://launcher.mlx.yt:45001/api/v2"
MLX_CLOUD_API = "https://api.multilogin.com"

# Performance
MAX_CONCURRENT = 5
PROXY_WARMUP_DELAY = 5
TOKEN_REFRESH_INTERVAL = 900

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
                    print(f"🔑 Token refreshed")
                    return
            except Exception as e:
                print(f"⚠️ Token refresh {attempt}/5 failed: {e}")
                time.sleep(2)
        
        raise Exception("Failed to refresh token")

token_manager = TokenManager()

# ==========================================
# COUNTERS
# ==========================================
logged_in_count = 0
not_logged_in_count = 0
error_count = 0
counter_lock = asyncio.Lock()

# ==========================================
# TAG PROFILE IN MLX
# ==========================================
def tag_profile_in_mlx(mla_uuid, token, tag="google_logged_in"):
    """Add a tag to a profile in Multilogin X via API."""
    try:
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        # Use partial update to add tag
        payload = {
            "tags": [tag]
        }
        with httpx.Client(verify=False, timeout=15, trust_env=False) as client:
            resp = client.post(
                f"{MLX_CLOUD_API}/profile/partial_update/{mla_uuid}",
                json=payload,
                headers=headers
            )
            if resp.status_code == 200:
                return True
            # If partial_update doesn't work, try regular update
    except:
        pass
    return False

# ==========================================
# CHECK SINGLE PROFILE
# ==========================================
async def check_profile(profile_data, worker_id):
    """Open a profile, check if Google is logged in, update status."""
    global logged_in_count, not_logged_in_count, error_count
    
    mla_uuid = profile_data.get('mla_uuid')
    db_id = profile_data.get('id')
    profile_name = profile_data.get('profile_id', 'Unknown')
    
    if not mla_uuid:
        return
    
    token = token_manager.get_token()
    await asyncio.sleep(worker_id * 2)
    
    start_url = f"{MLX_LAUNCHER}/profile/f/{MLX_FOLDER_ID}/p/{mla_uuid}/start?automation_type=playwright&headless_mode=false"
    stop_url = f"{MLX_LAUNCHER}/profile/f/{MLX_FOLDER_ID}/p/{mla_uuid}/stop"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    
    browser = None
    is_logged_in = False
    
    try:
        # Start profile
        try:
            async with httpx.AsyncClient(verify=False, trust_env=False, timeout=60) as client:
                resp = await client.get(start_url, headers=headers)
        except Exception as e:
            print(f"  [{profile_name}] ⚠️ Network error starting profile: {str(e)[:50]}")
            async with counter_lock:
                error_count += 1
            return
        
        if resp.status_code != 200:
            error_text = resp.text[:120]
            if "GET_DIRECT_CONNECTION_IP_ERROR" in error_text:
                print(f"  [{profile_name}] ⚠️ Proxy error - marking as proxy_error")
            elif "PROFILE_ALREADY_RUNNING" in error_text:
                print(f"  [{profile_name}] ⚠️ Already running - skipping")
                async with counter_lock:
                    error_count += 1
                return  # Don't mark as proxy_error, just skip
            else:
                print(f"  [{profile_name}] ❌ Start failed - marking as proxy_error")
            
            # Mark as proxy_error so it won't be retried
            supabase.table('profiles').update({
                'status': 'proxy_error'
            }).eq('id', db_id).execute()
            
            async with counter_lock:
                error_count += 1
            return
        
        port = resp.json().get("data", {}).get("port")
        if not port:
            supabase.table('profiles').update({
                'status': 'proxy_error'
            }).eq('id', db_id).execute()
            async with counter_lock:
                error_count += 1
            return
        
        # Wait for proxy
        await asyncio.sleep(PROXY_WARMUP_DELAY)
        
        # Connect and check
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
            context = browser.contexts[0]
            context.set_default_timeout(15000)
            page = context.pages[0] if context.pages else await context.new_page()
            
            # Navigate to YouTube - check if signed in
            try:
                await page.goto("https://www.youtube.com", wait_until="domcontentloaded", timeout=20000)
                await asyncio.sleep(3)
                
                page_content = await page.content()
                
                # If signed in: YouTube shows avatar button (id="avatar-btn") or account menu
                # If not signed in: YouTube shows "Sign in" button
                has_sign_in_button = await page.locator("a[href*='accounts.google.com/ServiceLogin'], tp-yt-paper-button#sign-in-button, a:text('Sign in')").count()
                has_avatar = await page.locator("#avatar-btn, button#avatar-btn, img#img[alt*='Avatar']").count()
                
                if has_avatar > 0 and has_sign_in_button == 0:
                    is_logged_in = True
                elif has_sign_in_button > 0:
                    is_logged_in = False
                else:
                    # Fallback: check page content
                    if "Sign in" in page_content and "avatar-btn" not in page_content:
                        is_logged_in = False
                    elif "avatar-btn" in page_content:
                        is_logged_in = True
                    else:
                        is_logged_in = False
                        
            except Exception as e:
                error_msg = str(e)
                if "ERR_INVALID_AUTH_CREDENTIALS" in error_msg or "ERR_PROXY" in error_msg:
                    print(f"  [{profile_name}] ⚠️ Proxy error - marking as proxy_error")
                    supabase.table('profiles').update({
                        'status': 'proxy_error'
                    }).eq('id', db_id).execute()
                    async with counter_lock:
                        error_count += 1
                    # Stop profile before returning
                    try:
                        async with httpx.AsyncClient(verify=False, timeout=15) as client:
                            await client.get(stop_url, headers=headers)
                    except:
                        pass
                    try:
                        await browser.close()
                    except:
                        pass
                    browser = None
                    return
                is_logged_in = False
            
            # Stop MLX profile first (saves cookies)
            try:
                async with httpx.AsyncClient(verify=False, timeout=15) as client:
                    await client.get(stop_url, headers=headers)
            except:
                pass
            
            await asyncio.sleep(2)
            
            try:
                await browser.close()
            except:
                pass
            browser = None
        
        # Update results
        if is_logged_in:
            # Update Supabase
            supabase.table('profiles').update({
                'status': 'google_logged_in',
                'last_used_at': datetime.now(timezone.utc).isoformat()
            }).eq('id', db_id).execute()
            
            # Tag in MLX
            tag_profile_in_mlx(mla_uuid, token)
            
            async with counter_lock:
                logged_in_count += 1
            print(f"  [{profile_name}] ✅ LOGGED IN")
        else:
            # Keep as available - still needs manual login
            async with counter_lock:
                not_logged_in_count += 1
            print(f"  [{profile_name}] ❌ Not logged in")
    
    except Exception as e:
        print(f"  [{profile_name}] ❌ Error: {str(e)[:60]}")
        async with counter_lock:
            error_count += 1
    
    finally:
        if browser:
            try: await browser.close()
            except: pass
        
        # Make sure profile is stopped
        try:
            async with httpx.AsyncClient(verify=False, timeout=10) as client:
                await client.get(stop_url, headers=headers)
        except:
            pass

# ==========================================
# PROFILE LOCKING
# ==========================================
async def get_and_lock_profile():
    """Get a profile to check."""
    try:
        resp = supabase.table('profiles')\
            .select('*')\
            .eq('status', 'available')\
            .not_.is_('mla_uuid', 'null')\
            .limit(1)\
            .execute()
        
        if not resp.data:
            return None
        
        profile = resp.data[0]
        
        # Lock it temporarily
        update = supabase.table('profiles')\
            .update({'status': 'checking'})\
            .eq('id', profile['id'])\
            .eq('status', 'available')\
            .execute()
        
        if update.data and len(update.data) > 0:
            return profile
        return None
    except:
        return None

async def release_profile(db_id, new_status='available'):
    """Release a profile back."""
    supabase.table('profiles').update({
        'status': new_status
    }).eq('id', db_id).execute()

# ==========================================
# WORKER
# ==========================================
processed_count = 0
processed_lock = asyncio.Lock()

async def worker(worker_id, semaphore, total_profiles):
    global processed_count
    
    while True:
        async with semaphore:
            profile = await get_and_lock_profile()
            
            if not profile:
                await asyncio.sleep(1)
                # Check if any left
                check = supabase.table('profiles')\
                    .select('id')\
                    .eq('status', 'available')\
                    .not_.is_('mla_uuid', 'null')\
                    .limit(1)\
                    .execute()
                if not check.data:
                    # Also check for any stuck in 'checking'
                    check2 = supabase.table('profiles')\
                        .select('id')\
                        .eq('status', 'checking')\
                        .limit(1)\
                        .execute()
                    if not check2.data:
                        print(f"[Worker {worker_id}] ✅ Done")
                        break
                continue
            
            async with processed_lock:
                processed_count += 1
                current = processed_count
            
            print(f"\n[{current}/{total_profiles}] Checking {profile.get('profile_id', '?')}...")
            
            await check_profile(profile, worker_id)
            
            # If profile wasn't marked as logged_in, release back to available
            current_status = supabase.table('profiles')\
                .select('status')\
                .eq('id', profile['id'])\
                .execute()
            
            if current_status.data and current_status.data[0].get('status') == 'checking':
                await release_profile(profile['id'], 'available')
            
            await asyncio.sleep(random.uniform(2, 4))

# ==========================================
# MAIN
# ==========================================
async def main():
    import warnings
    warnings.filterwarnings("ignore", message="Unverified HTTPS request")
    
    print("\n" + "="*50)
    print("🔍 GOOGLE LOGIN CHECKER")
    print("="*50)
    print("✓ Checks if Google is logged in per profile")
    print("✓ Updates Supabase status to 'google_logged_in'")
    print("✓ Tags profile in MLX desktop app")
    print(f"✓ Max {MAX_CONCURRENT} concurrent browsers")
    print("="*50 + "\n")
    
    try:
        token_manager.get_token()
        print("✅ Authenticated\n")
    except Exception as e:
        print(f"❌ Auth failed: {e}")
        return
    
    # Count available profiles
    count = supabase.table('profiles')\
        .select('id', count='exact')\
        .eq('status', 'available')\
        .not_.is_('mla_uuid', 'null')\
        .execute()
    total = count.count if hasattr(count, 'count') and count.count is not None else len(count.data)
    
    # Also show already logged in
    logged = supabase.table('profiles')\
        .select('id', count='exact')\
        .eq('status', 'google_logged_in')\
        .execute()
    already_logged = logged.count if hasattr(logged, 'count') and logged.count is not None else len(logged.data)
    
    print(f"📊 {total} profiles to check")
    print(f"📊 {already_logged} already marked as logged in\n")
    
    if total == 0:
        print("No profiles to check.")
        return
    
    # Run workers
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    tasks = [asyncio.create_task(worker(i, semaphore, total)) for i in range(MAX_CONCURRENT)]
    await asyncio.gather(*tasks, return_exceptions=True)
    
    # Final summary - get actual counts from DB
    final_counts = {}
    for status in ['google_logged_in', 'available', 'proxy_error', 'checking']:
        r = supabase.table('profiles').select('id', count='exact').eq('status', status).execute()
        final_counts[status] = r.count if hasattr(r, 'count') and r.count is not None else len(r.data)
    
    print("\n" + "="*50)
    print("🏁 CHECK COMPLETE!")
    print(f"  ✅ Logged in:      {final_counts.get('google_logged_in', 0)}")
    print(f"  ❌ Not logged in:  {final_counts.get('available', 0)}")
    print(f"  ⚠️  Proxy errors:  {final_counts.get('proxy_error', 0)}")
    print("="*50)
    
    if final_counts.get('available', 0) > 0:
        print(f"\n👉 {final_counts['available']} profiles still need manual Google login in MLX.")
        print("   Log in manually, then run this script again to update.")

if __name__ == "__main__":
    asyncio.run(main())