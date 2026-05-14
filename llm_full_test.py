import asyncio
from dotenv import load_dotenv
load_dotenv()  # MUST be before importing llm_helper

try:
    import truststore
    truststore.inject_into_ssl()
    print("truststore injected globally")
except ImportError:
    print("truststore not available")

from llm_helper import generate_dynamic_search

async def main():
    test_profile = {
        "persona": {"name": "TestUser", "interests": ["gaming"], "location": {"city": "Boston", "state": "MA"}},
        "demographics": {"occupation": "engineer"}
    }
    result = await generate_dynamic_search(test_profile, "Direct News Domain")
    print("LLM returned:", result)

asyncio.run(main())