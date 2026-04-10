"""
warmup_profiles.py - Enhanced Cookie Warm-Up Script with Personalization

This script connects to your Supabase database, retrieves profiles marked as 'available',
and uses Playwright to automate browsing sessions through the Multilogin X local API.

Each profile is warmed up with PERSONALIZED browsing based on:
1. Proxy location (city/state) - for local searches like "restaurants in Denver"
2. Profile interests - for niche site visits and targeted searches
3. Human-like behavior simulation

Requirements:
- MLX desktop app must be running and connected
- Supabase credentials in .env file
- Playwright installed
"""

import os
import hashlib
import random
import time
import asyncio
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

import httpx
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

# Performance Settings
MAX_CONCURRENT_BROWSERS = 5      # How many browsers at once
TOKEN_REFRESH_INTERVAL = 900     # Refresh token every 15 minutes

if not all([SUPABASE_URL, SUPABASE_KEY, MLX_EMAIL, MLX_PASSWORD, MLX_FOLDER_ID]):
    raise ValueError("Missing credentials in .env")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==========================================
# NICHE SITES BY INTEREST CATEGORY
# ==========================================
INTEREST_SITES = {
    # Technology & Gaming
    "technology": ["https://www.theverge.com", "https://techcrunch.com", "https://www.wired.com"],
    "tech": ["https://www.theverge.com", "https://techcrunch.com", "https://www.cnet.com"],
    "gaming": ["https://www.ign.com", "https://www.gamespot.com", "https://kotaku.com"],
    "computers": ["https://www.tomshardware.com", "https://www.pcgamer.com"],
    "programming": ["https://stackoverflow.com", "https://github.com", "https://dev.to"],
    
    # Sports
    "sports": ["https://www.espn.com", "https://www.cbssports.com", "https://bleacherreport.com"],
    "football": ["https://www.espn.com/nfl/", "https://www.nfl.com"],
    "basketball": ["https://www.espn.com/nba/", "https://www.nba.com"],
    "soccer": ["https://www.espn.com/soccer/", "https://www.goal.com"],
    "fitness": ["https://www.bodybuilding.com", "https://www.menshealth.com"],
    
    # Entertainment
    "movies": ["https://www.imdb.com", "https://www.rottentomatoes.com"],
    "tv": ["https://www.tvguide.com", "https://www.imdb.com"],
    "music": ["https://www.billboard.com", "https://pitchfork.com"],
    
    # Lifestyle
    "cooking": ["https://www.allrecipes.com", "https://www.foodnetwork.com", "https://www.bonappetit.com"],
    "food": ["https://www.allrecipes.com", "https://www.eater.com"],
    "recipes": ["https://www.allrecipes.com", "https://www.epicurious.com"],
    "travel": ["https://www.tripadvisor.com", "https://www.lonelyplanet.com"],
    "fashion": ["https://www.vogue.com", "https://www.gq.com"],
    "home": ["https://www.houzz.com", "https://www.apartmenttherapy.com"],
    "pets": ["https://www.petmd.com", "https://www.chewy.com"],
    
    # Finance & Business
    "finance": ["https://www.bloomberg.com", "https://www.cnbc.com", "https://finance.yahoo.com"],
    "investing": ["https://www.investopedia.com", "https://www.fool.com"],
    "crypto": ["https://www.coindesk.com", "https://cointelegraph.com"],
    "business": ["https://www.forbes.com", "https://www.businessinsider.com"],
    "realestate": ["https://www.zillow.com", "https://www.realtor.com"],
    
    # News
    "news": ["https://www.cnn.com", "https://www.bbc.com", "https://www.reuters.com"],
    "politics": ["https://www.politico.com", "https://thehill.com"],
    
    # Health
    "health": ["https://www.webmd.com", "https://www.healthline.com"],
    "wellness": ["https://www.mindbodygreen.com", "https://www.wellandgood.com"],
    
    # Education & Science
    "science": ["https://www.scientificamerican.com", "https://www.sciencedaily.com"],
    "education": ["https://www.khanacademy.org", "https://www.coursera.org"],
    
    # Shopping
    "shopping": ["https://www.amazon.com", "https://www.ebay.com", "https://www.walmart.com"],
    
    # Outdoors
    "outdoors": ["https://www.rei.com", "https://www.outsideonline.com"],
    "hiking": ["https://www.alltrails.com"],
    "camping": ["https://www.rei.com", "https://koa.com"],
    
    # Automotive
    "cars": ["https://www.caranddriver.com", "https://www.motortrend.com"],
}

