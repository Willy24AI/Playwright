import os
from dotenv import load_dotenv
load_dotenv()
key = os.getenv("OPENAI_API_KEY")
print(f"Key starts with: {key[:15] if key else 'NONE'}...")
print(f"Key length: {len(key) if key else 0}")

from openai import OpenAI
client = OpenAI(api_key=key)
try:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Say hi"}],
        max_tokens=10
    )
    print(f"SUCCESS: {response.choices[0].message.content}")
except Exception as e:
    print(f"FAIL: {type(e).__name__}: {e}")
