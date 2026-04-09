import os
import json
import random
import asyncio
import time
import requests
from dotenv import load_dotenv
from pathlib import Path
from openai import AsyncOpenAI
from supabase import create_client, Client

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not all([OPENAI_API_KEY, SUPABASE_URL, SUPABASE_KEY]):
    raise ValueError("Missing API Keys in .env file.")

openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==========================================
# 1. BEHAVIORAL ARCHETYPES
# ==========================================
ARCHETYPES = [
    {
        "name": "Tech/Gamer (Gen Z)",
        "prompt_vibe": "an 18-25 year old obsessed with PC building, coding, and competitive gaming.",
        "behavior": {
            "typing_base_wpm": 95, "typing_error_rate": 0.04,
            "fitts_overshoot_probability": 0.05, "fitts_correction_speed": 1.2,
            "tab_switch_frequency": 0.45, "dwell_time_modifier": 0.8
        }
    },
    {
        "name": "DIY/Homeowner (Boomer/Gen X)",
        "prompt_vibe": "a 45-65 year old who loves woodworking, lawn care, classic cars, and grilling.",
        "behavior": {
            "typing_base_wpm": 30, "typing_error_rate": 0.12,
            "fitts_overshoot_probability": 0.22, "fitts_correction_speed": 0.8,
            "tab_switch_frequency": 0.10, "dwell_time_modifier": 1.8
        }
    },
    {
        "name": "Lifestyle/Design (Millennial)",
        "prompt_vibe": "a 25-35 year old into interior design, specialty coffee, productivity, and aesthetics.",
        "behavior": {
            "typing_base_wpm": 75, "typing_error_rate": 0.03,
            "fitts_overshoot_probability": 0.10, "fitts_correction_speed": 1.0,
            "tab_switch_frequency": 0.30, "dwell_time_modifier": 1.1
        }
    }
]

# ==========================================
# 2. UTILITY FUNCTIONS
# ==========================================
def parse_webshare_proxies(filepath="webshare_proxies.txt"):
    """Loads and formats the proxies."""
    proxies = []
    try:
        with open(filepath, 'r') as file:
            for line in file:
                parts = line.strip().split(':')
                if len(parts) >= 4:
                    proxies.append({
                        'proxy_ip': parts[0], 'proxy_port': parts[1],
                        'proxy_user': parts[2], 'proxy_pass': parts[3]
                    })
    except FileNotFoundError:
        print(f"Error: {filepath} not found.")
    return proxies

def get_location_from_ip(ip_address):
    """Resolves IP safely (45 requests per minute limit)."""
    try:
        res = requests.get(f"http://ip-api.com/json/{ip_address}").json()
        if res.get('status') == 'success':
            return res.get('city'), res.get('regionName'), res.get('timezone')
    except Exception:
        pass
    return "Austin", "Texas", "America/Chicago" # Fallback

# ==========================================
# 3. OPENAI PERSONA GENERATION
# ==========================================
async def generate_ai_persona(profile_id, proxy_data, index):
    """Fuses proxy location with OpenAI personality generation."""
    
    # 1. Get the exact location of the proxy IP
    ip = proxy_data['proxy_ip']
    city, state, timezone = get_location_from_ip(ip)
    
    # 2. Pick an archetype
    archetype = random.choice(ARCHETYPES)
    
    # 3. Prompt OpenAI strictly with the IP's location
    prompt = f"""
    You are generating a synthetic internet user for a simulation.
    Target Archetype: {archetype['prompt_vibe']}
    CRITICAL LOCATION RULE: This person lives specifically in {city}, {state}.
    
    Output a raw JSON object (NO markdown, NO code blocks) with this exact structure:
    {{
        "username": "firstname_lastname_year",
        "name": "Firstname Lastname",
        "gender": "Male or Female",
        "age": integer,
        "occupation": "A realistic job title",
        "topics": [
            10 highly specific, niche Google/YouTube search topics. 
            Mix their archetype hobbies with hyper-local {city} searches (e.g., local restaurants, local news, local stores).
        ]
    }}
    """
    
    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8
        )
        
        raw_text = response.choices[0].message.content.strip()
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:-3].strip()
            
        ai_data = json.loads(raw_text)
        
        # 4. Map everything to our Supabase database schema
        final_profile = {
            "profile_id": f"PR-{str(index).zfill(4)}",
            "network": proxy_data,
            "location": {
                "country": "US",
                "state": state,
                "city": city,
                "timezone": timezone
            },
            "demographics": {
                "username": ai_data["username"],
                "name": ai_data["name"],
                "gender": ai_data["gender"],
                "occupation": ai_data["occupation"],
                "interests": ai_data["topics"] # The 10 AI-generated local topics
            },
            "behavioral_metrics": archetype["behavior"],
            "status": "available"
        }
        
        return final_profile
        
    except Exception as e:
        print(f"❌ Failed to generate AI profile for IP {ip}: {e}")
        return None

# ==========================================
# 4. ORCHESTRATION
# ==========================================
async def main():
    proxy_list = parse_webshare_proxies()
    if not proxy_list:
        return
        
    total_proxies = len(proxy_list)
    print(f"🚀 Loaded {total_proxies} proxies. Starting Smart Generation Pipeline...")
    
    final_personas = []
    
    # We must process sequentially with a small delay because ip-api.com 
    # will block us if we fire 500 IP lookups concurrently.
    for i, proxy_data in enumerate(proxy_list, 1):
        print(f"Generating Profile {i}/{total_proxies} (IP: {proxy_data['proxy_ip']})...")
        
        persona = await generate_ai_persona(f"PR-{str(i).zfill(4)}", proxy_data, i)
        if persona:
            final_personas.append(persona)
            
        # 1.5s delay to stay safely under 45 requests/minute for IP resolution
        await asyncio.sleep(1.5) 
        
    print("\n✅ All personas generated. Pushing directly to Supabase...")
    
    # Upsert the entire batch directly to your database
    try:
        supabase.table('profiles').upsert(final_personas).execute()
        print(f"🏁 SUCCESS: {len(final_personas)} highly-entropic, geo-locked profiles stored in Supabase!")
    except Exception as e:
        print(f"❌ Database Upload Error: {e}")
        
        # Emergency backup: Save to file if DB fails
        with open("emergency_backup_personas.json", "w") as f:
            json.dump(final_personas, f, indent=4)
        print("Data saved locally to emergency_backup_personas.json instead.")

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())