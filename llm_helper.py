"""
llm_helper.py
-------------
Handles dynamic generation of search terms, documents, and comments using OpenAI.
Upgraded with Strict System Prompts and Output Sanitization to prevent 
conversational filler from breaking the automation UI.
"""

import os
import logging
import random
import re
from openai import AsyncOpenAI

log = logging.getLogger(__name__)

# Initialize the async client
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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
            frequency_penalty=0.3
        )
        
        output = response.choices[0].message.content.strip()
        
        # Aggressive Sanitization: Remove rogue quotes, asterisks, or conversational prefixes
        output = output.strip('\'"*.')
        output = re.sub(r"^(here is|sure,?|the domain is|query:)\s*", "", output, flags=re.IGNORECASE).strip()
        
        return output
        
    except Exception as e:
        log.warning(f"    ⚠️ LLM generation failed: {e}")
        return ""

async def generate_dynamic_search(profile: dict, platform: str) -> str:
    persona = profile.get("persona", {})
    
    # 1. Pick just ONE topic to focus on today
    focus_topic = random.choice(profile.get("topics", ["interesting videos"]))
        
    user_prompt = f"I am {persona.get('name', 'a user')}, a {persona.get('age', '30')}-year-old living in {persona.get('city', 'a city')}. My current focus is: '{focus_topic}'."

    # 2. Base System Prompt (Enforces strict robotic compliance)
    base_system = (
        "You are the internal thought process of a human web user. "
        "CRITICAL RULE: Never explain yourself. Never use conversational filler like 'Sure' or 'Here is'. "
        "Output ONLY the exact raw text requested, without quotation marks."
    )

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
        
        # Extra post-processing for domains
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
        # Standard Search Query Logic
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
        return output or focus_topic

async def generate_contextual_comment(profile: dict, video_title: str, video_desc: str) -> str:
    persona = profile.get("persona", {})
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
        f"I am {persona.get('name', 'a user')}, a {persona.get('age', '30')}-year-old from {persona.get('city', 'a city')}. "
        f"I watched '{video_title}'. Context: '{safe_desc}'. "
        f"VIBE: {random.choice(vibes)}. FORMATTING: {random.choice(formats)}. Keep under 15 words."
    )

    output = await _safe_generate(system_prompt, user_prompt, 35, 0.85)
    
    if output:
        log.info(f"    🧠 LLM generated comment: '{output}'")
        return output
    else:
        fallbacks = ["this is actually crazy tbh", "saving this for later", "i needed this today lol", "wait is this actually real?"]
        return random.choice(fallbacks)