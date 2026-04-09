import os
import requests
import asyncio
import random
from datetime import datetime, timezone
from supabase import create_client
from playwright.async_api import async_playwright

# ==========================================
# CONFIGURATION
# ==========================================
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
MLA_API_PORT = 35000 
MAX_CONCURRENT_BROWSERS = 15 # Capped for your 32GB RAM system

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing Supabase credentials in environment variables.")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

 
# These sites use Google's ad/analytics networks extensively.
SEED_SITES = [
    # === NEWS & MEDIA ===
    "https://www.cnn.com",
    "https://www.bbc.com",
    "https://www.nytimes.com",
    "https://www.theguardian.com",
    "https://www.washingtonpost.com",
    "https://www.foxnews.com",
    "https://www.nbcnews.com",
    "https://www.usatoday.com",
    "https://www.reuters.com",
    "https://www.apnews.com",
    "https://www.bloomberg.com",
    "https://www.forbes.com",
    "https://www.businessinsider.com",
    "https://www.huffpost.com",
    "https://www.politico.com",
    "https://www.theatlantic.com",
    "https://www.vice.com",
    "https://www.vox.com",
    "https://www.buzzfeed.com",
    "https://www.dailymail.co.uk",
    "https://www.independent.co.uk",
    "https://www.telegraph.co.uk",
    "https://www.nypost.com",
    "https://www.axios.com",
    "https://www.cbsnews.com",
    "https://www.abcnews.go.com",
    "https://www.msn.com",
    "https://www.time.com",
    "https://www.newsweek.com",
    "https://www.thehill.com",

    # === TECH & SCIENCE ===
    "https://www.wired.com",
    "https://www.techcrunch.com",
    "https://www.theverge.com",
    "https://www.engadget.com",
    "https://www.arstechnica.com",
    "https://www.gizmodo.com",
    "https://www.cnet.com",
    "https://www.zdnet.com",
    "https://www.tomsguide.com",
    "https://www.pcmag.com",
    "https://www.9to5mac.com",
    "https://www.androidauthority.com",
    "https://www.slashdot.org",
    "https://www.hackaday.com",
    "https://www.digitaltrends.com",
    "https://www.macrumors.com",
    "https://www.sciencedaily.com",
    "https://www.newscientist.com",
    "https://www.popularmechanics.com",
    "https://www.technologyreview.com",

    # === SHOPPING & E-COMMERCE ===
    "https://www.amazon.com",
    "https://www.ebay.com",
    "https://www.etsy.com",
    "https://www.walmart.com",
    "https://www.target.com",
    "https://www.bestbuy.com",
    "https://www.wayfair.com",
    "https://www.chewy.com",
    "https://www.homedepot.com",
    "https://www.lowes.com",
    "https://www.costco.com",
    "https://www.newegg.com",
    "https://www.macys.com",
    "https://www.nordstrom.com",
    "https://www.zappos.com",
    "https://www.overstock.com",
    "https://www.shopify.com",
    "https://www.aliexpress.com",
    "https://www.wish.com",
    "https://www.rakuten.com",

    # === SOCIAL & FORUMS ===
    "https://www.reddit.com/r/news",
    "https://www.reddit.com/r/technology",
    "https://www.reddit.com/r/worldnews",
    "https://www.reddit.com/r/science",
    "https://www.reddit.com/r/movies",
    "https://www.quora.com",
    "https://www.tumblr.com",
    "https://www.pinterest.com",
    "https://www.linkedin.com",
    "https://www.stackoverflow.com",
    "https://www.medium.com",
    "https://www.substack.com",

    # === ENTERTAINMENT & STREAMING ===
    "https://www.imdb.com",
    "https://www.rottentomatoes.com",
    "https://www.metacritic.com",
    "https://www.tvguide.com",
    "https://www.vulture.com",
    "https://www.hollywoodreporter.com",
    "https://www.variety.com",
    "https://www.ew.com",
    "https://www.screenrant.com",
    "https://www.comingsoon.net",
    "https://www.fandango.com",
    "https://www.gamespot.com",
    "https://www.ign.com",
    "https://www.polygon.com",
    "https://www.kotaku.com",
    "https://www.pcgamer.com",
    "https://www.eurogamer.net",

    # === SPORTS ===
    "https://www.espn.com",
    "https://www.cbssports.com",
    "https://www.bleacherreport.com",
    "https://www.nfl.com",
    "https://www.nba.com",
    "https://www.mlb.com",
    "https://www.nhl.com",
    "https://www.si.com",
    "https://www.theathletic.com",
    "https://www.skysports.com",
    "https://www.bbc.com/sport",
    "https://www.goal.com",
    "https://www.sofascore.com",

    # === FINANCE ===
    "https://www.investopedia.com",
    "https://www.marketwatch.com",
    "https://www.cnbc.com",
    "https://www.fool.com",
    "https://www.bankrate.com",
    "https://www.nerdwallet.com",
    "https://www.creditkarma.com",
    "https://finance.yahoo.com",
    "https://www.seekingalpha.com",
    "https://www.thestreet.com",
    "https://www.morningstar.com",

    # === LIFESTYLE, HEALTH & FOOD ===
    "https://www.weather.com",
    "https://www.accuweather.com",
    "https://www.webmd.com",
    "https://www.healthline.com",
    "https://www.mayoclinic.org",
    "https://www.medicalnewstoday.com",
    "https://www.allrecipes.com",
    "https://www.foodnetwork.com",
    "https://www.seriouseats.com",
    "https://www.epicurious.com",
    "https://www.bonappetit.com",
    "https://www.tasteofhome.com",
    "https://www.cookinglight.com",
    "https://www.self.com",
    "https://www.womenshealthmag.com",
    "https://www.menshealth.com",
    "https://www.shape.com",
    "https://www.prevention.com",
    "https://www.verywellhealth.com",
    "https://www.psychologytoday.com",

    # === TRAVEL ===
    "https://www.tripadvisor.com",
    "https://www.booking.com",
    "https://www.expedia.com",
    "https://www.kayak.com",
    "https://www.hotels.com",
    "https://www.airbnb.com",
    "https://www.lonelyplanet.com",
    "https://www.travelchannel.com",
    "https://www.fodors.com",
    "https://www.frommers.com",

    # === REAL ESTATE & LOCAL ===
    "https://www.zillow.com",
    "https://www.realtor.com",
    "https://www.redfin.com",
    "https://www.trulia.com",
    "https://www.yelp.com",
    "https://www.angi.com",
    "https://www.thumbtack.com",
    "https://www.apartments.com",
    "https://www.craigslist.org",

    # === REFERENCE & EDUCATION ===
    "https://en.wikipedia.org/wiki/Special:Random",
    "https://www.britannica.com",
    "https://www.howstuffworks.com",
    "https://www.khanacademy.org",
    "https://www.coursera.org",
    "https://www.udemy.com",
    "https://www.edx.org",
    "https://www.dictionary.com",
    "https://www.merriam-webster.com",
    "https://www.wolframalpha.com",
    "https://www.archive.org",
    "https://www.snopes.com",
    "https://www.gutenberg.org",
]