# ==========================================
# LOCATION-BASED SEARCH TEMPLATES
# ==========================================
LOCAL_SEARCH_TEMPLATES = [
    "{interest} in {city}",
    "best {interest} near {city}",
    "{interest} {city} {state}",
    "top rated {interest} {city}",
]

LOCAL_GENERAL_SEARCHES = [
    "restaurants in {city}",
    "things to do in {city}",
    "weather {city} {state}",
    "events in {city} this weekend",
    "best coffee shops {city}",
    "news {city} {state}",
    "gas prices {city}",
    "grocery stores near {city}",
    "parks in {city}",
    "gyms near {city}",
    "movie theaters {city}",
    "best pizza {city}",
]

GENERAL_SITES = [
    "https://www.google.com",
    "https://www.youtube.com",
    "https://www.amazon.com",
    "https://www.wikipedia.org",
    "https://www.reddit.com",
    "https://weather.com",
]

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
# HELPERS
# ==========================================
def get_niche_sites(interests: list, max_sites: int = 3) -> list:
    """Get niche sites based on interests."""
    sites = []
    for interest in interests:
        key = interest.lower().strip()
        if key in INTEREST_SITES:
            sites.extend(INTEREST_SITES[key])
        else:
            for k, v in INTEREST_SITES.items():
                if k in key or key in k:
                    sites.extend(v)
                    break
    
    unique = list(set(sites))
    random.shuffle(unique)
    return unique[:max_sites]

def generate_local_searches(city: str, state: str, interests: list, max_searches: int = 2) -> list:
    """Generate location-based searches."""
    if not city or city == "Unknown":
        return []
    
    searches = []
    
    # General local searches
    general = random.sample(LOCAL_GENERAL_SEARCHES, min(2, len(LOCAL_GENERAL_SEARCHES)))
    for template in general:
        searches.append(template.format(city=city, state=state or "").strip())
    
    # Interest + location searches
    if interests:
        for interest in random.sample(interests, min(2, len(interests))):
            template = random.choice(LOCAL_SEARCH_TEMPLATES)
            searches.append(template.format(interest=interest, city=city, state=state or "").strip())
    
    random.shuffle(searches)
    return searches[:max_searches]

def generate_interest_searches(interests: list, max_searches: int = 2) -> list:
    """Generate searches based on interests."""
    if not interests:
        return []
    
    templates = [
        "best {interest} 2024",
        "{interest} tips",
        "{interest} for beginners",
        "top {interest} recommendations",
    ]
    
    searches = []
    for interest in random.sample(interests, min(max_searches, len(interests))):
        template = random.choice(templates)
        searches.append(template.format(interest=interest))
    
    return searches

# ==========================================
# HUMAN BEHAVIOR
# ==========================================
async def random_delay(min_sec=0.5, max_sec=2.0):
    await asyncio.sleep(random.uniform(min_sec, max_sec))

async def simulate_scrolling(page):
    """Human-like scrolling."""
    try:
        page_height = await page.evaluate("document.body.scrollHeight")
        viewport_height = await page.evaluate("window.innerHeight")
        
        if page_height <= viewport_height:
            return
        
        current = 0
        for _ in range(random.randint(3, 7)):
            scroll = random.randint(200, 500)
            await page.mouse.wheel(0, scroll)
            current += scroll
            
            # Pause to "read"
            await asyncio.sleep(random.uniform(1.0, 3.0))
            
            # Sometimes scroll back
            if random.random() < 0.2:
                await page.mouse.wheel(0, -random.randint(50, 150))
                await asyncio.sleep(random.uniform(0.5, 1.0))
            
            if current >= page_height - viewport_height:
                break
    except:
        pass

async def simulate_mouse(page):
    """Random mouse movement."""
    try:
        viewport = await page.evaluate("({w: window.innerWidth, h: window.innerHeight})")
        for _ in range(random.randint(2, 4)):
            x = random.randint(100, viewport['w'] - 100)
            y = random.randint(100, viewport['h'] - 100)
            await page.mouse.move(x, y, steps=random.randint(10, 20))
            await asyncio.sleep(random.uniform(0.3, 0.7))
    except:
        pass

