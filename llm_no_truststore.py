import asyncio
from dotenv import load_dotenv
load_dotenv()

# NO truststore here
print("[1] No truststore injected")

from llm_helper import generate_dynamic_search

async def main():
    test_profile = {
        "persona": {"name": "TestUser", "interests": ["gaming"], "location": {"city": "Boston", "state": "MA"}},
        "demographics": {"occupation": "engineer"}
    }
    result = await generate_dynamic_search(test_profile, "Direct News Domain")
    print("LLM returned:", result)

asyncio.run(main())