# ==========================================
# HUMAN BEHAVIOR LOGIC
# ==========================================
async def simulate_human_reading(page, dwell_modifier):
    """Simulates a human scrolling and reading a webpage."""
    try:
        # Number of scroll actions to take on this page
        scroll_steps = random.randint(3, 7)
        
        for _ in range(scroll_steps):
            # Scroll down by a random amount (simulating mouse wheel or trackpad)
            scroll_amount = random.randint(300, 800)
            await page.mouse.wheel(0, scroll_amount)
            
            # Pause to "read" - adjusted by the persona's dwell time modifier
            base_pause = random.uniform(1.5, 4.0)
            actual_pause = base_pause * dwell_modifier
            await asyncio.sleep(actual_pause)
            
    except Exception as e:
        print(f"Scrolling interrupted: {e}")


async def execute_warmup_routine(page, profile_data, mla_uuid):
    """Visits a few random seed sites to build a localized cookie history."""
    # Extract the persona's specific reading speed
    dwell_modifier = profile_data['behavioral_metrics'].get('dwell_time_modifier', 1.0)
    
    # Pick 3 to 5 random sites for this session
    num_sites = random.randint(3, 5)
    sites_to_visit = random.sample(SEED_SITES, num_sites)
    
    print(f"[{mla_uuid}] Warming up on {num_sites} sites...")
    
    for site in sites_to_visit:
        try:
            print(f"[{mla_uuid}] Navigating to {site}")
            # wait_until="domcontentloaded" is faster and prevents hanging on ads/videos
            await page.goto(site, wait_until="domcontentloaded", timeout=45000)
            
            # Wait a moment for trackers to fire
            await asyncio.sleep(random.uniform(2.0, 4.0))
            
            # Simulate scrolling and reading
            await simulate_human_reading(page, dwell_modifier)
            
        except Exception as e:
            print(f"[{mla_uuid}] ⚠️ Failed to load {site}: {e}")
            continue # Move on to the next site if one times out

    print(f"[{mla_uuid}] ✅ Warm-up session complete.")
    return True