async def maybe_click_link(page):
    """30% chance to click a link and explore."""
    try:
        if random.random() > 0.3:
            return
        
        links = await page.query_selector_all("a[href^='http']:not([href*='javascript'])")
        if not links or len(links) < 5:
            return
        
        # Pick from middle of page
        middle = links[len(links)//4 : 3*len(links)//4]
        if not middle:
            return
        
        link = random.choice(middle)
        if not await link.is_visible():
            return
        
        await link.click(timeout=5000)
        await page.wait_for_load_state("domcontentloaded", timeout=10000)
        print(f"      ↪ Clicked link, exploring...")
        
        await asyncio.sleep(random.uniform(2, 5))
        await simulate_scrolling(page)
        await page.go_back(timeout=10000)
        
    except:
        pass

async def google_search(page, query):
    """Perform a Google search."""
    try:
        await page.goto("https://www.google.com", wait_until="domcontentloaded", timeout=30000)
        await random_delay(1, 2)
        
        search_box = await page.query_selector('textarea[name="q"], input[name="q"]')
        if not search_box:
            return False
        
        await search_box.click()
        await random_delay(0.3, 0.6)
        
        # Type like a human
        for char in query:
            await search_box.type(char, delay=random.randint(50, 120))
        
        await random_delay(0.5, 1.0)
        await page.keyboard.press("Enter")
        await page.wait_for_load_state("domcontentloaded", timeout=15000)
        await random_delay(1, 2)
        
        await simulate_scrolling(page)
        
        # 40% chance to click a result
        if random.random() < 0.4:
            results = await page.query_selector_all("div.g a[href^='http']")
            if results:
                result = random.choice(results[:min(5, len(results))])
                try:
                    await result.click(timeout=5000)
                    await page.wait_for_load_state("domcontentloaded", timeout=15000)
                    print(f"      ↪ Clicked result")
                    await random_delay(3, 6)
                    await simulate_scrolling(page)
                except:
                    pass
        
        return True
    except Exception as e:
        print(f"      ⚠️ Search error: {str(e)[:40]}")
        return False

# ==========================================
# WARM-UP ROUTINE
# ==========================================
async def warmup_routine(page, profile_data, mla_uuid):
    """Execute personalized warm-up."""
    
    # Extract profile data
    demographics = profile_data.get('demographics', {}) or {}
    behavioral = profile_data.get('behavioral_metrics', {}) or {}
    location = profile_data.get('location', {}) or {}
    
    interests = demographics.get('interests', []) or []
    city = location.get('city', 'Unknown')
    state = location.get('state', '')
    dwell = behavioral.get('dwell_time_modifier', 1.0) or 1.0
    
    print(f"[{mla_uuid[:8]}] 📍 {city}, {state}")
    print(f"[{mla_uuid[:8]}] 🎯 Interests: {', '.join(interests[:3]) if interests else 'None'}")
    
    # Build activity list
    activities = []
    
    # 1. General site
    activities.append(("SITE", random.choice(GENERAL_SITES)))
    
    # 2. Local searches (based on city)
    for q in generate_local_searches(city, state, interests, 2):
        activities.append(("SEARCH", q))
    
    # 3. Niche sites (based on interests)
    for site in get_niche_sites(interests, 2):
        activities.append(("SITE", site))
    
    # 4. Interest searches
    for q in generate_interest_searches(interests, 1):
        activities.append(("SEARCH", q))
    
    # 5. Another general site
    activities.append(("SITE", random.choice(GENERAL_SITES)))
    
    # Shuffle (keep first, shuffle rest)
    first = activities[0]
    rest = activities[1:]
    random.shuffle(rest)
    activities = [first] + rest[:8]  # Max 9 activities
    
    print(f"[{mla_uuid[:8]}] 📋 {len(activities)} activities planned\n")
    
    # Execute
    for i, (atype, target) in enumerate(activities):
        try:
            if atype == "SEARCH":
                print(f"  [{i+1}/{len(activities)}] 🔍 \"{target}\"")
                await google_search(page, target)
            else:
                print(f"  [{i+1}/{len(activities)}] 🌐 {target}")
                await page.goto(target, wait_until="domcontentloaded", timeout=30000)
                await random_delay(1.5, 2.5)
                await simulate_mouse(page)
                await simulate_scrolling(page)
                await maybe_click_link(page)
            
            await asyncio.sleep(random.uniform(2, 4) * dwell)
            
        except Exception as e:
            print(f"  ⚠️ {str(e)[:40]}")
            continue
    
    print(f"\n[{mla_uuid[:8]}] ✅ Warm-up done!")
    return True

# ==========================================
# PROFILE PROCESSING
# ==========================================
async def process_profile(profile_data, worker_id):
    mla_uuid = profile_data.get('mla_uuid')
    db_id = profile_data.get('id')
    name = profile_data.get('profile_id', 'Unknown')
    
    if not mla_uuid:
        supabase.table('profiles').update({'status': 'error'}).eq('id', db_id).execute()
        return
    
    token = token_manager.get_token()
    await asyncio.sleep(worker_id * 2)
    
    start_url = f"{MLX_LAUNCHER}/profile/f/{MLX_FOLDER_ID}/p/{mla_uuid}/start?automation_type=playwright&headless_mode=false"
    stop_url = f"{MLX_LAUNCHER}/profile/f/{MLX_FOLDER_ID}/p/{mla_uuid}/stop"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    
    browser = None
    
    try:
        print(f"\n{'='*50}")
        print(f"[Worker {worker_id}] Starting: {name}")
        print(f"{'='*50}")
        
        async with httpx.AsyncClient(verify=False, trust_env=False, timeout=60) as client:
            resp = await client.get(start_url, headers=headers)
        
        if resp.status_code != 200:
            print(f"[{name}] ❌ Start failed: {resp.text[:80]}")
            supabase.table('profiles').update({'status': 'error'}).eq('id', db_id).execute()
            return
        
        port = resp.json().get("data", {}).get("port")
        if not port:
            print(f"[{name}] ❌ No port")
            supabase.table('profiles').update({'status': 'error'}).eq('id', db_id).execute()
            return
        
        print(f"[{name}] 🚀 Port {port}")
        
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
            context = browser.contexts[0]
            context.set_default_timeout(30000)
            page = context.pages[0] if context.pages else await context.new_page()
            
            await warmup_routine(page, profile_data, mla_uuid)
            
            supabase.table('profiles').update({
                'status': 'available',
                'last_used_at': datetime.now(timezone.utc).isoformat()
            }).eq('id', db_id).execute()
            
            await browser.close()
            browser = None
    
    except Exception as e:
        print(f"[{name}] ❌ {str(e)[:80]}")
        supabase.table('profiles').update({'status': 'error'}).eq('id', db_id).execute()
    
    finally:
        if browser:
            try: await browser.close()
            except: pass
        
        try:
            async with httpx.AsyncClient(verify=False, timeout=15) as client:
                await client.get(stop_url, headers=headers)
            print(f"[{name}] 🛑 Stopped\n")
        except:
            pass

# ==========================================
# ATOMIC LOCK
# ==========================================
async def get_and_lock_profile():
    try:
        resp = supabase.table('profiles').select('*').eq('status', 'available').limit(1).execute()
        if not resp.data:
            return None
        
        profile = resp.data[0]
        update = supabase.table('profiles').update({'status': 'in_use'}).eq('id', profile['id']).eq('status', 'available').execute()
        
        if update.data and len(update.data) > 0:
            return profile
        return None
    except:
        return None

# ==========================================
# WORKER
# ==========================================
async def worker(worker_id, semaphore):
    while True:
        async with semaphore:
            profile = await get_and_lock_profile()
            
            if not profile:
                await asyncio.sleep(1)
                check = supabase.table('profiles').select('id').eq('status', 'available').limit(1).execute()
                if not check.data:
                    print(f"[Worker {worker_id}] ✅ Done")
                    break
                continue
            
            await process_profile(profile, worker_id)
            await asyncio.sleep(2)

# ==========================================
# MAIN
# ==========================================
async def main():
    import warnings
    warnings.filterwarnings("ignore", message="Unverified HTTPS request")
    
    print("\n" + "="*50)
    print("🍪 PERSONALIZED WARM-UP SCRIPT")
    print("="*50)
    print("✓ Location-based searches")
    print("✓ Interest-based niche sites")
    print("✓ Human-like behavior")
    print(f"✓ Max {MAX_CONCURRENT_BROWSERS} browsers")
    print("="*50 + "\n")
    
    try:
        token_manager.get_token()
        print("✅ Authenticated\n")
    except Exception as e:
        print(f"❌ Auth failed: {e}")
        return
    
    count = supabase.table('profiles').select('id', count='exact').eq('status', 'available').execute()
    total = count.count if hasattr(count, 'count') else len(count.data)
    print(f"📊 {total} profiles to warm up\n")
    
    if total == 0:
        print("No profiles available")
        return
    
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_BROWSERS)
    tasks = [asyncio.create_task(worker(i, semaphore)) for i in range(MAX_CONCURRENT_BROWSERS)]
    await asyncio.gather(*tasks, return_exceptions=True)
    
    print("\n" + "="*50)
    print("🎉 ALL DONE!")
    print("="*50)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Stopped")