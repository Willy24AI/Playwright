"""
llm_helper.py
-------------
Handles dynamic generation of search terms, documents, and comments using OpenAI.

[FIXED]:
- Uses profile interests directly (from demographics.interests) as PRIMARY search source
- OpenAI is an ENHANCEMENT, not a dependency — if it fails, interests are used directly
- Reads location from the correct field path (persona.location or profile.location)
- No more "interesting videos" fallback spam
- Adds natural variation to interest-based searches without needing LLM
"""

import os
import logging
import random
import re
from openai import AsyncOpenAI

log = logging.getLogger(__name__)

# Initialize the async client
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# ---------------------------------------------------------------------------
# INTEREST-BASED SEARCH (NO LLM NEEDED)
# ---------------------------------------------------------------------------

def _get_profile_interests(profile: dict) -> list:
    """Extract interests from profile, checking all possible field locations."""
    interests = []
    
    # Check persona.interests (set by profiles_config.py mapper)
    persona = profile.get("persona", {})
    if isinstance(persona, dict):
        interests = persona.get("interests", [])
    
    # Fallback: check demographics.interests directly
    if not interests:
        demographics = profile.get("demographics", {})
        if isinstance(demographics, dict):
            interests = demographics.get("interests", [])
    
    # Fallback: check top-level topics
    if not interests:
        interests = profile.get("topics", [])
    
    return interests if interests else []

def _get_profile_location(profile: dict) -> dict:
    """Extract location from profile, checking all possible field locations."""
    # Check persona.location (set by profiles_config.py mapper)
    persona = profile.get("persona", {})
    if isinstance(persona, dict):
        loc = persona.get("location", {})
        if loc and loc.get("city"):
            return loc
    
    # Fallback: check top-level location
    loc = profile.get("location", {})
    if isinstance(loc, dict) and loc.get("city"):
        return loc
    
    return {}

def _get_persona_info(profile: dict) -> dict:
    """Extract persona display info."""
    persona = profile.get("persona", {})
    demographics = profile.get("demographics", {})
    location = _get_profile_location(profile)
    
    return {
        "name": persona.get("name") or demographics.get("name", "a user"),
        "city": location.get("city", ""),
        "state": location.get("state", ""),
        "occupation": demographics.get("occupation", ""),
    }

def _pick_interest_search(profile: dict) -> str:
    """
    Pick a search query directly from the profile's interests.
    These are already great search queries like "Dallas esports tournaments 2023".
    Adds slight natural variation.
    """
    interests = _get_profile_interests(profile)
    
    if not interests:
        # Absolute last resort — generic but varied
        generic = [
            "trending videos today", "things to do this weekend",
            "best new movies 2024", "cool tech gadgets", 
            "how to learn something new", "funny videos compilation",
            "life hacks everyone should know", "best podcasts right now",
            "what to watch on youtube", "interesting documentaries"
        ]
        return random.choice(generic)
    
    # Pick a random interest
    query = random.choice(interests)
    
    # 30% chance to add a natural modifier
    if random.random() < 0.30:
        modifiers = [
            "", "reddit", "2024", "best", "how to", 
            "near me", "tutorial", "explained", "review", "tips"
        ]
        mod = random.choice(modifiers)
        if mod:
            # Sometimes prepend, sometimes append
            if random.random() < 0.5:
                query = f"{mod} {query}"
            else:
                query = f"{query} {mod}"
    
    return query


# ---------------------------------------------------------------------------
# LLM-ENHANCED SEARCH (OPTIONAL — FALLS BACK TO INTERESTS)
# ---------------------------------------------------------------------------

async def _safe_generate(system_prompt: str, user_prompt: str, token_limit: int, temp: float) -> str:
    """Internal helper to securely call OpenAI and strip conversational filler."""
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temp, 
            max_tokens=token_limit,
            presence_penalty=0.6, 
            frequency_penalty=0.3,
            timeout=10  # Don't hang forever
        )
        
        output = response.choices[0].message.content.strip()
        
        # Aggressive Sanitization
        output = output.strip('\'"*.')
        output = re.sub(r"^(here is|sure,?|the domain is|query:)\s*", "", output, flags=re.IGNORECASE).strip()
        
        return output
        
    except Exception as e:
        log.warning(f"    ⚠️ LLM generation failed: {e}")
        return ""


