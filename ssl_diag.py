import asyncio
import ssl
import certifi
from dotenv import load_dotenv
load_dotenv()

# Step 1: inject truststore (like main.py does)
import truststore
truststore.inject_into_ssl()
print("[1] truststore injected globally")

# Step 2: check if our SSL context is still clean
import httpx
ctx = ssl.create_default_context(cafile=certifi.where())
print("[2] SSL context built with certifi CA")

# Step 3: try a direct httpx call with this clean context
import os
key = os.getenv("OPENAI_API_KEY")
print(f"[3] Key starts with: {key[:15]}")

async def test():
    async with httpx.AsyncClient(verify=ctx, timeout=15.0) as client:
        try:
            r = await client.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {key}"}
            )
            print(f"[4] HTTPX direct call: {r.status_code}")
        except Exception as e:
            print(f"[4] HTTPX direct call FAILED: {type(e).__name__}: {e}")

asyncio.run(test())
