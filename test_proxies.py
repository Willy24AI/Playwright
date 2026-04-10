"test_proxies.py"

import asyncio
import aiohttp
import time

PROXY_FILE = "webshare_proxies.txt"
TEST_URL = "http://ip-api.com/json" # Fast, lightweight endpoint that returns the IP

def load_proxies(filepath):
    """Parses the Webshare proxy file."""
    proxies = []
    try:
        with open(filepath, 'r') as f:
            for line in f:
                parts = line.strip().split(':')
                if len(parts) >= 4:
                    proxies.append({
                        'ip': parts[0],
                        'port': parts[1],
                        'user': parts[2],
                        'pass': parts[3],
                        # aiohttp requires this specific proxy URL format
                        'url': f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
                    })
    except FileNotFoundError:
        print(f"Error: Could not find {filepath}.")
    return proxies

async def test_single_proxy(session, proxy_data):
    """Tests a single proxy and verifies the IP matches."""
    proxy_url = proxy_data['url']
    expected_ip = proxy_data['ip']
    
    try:
        # 10-second timeout. If a proxy takes longer than this to route, 
        # it will cause Playwright scripts to fail later.
        timeout = aiohttp.ClientTimeout(total=10)
        
        async with session.get(TEST_URL, proxy=proxy_url, timeout=timeout) as response:
            if response.status == 200:
                data = await response.json()
                returned_ip = data.get('query')
                
                if returned_ip == expected_ip:
                    return {"ip": expected_ip, "status": "Alive", "geo": data.get('regionName', 'Unknown')}
                else:
                    return {"ip": expected_ip, "status": "IP Mismatch / Leak", "geo": "N/A"}
            else:
                return {"ip": expected_ip, "status": f"HTTP {response.status}", "geo": "N/A"}
                
    except asyncio.TimeoutError:
        return {"ip": expected_ip, "status": "Timeout (Dead or Slow)", "geo": "N/A"}
    except Exception as e:
        return {"ip": expected_ip, "status": "Connection Failed", "geo": "N/A"}

async def main():
    proxies = load_proxies(PROXY_FILE)
    if not proxies:
        return
        
    print(f"Loaded {len(proxies)} proxies from {PROXY_FILE}. Beginning asynchronous testing...")
    start_time = time.time()
    
    alive_count = 0
    dead_proxies = []

    # Using a TCPConnector to limit concurrent connections and avoid overwhelming the OS
    connector = aiohttp.TCPConnector(limit=50)
    async with aiohttp.ClientSession(connector=connector) as session:
        # Create a task for every proxy
        tasks = [test_single_proxy(session, p) for p in proxies]
        
        # Run them all concurrently
        results = await asyncio.gather(*tasks)
        
        for res in results:
            if res["status"] == "Alive":
                alive_count += 1
                # print(f"✅ {res['ip']} is Alive ({res['geo']})") # Uncomment if you want spammy logs
            else:
                dead_proxies.append(res)
                print(f"❌ {res['ip']} Failed: {res['status']}")

    print("\n" + "="*40)
    print("PROXY TEST RESULTS")
    print("="*40)
    print(f"Total Proxies: {len(proxies)}")
    print(f"Alive & Routing: {alive_count}")
    print(f"Dead / Failed: {len(dead_proxies)}")
    print(f"Time Taken: {round(time.time() - start_time, 2)} seconds")
    
    if dead_proxies:
        print("\nRecommendation: Replace the failed proxies in your Webshare dashboard before running the persona generation script.")

if __name__ == "__main__":
    # Windows asyncio fix
    import os
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())