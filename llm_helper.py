"""
llm_helper.py
-------------
Handles dynamic generation of search terms, document drafts, calendar events,
news domains, shopping targets, Drive folders, and contextual YouTube comments using OpenAI.
Uses an "Entropy Matrix" to ensure outputs never converge, even across thousands of profiles.
"""

import os
import logging
import random
from openai import AsyncOpenAI

log = logging.getLogger(__name__)

# Initialize the async client
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

async def generate_dynamic_search(profile: dict, platform: str) -> str:
    """
    Generates a daily, mathematically unique search query, document draft, or domain.
    Adapts seamlessly to the requested platform and persona interests.
    """
    persona = profile.get("persona", {})
    
    # 1. Pick just ONE topic to focus on today
    if not profile.get("topics"):
        focus_topic = "interesting videos"
    else:
        focus_topic = random.choice(profile["topics"])
        
    base_prompt = f"You are {persona.get('name', 'a user')}, a {persona.get('age', '30')}-year-old living in {persona.get('city', 'a city')}. Your current focus/interest is: '{focus_topic}'.\n"

    # 2. Branch logic based on the requested platform
    if platform == "Google Docs Draft":
        prompt = base_prompt + (
            "You are writing a rough draft in a new, blank Google Doc. "
            "Write a realistic, 3-to-4 sentence paragraph about your interest. "
            "It could be a journal entry, a project outline, or a quick brainstorm. "
            "Do NOT use hashtags, emojis, or search query formatting. Just write the raw, casual text without quotes."
        )
        token_limit = 120 
        temp = 0.85
        
    elif platform == "Google Calendar Event":
        prompt = base_prompt + (
            "You are scheduling a new event on your personal calendar related to your interest. "
            "Write exactly ONE short, highly realistic event title (2 to 6 words maximum). "
            "Examples: 'Zoom call about X', 'Review X budget', 'Read up on X', 'Buy X supplies'. "
            "Do NOT use quotes. Just return the raw event title."
        )
        token_limit = 15
        temp = 0.80

    elif platform == "Google News":
        prompt = base_prompt + (
            "You are looking for the latest 2026 news or developments regarding your interest. "
            "Generate exactly ONE short, specific search query you would type into the Google News search bar. "
            "Do NOT use quotes. Keep it lowercase. Just return the raw search string."
        )
        token_limit = 20
        temp = 0.90

    elif platform == "Shopping Target":
        prompt = base_prompt + (
            "Identify the #1 most trusted, major website or marketplace to buy high-end products related to this interest. "
            "Examples: 'bestbuy.com' for tech, 'etsy.com' for crafts, 'nike.com' for sports, 'autozone.com' for cars. "
            "STRICT RULES: Return ONLY the raw domain (e.g., 'amazon.com'). Do NOT include https. Do NOT explain."
        )
        token_limit = 10
        temp = 0.5

    elif platform == "Shopping Query":
        prompt = base_prompt + (
            "You want to buy a specific high-end product related to your interest. "
            "Generate exactly ONE specific commercial search query for a product you would actually buy. "
            "Examples: 'sony a7iv price comparison', 'best organic protein powder 2lb', 'rtx 5060 pc build specs'. "
            "Do NOT use quotes. Just return the raw search string."
        )
        token_limit = 20
        temp = 0.85

    elif platform == "OAuth Target":
        prompt = base_prompt + (
            "Identify a popular, high-authority website or community related to your interest that "
            "almost certainly supports the 'Sign in with Google' OAuth button. "
            "Examples: 'behance.net', 'strava.com', 'quora.com', 'medium.com', 'canva.com'. "
            "STRICT RULES: Return ONLY the raw domain (e.g., 'pinterest.com'). Do NOT include https. Do NOT explain."
        )
        token_limit = 10
        temp = 0.6

    elif platform == "Direct News Domain":
        prompt = base_prompt + (
            "You are opening your web browser to read articles directly from a publisher you like. "
            "Based strictly on your current interest, return the domain name of a popular, real-world "
            "magazine, blog, or news website dedicated to this topic. "
            "STRICT RULES: Return ONLY the raw domain. Do NOT include 'https://' or 'www.'. Do NOT explain."
        )
        token_limit = 10
        temp = 0.5
        
    elif platform == "Drive Folder":
        prompt = base_prompt + (
            "You are organizing your personal Google Drive. "
            "Generate exactly ONE highly realistic, short name for a new folder related to your interest. "
            "Examples: 'Project references', 'Tax docs 2026', 'Inspiration', 'Trip planning', 'receipts', 'random ideas'. "
            "Make it sound casual, like a real human typed it. Sometimes use lowercase. "
            "STRICT RULES: Do NOT use quotes. Return ONLY the raw folder name."
        )
        token_limit = 12
        temp = 0.85

    else:
        # Standard Search Query Logic (Google, YouTube, Maps, etc.)
        intents = [
            "You are frustrated and trying to troubleshoot a specific problem related to it.",
            "You are a total beginner looking for a highly specific tutorial about it.",
            "You are looking for entertaining, long-form content about it.",
            "You are looking to buy something cheap related to it.",
            "You want to know the absolute latest news or drama regarding it.",
            "You are looking for an obscure, weird fact or niche rabbit-hole about it.",
            "You are trying to explain a complex concept to a friend regarding it."
        ]
        current_intent = random.choice(intents)
        
        modifiers = ["reddit", "step by step", "for dummies", "vs", "review", "tier list", "explained", "mistakes to avoid", "near me"]
        use_modifier = random.random() < 0.4 # 40% chance to append a web modifier
        mod_text = f" Optionally include a keyword like '{random.choice(modifiers)}'." if use_modifier else ""

        prompt = base_prompt + (
            f"SITUATION: {current_intent} "
            f"Generate exactly ONE highly specific, casual {platform} search query you would type right now. "
            f"Make it sound human, sometimes slightly poorly phrased. {mod_text} "
            "Do NOT use quotes. Do NOT explain. Just return the raw search string."
        )
        token_limit = 20 
        temp = 0.9

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=temp, 
            max_tokens=token_limit,
            presence_penalty=0.6, 
            frequency_penalty=0.3
        )
        output = response.choices[0].message.content.strip().strip('"')
        log.info(f"    🧠 LLM generated {platform} content: '{output[:50]}...'")
        return output
    except Exception as e:
        log.warning(f"    ⚠️ LLM generation failed: {e}")
        return focus_topic