async def generate_dynamic_search(profile: dict, platform: str) -> str:
    """
    Generate a search query for the given platform.
    
    Strategy:
    1. Try OpenAI for a creative, varied query (50% of the time)
    2. If OpenAI fails OR 50% of the time, use profile interests directly
    3. Profile interests are already excellent localized queries
    """
    interests = _get_profile_interests(profile)
    info = _get_persona_info(profile)
    location = _get_profile_location(profile)
    
    # Pick a focus topic from interests
    focus_topic = random.choice(interests) if interests else "interesting videos"
    
    # Build context for LLM
    city = location.get("city", "a city")
    state = location.get("state", "")
    name = info.get("name", "a user")
    occupation = info.get("occupation", "")
    
    user_prompt = (
        f"I am {name}, "
        f"{f'a {occupation} ' if occupation else ''}"
        f"living in {city}{f', {state}' if state else ''}. "
        f"My current interest: '{focus_topic}'."
    )

    # Base System Prompt
    base_system = (
        "You are the internal thought process of a human web user. "
        "CRITICAL RULE: Never explain yourself. Never use conversational filler like 'Sure' or 'Here is'. "
        "Output ONLY the exact raw text requested, without quotation marks."
    )

    # --- PLATFORM-SPECIFIC GENERATION ---
    
    if platform == "Google Docs Draft":
        system_prompt = base_system + " Write a realistic, 3-to-4 sentence paragraph about the user's interest. Do NOT use hashtags, emojis, or titles."
        output = await _safe_generate(system_prompt, user_prompt, 150, 0.85)
        return output or "Project outline: Needs more research and formatting before finalizing."

    elif platform == "Google Calendar Event":
        system_prompt = base_system + " Write exactly ONE short, highly realistic calendar event title (2 to 6 words). Examples: Zoom call about X, Read up on X."
        output = await _safe_generate(system_prompt, user_prompt, 15, 0.80)
        return output or "Review project notes"

    elif platform == "Google News":
        system_prompt = base_system + " Generate ONE short, specific search query for the Google News search bar. Keep it lowercase."
        output = await _safe_generate(system_prompt, user_prompt, 20, 0.90)
        return output or focus_topic

    elif platform in ["Shopping Target", "OAuth Target", "Direct News Domain"]:
        system_prompt = base_system + (
            " Identify a popular, high-authority website for this interest. "
            "STRICT RULES: Return ONLY the raw domain name (e.g., 'amazon.com', 'pinterest.com', 'theverge.com'). "
            "Do NOT include https:// or www."
        )
        output = await _safe_generate(system_prompt, user_prompt, 15, 0.5)
        output = output.lower().replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]
        return output or "amazon.com"

    elif platform == "Shopping Query":
        system_prompt = base_system + " Generate ONE specific commercial search query for a high-end product you would buy related to this interest. Example: 'sony a7iv price'."
        output = await _safe_generate(system_prompt, user_prompt, 20, 0.85)
        return output or f"buy {focus_topic}"

    elif platform == "Drive Folder":
        system_prompt = base_system + " Generate ONE short, casual name for a personal Google Drive folder related to this interest. Sometimes use lowercase."
        output = await _safe_generate(system_prompt, user_prompt, 15, 0.85)
        return output or "references"

    else:
        # --- STANDARD SEARCH (YouTube, Google, etc.) ---
        # 50% chance: use LLM for creative variation
        # 50% chance: use profile interests directly (already great queries)
        use_llm = random.random() < 0.50 and interests
        
        if use_llm:
            intents = [
                "troubleshoot a specific problem", "find a beginner tutorial", 
                "find entertaining long-form content", "buy something cheap", 
                "find the latest drama/news", "find an obscure weird fact"
            ]
            intent = random.choice(intents)
            modifiers = ["reddit", "step by step", "for dummies", "vs", "review", "explained", "near me"]
            mod = f" Optionally include '{random.choice(modifiers)}'." if random.random() < 0.4 else ""

            system_prompt = base_system + f" Situation: The user wants to {intent} regarding their interest. Generate ONE casual, highly specific web search query. Make it sound human.{mod}"
            output = await _safe_generate(system_prompt, user_prompt, 20, 0.9)
            
            if output:
                return output
        
        # Direct interest-based search (no LLM needed — these are already perfect)
        return _pick_interest_search(profile)


async def generate_contextual_comment(profile: dict, video_title: str, video_desc: str) -> str:
    """Generate a contextual YouTube comment."""
    info = _get_persona_info(profile)
    safe_desc = video_desc[:500].replace("\n", " ") if video_desc else "No description."
    
    vibes = [
        "extremely grateful because this solved a problem", "mildly disagreeing with one small point",
        "pointing out a random detail from the video", "sharing a brief 1-sentence personal anecdote",
        "asking a genuine follow-up question", "dropping a casual lazy reaction (like 'real' or 'big mood')",
        "adding a tiny bit of armchair expert info", "complaining about how hard this topic usually is"
    ]
    formats = [
        "entirely in lowercase with zero punctuation", "perfect grammar and capitalization",
        "casual internet grammar with exactly one emoji", "include a filler acronym (tbh, ngl, lol)",
        "an abrupt, fragmented sentence"
    ]

    system_prompt = (
        "You are an automated YouTube commenter. "
        "CRITICAL RULES: DO NOT use generic bot phrases ('Great video!', 'Thanks for sharing!'). "
        "DO NOT use AI buzzwords ('delve', 'moreover', 'testament'). "
        "DO NOT use quotes or hashtags. Output ONLY the raw comment text."
    )
    
    user_prompt = (
        f"I am {info['name']}, "
    )
    occupation = info.get("occupation", "")
    if occupation:
        user_prompt += f"a {occupation} "
    city = info.get("city") or "somewhere"
    user_prompt += (
        f"from {city}. "
        f"I watched '{video_title}'. Context: '{safe_desc}'. "
        f"VIBE: {random.choice(vibes)}. FORMATTING: {random.choice(formats)}. Keep under 15 words."
    )

    output = await _safe_generate(system_prompt, user_prompt, 35, 0.85)
    
    if output:
        log.info(f"    🧠 LLM generated comment: '{output}'")
        return output
    else:
        fallbacks = [
            "this is actually crazy tbh", "saving this for later", 
            "i needed this today lol", "wait is this actually real?",
            "bro this is exactly what i was looking for",
            "why did it take me so long to find this",
            "ngl this actually helped a lot"
        ]
        return random.choice(fallbacks)