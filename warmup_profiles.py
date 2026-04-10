"warmup_profiles.py - This script connects to your Supabase database, retrieves profiles marked as 'available', and uses Playwright to automate browsing sessions through the Multilogin X local API. Each profile is warmed up by visiting a mix of general and personalized websites based on the profile's demographics and interests. After the warm-up routine, profiles are marked back as 'available' for use in your main automation tasks. Make sure to have the MLX local app running and properly configured before executing this script."

import os
import hashlib
import urllib.parse
from dotenv import load_dotenv
load_dotenv()
import httpx  
import asyncio
import random
import time
from datetime import datetime, timezone
from supabase import create_client
from playwright.async_api import async_playwright

# ==========================================
# CONFIGURATION
# ==========================================
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

MLX_EMAIL = os.environ.get("MLX_EMAIL")
MLX_PASSWORD = os.environ.get("MLX_PASSWORD")
MLX_FOLDER_ID = os.environ.get("MLX_FOLDER_ID")
MLX_LAUNCHER = "https://launcher.mlx.yt:45001/api/v2" 

# Max simultaneous browsers to prevent overloading your PC or the local MLX API
MAX_CONCURRENT_BROWSERS = 10  

if not all([SUPABASE_URL, SUPABASE_KEY, MLX_EMAIL, MLX_PASSWORD, MLX_FOLDER_ID]):
    raise ValueError("Missing Supabase or MLX credentials in environment variables.")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

SEED_SITES = [
    "https://www.cnn.com", "https://www.bbc.com", "https://www.nytimes.com",
    "https://www.amazon.com", "https://www.ebay.com", "https://www.reddit.com/r/news",
    "https://www.imdb.com", "https://www.espn.com"
]

# ==========================================
# AUTHENTICATION
# ==========================================
def get_mlx_token():
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
                return response.json()['data']['token']
        except Exception as e:
            print(f"⚠️ Auth network hiccup (attempt {attempt}/5): {e}... retrying in 1s")
            time.sleep(1)
            
    raise Exception("Failed to get MLX token after 5 attempts.")

# ==========================================
# HUMAN BEHAVIOR LOGIC
# ==========================================
async def simulate_human_reading(page, dwell_modifier):
    try:
        scroll_steps = random.randint(3, 7)
        for _ in range(scroll_steps):
            scroll_amount = random.randint(300, 800)
            await page.mouse.wheel(0, scroll_amount)
            base_pause = random.uniform(1.5, 4.0)
            actual_pause = base_pause * dwell_modifier
            await asyncio.sleep(actual_pause)
    except Exception:
        pass

async def execute_warmup_routine(page, profile_data, mla_uuid):
    dwell_modifier = profile_data.get('behavioral_metrics', {}).get('dwell_time_modifier', 1.0)
    
    # 1. Pull the custom localized topics already saved in your database
    interests = profile_data.get('demographics', {}).get('interests', [])
    city = profile_data.get('location', {}).get('city', 'Unknown City')
    
    local_sites = []
    if interests:
        # Pick 2 random niche topics from this specific persona's list
        chosen_topics = random.sample(interests, min(2, len(interests)))
        for topic in chosen_topics:
            # Convert the topic into a perfectly formatted Google Search URL
            search_query = urllib.parse.quote(topic)
            local_sites.append(f"https://www.google.com/search?q={search_query}")

    print(f"[{mla_uuid}] 📍 Profile Location: {city} | Warming up...")

    # 2. Mix general sites with the local AI search sites
    num_sites = random.randint(2, 4)
    sites_to_visit = random.sample(SEED_SITES, num_sites) + local_sites
    
    # Shuffle so the Google searches don't always happen in the exact same order
    random.shuffle(sites_to_visit) 

    for site in sites_to_visit:
        try:
            # Decode Google URLs just for the terminal printout so it's readable for you
            display_site = urllib.parse.unquote(site) if "search?q=" in site else site
            print(f"  -> Browsing: {display_site}")
            
            await page.goto(site, wait_until="domcontentloaded", timeout=45000)
            await asyncio.sleep(random.uniform(2.0, 4.0))
            await simulate_human_reading(page, dwell_modifier)
        except Exception as e:
            print(f"  ⚠️ Failed to load {site}: {str(e)[:50]}")
            continue

    print(f"[{mla_uuid}] ✅ Warm-up complete.")
    return True