async def generate_contextual_comment(profile: dict, video_title: str, video_desc: str) -> str:
    """
    Reads the video title and description and generates a mathematically unique, 
    human-like comment using an entropy matrix (randomized vibes and formatting).
    """
    persona = profile.get("persona", {})
    
    # Truncate description to save tokens (first 500 chars is usually enough context)
    safe_desc = video_desc[:500].replace("\n", " ") if video_desc else "No description."
    
    # 1. Inject a random emotional angle / intent
    vibes = [
        "You are extremely grateful because this solved a specific problem you've been stuck on.",
        "You mildly disagree with one small point but liked the video overall.",
        "You are pointing out a random, specific detail from the description or title that amused you.",
        "You are sharing a very brief, 1-sentence personal anecdote related to the topic.",
        "You are asking a genuine, slightly confused follow-up question.",
        "You are just dropping a casual, lazy reaction (like 'real', 'big mood', or 'accurate').",
        "You are acting like an armchair expert adding a tiny bit of extra information.",
        "You are complaining about how hard this topic usually is, but glad this video exists."
    ]
    current_vibe = random.choice(vibes)
    
    # 2. Inject randomized formatting habits
    formats = [
        "Type entirely in lowercase with zero punctuation.",
        "Use completely perfect grammar and capitalization.",
        "Use casual internet grammar and add exactly one relevant emoji.",
        "Include a common internet filler acronym (tbh, ngl, lol, lmao).",
        "Make it an abrupt, fragmented sentence."
    ]
    current_format = random.choice(formats)

    prompt = (
        f"You are {persona.get('name', 'a user')}, a {persona.get('age', '30')}-year-old from {persona.get('city', 'a city')}. "
        f"You just watched a YouTube video titled '{video_title}'. "
        f"Context from description: '{safe_desc}'. "
        f"Write a YouTube comment. YOUR VIBE: {current_vibe} "
        f"YOUR FORMATTING RULE: {current_format} "
        "STRICT RULES: Keep it under 15 words. DO NOT use generic bot phrases (e.g., 'Great video!', 'Thanks for sharing!'). "
        "DO NOT use AI buzzwords (e.g., 'delve', 'moreover', 'testament', 'realm', 'crucial'). "
        "DO NOT use hashtags. DO NOT wrap the output in quotes. Just return the raw comment text."
    )

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.85, 
            max_tokens=35,
            presence_penalty=0.4, 
            frequency_penalty=0.4 
        )
        comment = response.choices[0].message.content.strip().strip('"')
        log.info(f"    🧠 LLM generated comment: '{comment}'")
        return comment
    except Exception as e:
        log.warning(f"    ⚠️ LLM comment generation failed: {e}")
        # Fallbacks in case the API times out
        fallbacks = [
            "this is actually crazy tbh", 
            "saving this for later", 
            "i needed this today lol", 
            "wait is this actually real?"
        ]
        return random.choice(fallbacks)