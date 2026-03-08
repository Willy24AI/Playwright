"""
generate_farm.py
----------------
Automated pipeline to generate 1000 unique profiles and push them to Supabase.
"""
import os
import json
import random
import asyncio
from dotenv import load_dotenv
from pathlib import Path
from openai import AsyncOpenAI
from supabase import create_client, Client

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

# 1. Initialize Clients
openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# 2. Define Base Archetypes (Controls physical behavior and topic direction)
ARCHETYPES = [
    {
        "name": "Tech/Gamer (Gen Z)",
        "prompt_vibe": "a 18-25 year old obsessed with PC building, coding, and competitive gaming.",
        "behavior": {
            "wpm_range": [85, 115], "typo_rate": 0.07, "typo_correction_delay": [100, 300],
            "scroll_chunk": [200, 400], "scroll_sessions": [4, 8], "back_scroll_chance": 0.15,
            "read_pause_range": [8, 20], "idle_drift_chance": 0.40, "pre_click_hover_ms": [100, 300],
            "result_position_weights": [4, 4, 3, 3, 3, 2, 2, 1],
        }
    },
    {
        "name": "DIY/Homeowner (Boomer/Gen X)",
        "prompt_vibe": "a 45-65 year old who loves woodworking, lawn care, classic cars, and grilling.",
        "behavior": {
            "wpm_range": [20, 35], "typo_rate": 0.10, "typo_correction_delay": [600, 1500],
            "scroll_chunk": [80, 200], "scroll_sessions": [3, 6], "back_scroll_chance": 0.22,
            "read_pause_range": [15, 35], "idle_drift_chance": 0.45, "pre_click_hover_ms": [400, 800],
            "result_position_weights": [6, 5, 4, 3, 2, 1, 1, 1],
        }
    },
    {
        "name": "Lifestyle/Design (Millennial)",
        "prompt_vibe": "a 25-35 year old into interior design, specialty coffee, productivity, and aesthetics.",
        "behavior": {
            "wpm_range": [65, 90], "typo_rate": 0.04, "typo_correction_delay": [180, 450],
            "scroll_chunk": [180, 420], "scroll_sessions": [3, 6], "back_scroll_chance": 0.10,
            "read_pause_range": [10, 25], "idle_drift_chance": 0.35, "pre_click_hover_ms": [150, 400],
            "result_position_weights": [5, 5, 4, 3, 3, 2, 1, 1],
        }
    }
]

# Timezones to randomly assign
TIMEZONES = [
    ("America/New_York", "en-US"), 
    ("America/Chicago", "en-US"), 
    ("America/Denver", "en-US"), 
    ("America/Los_Angeles", "en-US")
]

async def generate_single_profile(mlx_id: str, index: int):
    """Generates the AI persona and pushes it to Supabase."""
    archetype = random.choice(ARCHETYPES)
    tz, locale = random.choice(TIMEZONES)
    
    # Prompt OpenAI to return a JSON object with the persona data
    prompt = f"""
    You are generating a synthetic internet user for a simulation.
    Target Archetype: {archetype['prompt_vibe']}
    
    Output a raw JSON object (NO markdown formatting, NO code blocks, just raw JSON) with this exact structure:
    {{
        "id": "firstname_city", (e.g., 'dave_austin', all lowercase)
        "persona": {{
            "name": "Firstname",
            "age": integer,
            "city": "US City Name"
        }},
        "topics": [
            15 highly specific, niche youtube search topics this person would care about. Mix hobbies, career, and local city searches.
        ]
    }}
    """
    
    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9
        )
        
        # Parse the JSON response from OpenAI
        raw_text = response.choices[0].message.content.strip()
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:-3].strip() # Clean up markdown if LLM misbehaves
            
        ai_data = json.loads(raw_text)
        
        # Build the final profile object
        final_profile = {
            "id": ai_data["id"] + f"_{index}", # Ensure unique ID just in case (e.g., dave_austin_42)
            "mlx_profile_id": mlx_id,
            "persona": ai_data["persona"],
            "browser": {
                "timezone": tz,
                "locale": locale,
                "viewport": {"width": random.choice([1280, 1366, 1440, 1536, 1920]), 
                             "height": random.choice([720, 768, 864, 900, 1080])}
            },
            "behavior": archetype["behavior"],
            "topics": ai_data["topics"],
            "is_active": True
        }
        
        # Push to Supabase
        supabase.table("bot_profiles").upsert(final_profile).execute()
        print(f"✅ Generated & Uploaded [{index}]: {final_profile['id']} ({archetype['name']})")
        
    except Exception as e:
        print(f"❌ Failed on index {index} (MLX: {mlx_id}): {e}")

async def main():
    # 1. Provide your list of 1000 Multilogin IDs here. 
    # (In reality, you could export a CSV from MLX and load it here, or call the MLX API to list all profiles).
    # For demonstration, here are dummy IDs:
    mlx_ids = [f"mlx-uuid-100{i}" for i in range(1000)] 
    
    print(f"🚀 Starting generation of {len(mlx_ids)} profiles...")
    
    # Process in batches of 10 concurrently so we don't hit OpenAI API limits
    batch_size = 10
    for i in range(0, len(mlx_ids), batch_size):
        batch = mlx_ids[i:i + batch_size]
        tasks = [generate_single_profile(mlx_id, i + j) for j, mlx_id in enumerate(batch)]
        await asyncio.gather(*tasks)
        print(f"⏳ Batch complete. Pausing to respect API rate limits...")
        await asyncio.sleep(2) # Brief pause to avoid 429 Rate Limit errors from OpenAI
        
    print("🏁 All 1,000 profiles successfully generated and stored in Supabase!")

if __name__ == "__main__":
    asyncio.run(main())