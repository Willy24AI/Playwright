"""Quick test to check if a profile's proxy is alive."""
from dotenv import load_dotenv
import os
load_dotenv()

try:
    import truststore
    truststore.inject_into_ssl()
except:
    pass

from supabase import create_client
import requests

sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))

# Test a few profiles that showed "proxy dead"
test_profiles = ["PR-0021", "PR-0012", "PR-0042", "PR-0034", "PR-0053"]

for pid in test_profiles:
    r = sb.table("profiles").select("profile_id, network").eq("profile_id", pid).execute()
    if not r.data:
        print(f"{pid}: NOT FOUND in Supabase")
        continue
    
    n = r.data[0]["network"]
    if not n:
        print(f"{pid}: NO PROXY DATA")
        continue
    
    ip = n.get("proxy_ip", "")
    port = n.get("proxy_port", "")
    user = n.get("proxy_user", "")
    pwd = n.get("proxy_pass", "")
    
    print(f"\n{pid}: {ip}:{port} (user: {user[:8]}...)")
    
    try:
        proxy_url = f"http://{user}:{pwd}@{ip}:{port}"
        resp = requests.get(
            "https://httpbin.org/ip",
            proxies={"http": proxy_url, "https": proxy_url},
            timeout=15
        )
        print(f"  ✅ ALIVE — Response: {resp.text.strip()}")
    except Exception as e:
        print(f"  ❌ DEAD — Error: {str(e)[:80]}")