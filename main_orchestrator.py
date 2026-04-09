import os
import requests
import asyncio
from datetime import datetime, timezone
from supabase import create_client
from playwright.async_api import async_playwright

# ==========================================
# CONFIGURATION
# ==========================================
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
MLA_API_PORT = 35000 
MAX_CONCURRENT_BROWSERS = 15 # Safely capped for 32GB RAM

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing Supabase credentials in environment variables.")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


# ==========================================
# AUTOMATION LOGIC
# ==========================================
async def execute_google_login(page, profile_data, db_id, mla_uuid):
    """Executes human-like login and checks for PVA (Phone Verification) locks."""
    email = profile_data.get('google_email')
    password = profile_data.get('google_password')
    
    if not email or not password:
        print(f"[{mla_uuid}] ⚠️ No Google credentials found. Skipping login.")
        return False

    print(f"[{mla_uuid}] Attempting login for {email}...")
    
    try:
        # 1. Navigate to Google Sign-In
        await page.goto("https://accounts.google.com/signin", wait_until="domcontentloaded")
        
        # 2. Emulate human typing for the email
        await page.locator('input[type="email"]').press_sequentially(email, delay=120)
        await page.keyboard.press("Enter")
        
        # Wait for the password field to appear
        await page.wait_for_selector('input[type="password"]', state="visible", timeout=10000)
        await asyncio.sleep(1.5) # Natural human pause
        
        # 3. Emulate human typing for the password
        await page.locator('input[type="password"]').press_sequentially(password, delay=150)
        await page.keyboard.press("Enter")
        
        # Wait a moment for the redirect routing to settle
        await page.wait_for_timeout(4000) 
        
        current_url = page.url
        
        # 4. Detect the Phone Verification Checkpoint
        if "challenge/wa" in current_url or "challenge/ipp" in current_url or "speedbump" in current_url:
            print(f"[{mla_uuid}] ❌ PVA Lock detected! Flagging and discarding account.")
            
            # Update Supabase immediately
            supabase.table('profiles').update({
                'status': 'pva_locked',
                'last_used_at': datetime.now(timezone.utc).isoformat()
            }).eq('id', db_id).execute()
            
            return False
            
        print(f"[{mla_uuid}] ✅ Login successful and verified.")
        return True
        
    except Exception as e:
        print(f"[{mla_uuid}] ⚠️ Login error or timeout: {e}")
        return False


async def process_profile(profile_data):
    """Handles the full lifecycle of a single profile."""
    mla_uuid = profile_data['mla_uuid']
    db_id = profile_data['id']
    
    # 1. Start the Multilogin Profile
    start_url = f"http://127.0.0.1:{MLA_API_PORT}/api/v1/profile/start?automation=true&profileId={mla_uuid}"
    try:
        # Run synchronous requests in a thread to avoid blocking the async loop
        mla_response = await asyncio.to_thread(requests.get, start_url)
        mla_data = mla_response.json()
        
        if mla_data.get("status") != "OK":
            print(f"[{mla_uuid}] Failed to start Multilogin profile.")
            # Set to error so it doesn't get stuck in 'in_use' forever
            supabase.table('profiles').update({'status': 'error'}).eq('id', db_id).execute()
            return
            
        ws_endpoint = mla_data["value"]
        print(f"[{mla_uuid}] Launched successfully. Connecting Playwright...")
        
        # 2. Connect Playwright
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(ws_endpoint)
            context = browser.contexts[0]
            page = context.pages[0] if context.pages else await context.new_page()

            # 3. Execute Login & Check Attrition
            login_success = await execute_google_login(page, profile_data, db_id, mla_uuid)
            
            if login_success:
                print(f"[{mla_uuid}] Executing post-login warm-up tasks...")
                
                # --- YOUR WARMUP / BEHAVIORAL LOGIC HERE ---
                await page.goto("https://www.google.com")
                await asyncio.sleep(5) 
                # -------------------------------------------
                
                # Release back to available pool
                supabase.table('profiles').update({
                    'status': 'available',
                    'last_used_at': datetime.now(timezone.utc).isoformat()
                }).eq('id', db_id).execute()
            else:
                print(f"[{mla_uuid}] Aborting tasks for this profile.")
                # Note: If it failed due to PVA, the status is already 'pva_locked'.
                # If it failed due to another error, you might want to flag it as 'error'.

            await browser.close()
            
    except Exception as e:
        print(f"[{mla_uuid}] Critical execution error: {e}")
        supabase.table('profiles').update({
            'status': 'error',
            'last_used_at': datetime.now(timezone.utc).isoformat()
        }).eq('id', db_id).execute()
        
    finally:
        # 4. Stop Multilogin and Save Cookies
        stop_url = f"http://127.0.0.1:{MLA_API_PORT}/api/v1/profile/stop?profileId={mla_uuid}"
        await asyncio.to_thread(requests.get, stop_url)
        print(f"[{mla_uuid}] Profile safely shut down and session saved.")


# ==========================================
# QUEUE / WORKER ORCHESTRATION
# ==========================================
async def worker(worker_id, semaphore):
    """A worker that continually fetches profiles until the queue is empty."""
    while True:
        async with semaphore:
            # Fetch one available profile
            response = supabase.table('profiles')\
                .select('*').eq('status', 'available').limit(1).execute()
            
            if not response.data:
                print(f"Worker {worker_id} found no available profiles. Shutting down.")
                break 
                
            profile_data = response.data[0]
            
            # Lock the profile immediately
            supabase.table('profiles').update({'status': 'in_use'}).eq('id', profile_data['id']).execute()
            
            # Process the profile
            await process_profile(profile_data)
            
            # Brief pause between profiles to avoid spamming the local Multilogin API
            await asyncio.sleep(2)


async def main():
    print(f"Starting orchestration with max {MAX_CONCURRENT_BROWSERS} concurrent limits...")
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_BROWSERS)
    
    # Spawn the asynchronous workers
    tasks = [asyncio.create_task(worker(i, semaphore)) for i in range(MAX_CONCURRENT_BROWSERS)]
    
    # Wait for all workers to finish processing the 500 profiles
    await asyncio.gather(*tasks)
    print("All available profiles processed successfully.")

if __name__ == "__main__":
    # Standard boilerplate for running asyncio on Windows cleanly
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    asyncio.run(main())