# ==========================================
# CORE WORKER LOGIC
# ==========================================
async def process_profile(profile_data, mlx_token, worker_id):
    mla_uuid = profile_data['mla_uuid']
    db_id = profile_data['id']

    if not mla_uuid:
        print(f"[SKIP] Profile id={db_id} has no mla_uuid, skipping.")
        supabase.table('profiles').update({'status': 'error'}).eq('id', db_id).execute()
        return

    # Stagger profile starts to prevent overloading the MLX local app
    stagger_delay = worker_id * 1.5 
    await asyncio.sleep(stagger_delay)

    start_url = f"{MLX_LAUNCHER}/profile/f/{MLX_FOLDER_ID}/p/{mla_uuid}/start?automation_type=playwright&headless_mode=false"
    stop_url = f"{MLX_LAUNCHER}/profile/f/{MLX_FOLDER_ID}/p/{mla_uuid}/stop"
    
    headers = {
        "Authorization": f"Bearer {mlx_token}",
        "Accept": "application/json"
    }

    try:
        async with httpx.AsyncClient(verify=False, trust_env=False, timeout=60) as client:
            mla_response = await client.get(start_url, headers=headers)
            
        raw = mla_response.text.strip()
        
        if mla_response.status_code != 200:
            print(f"[{mla_uuid}] Failed to start. Code: {mla_response.status_code}. Details: {raw[:150]}")
            supabase.table('profiles').update({'status': 'error'}).eq('id', db_id).execute()
            return

        try:
            mla_data = mla_response.json()
        except Exception:
            mla_data = {}

        port = mla_data.get("data", {}).get("port")
        if not port:
            print(f"[{mla_uuid}] No port returned.")
            supabase.table('profiles').update({'status': 'error'}).eq('id', db_id).execute()
            return

        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
            context = browser.contexts[0]
            context.set_default_timeout(45000)
            page = context.pages[0] if context.pages else await context.new_page()

            await execute_warmup_routine(page, profile_data, mla_uuid)

            # Release profile back to available pool
            supabase.table('profiles').update({
                'status': 'available',
                'last_used_at': datetime.now(timezone.utc).isoformat()
            }).eq('id', db_id).execute()

            await browser.close()

    except Exception as e:
        print(f"[{mla_uuid}] Error during warm-up: {e}")
        supabase.table('profiles').update({
            'status': 'error',
            'last_used_at': datetime.now(timezone.utc).isoformat()
        }).eq('id', db_id).execute()

    finally:
        try:
            async with httpx.AsyncClient(verify=False, trust_env=False, timeout=15) as client:
                await client.get(stop_url, headers=headers)
            print(f"[{mla_uuid}] Profile stopped and cookies saved.\n")
        except Exception:
            pass

# ==========================================
# ORCHESTRATION
# ==========================================
async def worker(worker_id, semaphore, mlx_token):
    while True:
        async with semaphore:
            response = supabase.table('profiles')\
                .select('*').eq('status', 'available').limit(1).execute()

            if not response.data:
                print(f"Worker {worker_id} found no available profiles. Shutting down.")
                break

            profile_data = response.data[0]
            
            # Immediately lock the profile so other workers don't grab it
            supabase.table('profiles').update({'status': 'in_use'}).eq('id', profile_data['id']).execute()
            
            await process_profile(profile_data, mlx_token, worker_id) 
            await asyncio.sleep(2)

async def main():
    import warnings
    warnings.filterwarnings("ignore", message="Unverified HTTPS request")
    
    print(f"Starting COOKIE WARM-UP Phase (Max {MAX_CONCURRENT_BROWSERS} browsers)...")
    
    try:
        mlx_token = await asyncio.to_thread(get_mlx_token)
        print("✅ Successfully authenticated with Multilogin X.")
    except Exception as e:
        print(f"❌ Failed to get MLX Token: {e}")
        return

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_BROWSERS)
    tasks = [asyncio.create_task(worker(i, semaphore, mlx_token)) for i in range(MAX_CONCURRENT_BROWSERS)]
    await asyncio.gather(*tasks, return_exceptions=True)
    print("Warm-up phase completed for all available profiles.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Execution stopped by user.")