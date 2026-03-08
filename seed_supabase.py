"""
seed_supabase.py
----------------
Run this ONCE to push your 7 profiles into your new Supabase database.
"""
import os
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client, Client

# Load .env file
load_dotenv(dotenv_path=Path(__file__).parent / ".env")

# 1. Connect to Supabase
url: str = os.getenv("SUPABASE_URL")
key: str = os.getenv("SUPABASE_KEY")
if not url or not key:
    raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY in .env")
    
supabase: Client = create_client(url, key)

def _pid(n: int) -> str:
    # Pulls the MLX IDs from your existing .env file
    return os.getenv(f"PROFILE_{n}", f"fallback-id-{n}").strip()

# 2. Your 7 Master Profiles (Updated to use 'mlx_profile_id' directly!)
PROFILES_TO_UPLOAD = [
    {
        "id": "sarah_nyc",
        "mlx_profile_id": _pid(1),
        "persona": {"name": "Sarah", "age": 34, "city": "New York"},
        "browser": {"timezone": "America/New_York", "locale": "en-US", "viewport": {"width": 1440, "height": 900}},
        "behavior": {
            "wpm_range": (70, 95), "typo_rate": 0.02, "typo_correction_delay": (150, 400),
            "scroll_chunk": (200, 450), "scroll_sessions": (2, 4), "back_scroll_chance": 0.05,
            "read_pause_range": (4, 10), "idle_drift_chance": 0.25, "pre_click_hover_ms": (80, 200),
            "result_position_weights": [7, 5, 3, 2, 1, 1, 1, 1],
        },
        "topics": [
            "best project management tools for remote teams", "how to write a performance review", 
            "content marketing trends this year", "linkedin profile tips for managers",
            "quick healthy dinner recipes after work", "pilates vs yoga for back pain",
            "NYC restaurant week deals", "best coffee shops to work from in Manhattan"
        ],
        "is_active": True
    },
    {
        "id": "marcus_austin",
        "mlx_profile_id": _pid(2),
        "persona": {"name": "Marcus", "age": 22, "city": "Austin"},
        "browser": {"timezone": "America/Chicago", "locale": "en-US", "viewport": {"width": 1366, "height": 768}},
        "behavior": {
            "wpm_range": (85, 115), "typo_rate": 0.07, "typo_correction_delay": (100, 300),
            "scroll_chunk": (100, 280), "scroll_sessions": (5, 9), "back_scroll_chance": 0.18,
            "read_pause_range": (12, 25), "idle_drift_chance": 0.40, "pre_click_hover_ms": (200, 550),
            "result_position_weights": [4, 4, 3, 3, 3, 2, 2, 1],
        },
        "topics": [
            "how to learn rust programming language", "neovim vs vscode which is better",
            "best mechanical keyboard switches for typing", "best budget gaming monitor 144hz",
            "push pull legs workout routine", "austin texas tech scene"
        ],
        "is_active": True
    },
    {
        "id": "linda_chicago",
        "mlx_profile_id": _pid(3),
        "persona": {"name": "Linda", "age": 58, "city": "Chicago"},
        "browser": {"timezone": "America/Chicago", "locale": "en-US", "viewport": {"width": 1280, "height": 800}},
        "behavior": {
            "wpm_range": (20, 35), "typo_rate": 0.05, "typo_correction_delay": (800, 1500),
            "scroll_chunk": (80, 200), "scroll_sessions": (4, 7), "back_scroll_chance": 0.22,
            "read_pause_range": (18, 40), "idle_drift_chance": 0.50, "pre_click_hover_ms": (400, 900),
            "result_position_weights": [6, 5, 4, 3, 2, 1, 1, 1],
        },
        "topics": [
            "best anti inflammatory foods for joint pain", "easy chair yoga for seniors beginners",
            "how to video call grandchildren ipad", "how to cancel a subscription on iphone",
            "chicago architecture boat tour", "chicago weather forecast next week"
        ],
        "is_active": True
    },
    {
        "id": "james_london",
        "mlx_profile_id": _pid(4),
        "persona": {"name": "James", "age": 41, "city": "London"},
        "browser": {"timezone": "Europe/London", "locale": "en-GB", "viewport": {"width": 1920, "height": 1080}},
        "behavior": {
            "wpm_range": (60, 80), "typo_rate": 0.03, "typo_correction_delay": (200, 500),
            "scroll_chunk": (150, 350), "scroll_sessions": (3, 6), "back_scroll_chance": 0.10,
            "read_pause_range": (8, 18), "idle_drift_chance": 0.30, "pre_click_hover_ms": (120, 300),
            "result_position_weights": [6, 5, 4, 3, 2, 2, 1, 1],
        },
        "topics": [
            "uk inflation forecast 2026", "best index funds to invest in uk",
            "best espresso machine under 500 pounds", "golf swing slow motion analysis",
            "london property market outlook", "best pubs for sunday roast london"
        ],
        "is_active": True
    },
    {
        "id": "priya_la",
        "mlx_profile_id": _pid(5),
        "persona": {"name": "Priya", "age": 29, "city": "Los Angeles"},
        "browser": {"timezone": "America/Los_Angeles", "locale": "en-US", "viewport": {"width": 1536, "height": 864}},
        "behavior": {
            "wpm_range": (65, 90), "typo_rate": 0.04, "typo_correction_delay": (180, 450),
            "scroll_chunk": (180, 420), "scroll_sessions": (2, 5), "back_scroll_chance": 0.07,
            "read_pause_range": (5, 12), "idle_drift_chance": 0.35, "pre_click_hover_ms": (100, 280),
            "result_position_weights": [5, 5, 4, 3, 3, 2, 1, 1],
        },
        "topics": [
            "figma vs adobe xd comparison", "best free fonts for graphic designers",
            "thrift flip clothing ideas", "matcha latte recipe at home",
            "los angeles hidden gems hiking", "best vegan food trucks LA"
        ],
        "is_active": True
    },
    {
        "id": "tom_houston",
        "mlx_profile_id": _pid(6),
        "persona": {"name": "Tom", "age": 47, "city": "Houston"},
        "browser": {"timezone": "America/Chicago", "locale": "en-US", "viewport": {"width": 1280, "height": 720}},
        "behavior": {
            "wpm_range": (18, 30), "typo_rate": 0.12, "typo_correction_delay": (600, 1500),
            "scroll_chunk": (120, 300), "scroll_sessions": (3, 6), "back_scroll_chance": 0.15,
            "read_pause_range": (10, 22), "idle_drift_chance": 0.45, "pre_click_hover_ms": (300, 700),
            "result_position_weights": [5, 4, 4, 3, 3, 2, 2, 1],
        },
        "topics": [
            "how to fix a leaking kitchen faucet", "how to patch drywall hole yourself",
            "f150 oil change tutorial", "best offset smokers for beginners",
            "classic rock guitar solos", "houston astros highlights"
        ],
        "is_active": True
    },
    {
        "id": "yuki_seattle",
        "mlx_profile_id": _pid(7),
        "persona": {"name": "Yuki", "age": 26, "city": "Seattle"},
        "browser": {"timezone": "America/Los_Angeles", "locale": "en-US", "viewport": {"width": 1440, "height": 900}},
        "behavior": {
            "wpm_range": (90, 120), "typo_rate": 0.02, "typo_correction_delay": (100, 250),
            "scroll_chunk": (250, 500), "scroll_sessions": (6, 11), "back_scroll_chance": 0.20,
            "read_pause_range": (15, 35), "idle_drift_chance": 0.35, "pre_click_hover_ms": (100, 300),
            "result_position_weights": [4, 4, 4, 3, 3, 2, 2, 2],
        },
        "topics": [
            "how does transformer architecture work nlp", "best research papers on reinforcement learning",
            "best mechanical pencils for drawing", "how to solve a rubiks cube blindfolded",
            "seattle rainy day outfit aesthetic", "best indie bookstores seattle"
        ],
        "is_active": True
    }
]

def run_seed():
    print(f"🚀 Uploading {len(PROFILES_TO_UPLOAD)} profiles to Supabase...")
    for profile in PROFILES_TO_UPLOAD:
        try:
            # Upsert will insert or update if 'id' already exists
            supabase.table("bot_profiles").upsert(profile).execute()
            print(f"  ✅ Uploaded: {profile['id']}")
        except Exception as e:
            print(f"  ❌ Failed {profile['id']}: {e}")
            
    print("\n🏁 Seeding complete! You can verify this in your Supabase Table Editor.")

if __name__ == "__main__":
    run_seed()