# ==========================================
# CORE WORKER LOGIC
# ==========================================
async def process_profile(profile_data):
    mla_uuid = profile_data['mla_uuid']
    db_id = profile_data['id']
    
    start_url = f"http://127.0.0.1:{MLA_API_PORT}/api/v1/profile/start?automation=true&profileId={mla_uuid}"
    try:
        mla_response = await asyncio.to_thread(requests.get, start_url)
        mla_data = mla_response.json()
        
        if mla_data.get("status") != "OK":
            print(f"[{mla_uuid}] Failed to start MLA profile.")
            supabase.table('profiles').update({'status': 'error'}).eq('id', db_id).execute()
            return
            
        ws_endpoint = mla_data["value"]
        
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(ws_endpoint)
            context = browser.contexts[0]
            # Set default timeout to prevent hanging on slow proxies
            context.set_default_timeout(45000) 
            page = context.pages[0] if context.pages else await context.new_page()

            # Execute the warm-up browsing
            await execute_warmup_routine(page, profile_data, mla_uuid)
            
            # Release back to available pool
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
        stop_url = f"http://127.0.0.1:{MLA_API_PORT}/api/v1/profile/stop?profileId={mla_uuid}"
        await asyncio.to_thread(requests.get, stop_url)
        print(f"[{mla_uuid}] Profile stopped and cookies saved.")

# ==========================================
# ORCHESTRATION
# ==========================================
async def worker(worker_id, semaphore):
    while True:
        async with semaphore:
            # Note: You might want to filter this so it only picks up profiles 
            # that haven't been warmed up today.
            response = supabase.table('profiles')\
                .select('*').eq('status', 'available').limit(1).execute()
            
            if not response.data:
                print(f"Worker {worker_id} found no available profiles. Shutting down.")
                break 
                
            profile_data = response.data[0]
            
            supabase.table('profiles').update({'status': 'in_use'}).eq('id', profile_data['id']).execute()
            await process_profile(profile_data)
            await asyncio.sleep(2)

async def main():
    print(f"Starting COOKIE WARM-UP Phase (Max {MAX_CONCURRENT_BROWSERS} browsers)...")
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_BROWSERS)
    tasks = [asyncio.create_task(worker(i, semaphore)) for i in range(MAX_CONCURRENT_BROWSERS)]
    await asyncio.gather(*tasks)
    print("Warm-up phase completed for all available profiles.")

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())