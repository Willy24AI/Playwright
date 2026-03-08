"""
llm_helper.py
-------------
Handles dynamic generation of search terms and contextual YouTube comments using OpenAI.
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
    Generates a daily, mathematically unique search query.
    Injects random intents, modifiers, and time-context to prevent LLM convergence.
    """
    persona = profile["persona"]
    
    # 1. Pick just ONE topic to focus on today, rather than listing all of them
    if not profile.get("topics"):
        return "interesting videos"
        
    focus_topic = random.choice(profile["topics"])
    
    # 2. Inject a random human "Intent" or "Situation"
    intents = [
        "You are frustrated and trying to troubleshoot a specific problem related to",
        "You are a total beginner looking for a highly specific tutorial about",
        "You are bored and looking for entertaining, long-form content about",
        "You are looking to buy something cheap related to",
        "You want to know the absolute latest 2026 news or drama regarding",
        "You are looking for an obscure, weird fact or niche rabbit-hole about",
        "You are trying to explain a complex concept to a friend regarding"
    ]
    current_intent = random.choice(intents)
    
    # 3. Inject a random format modifier
    modifiers = ["reddit", "step by step", "for dummies", "vs", "review", "tier list", "explained", "mistakes to avoid", "speedrun"]
    use_modifier = random.random() < 0.4 # 40% chance to append a web modifier
    mod_text = f" Optionally include a keyword like '{random.choice(modifiers)}'." if use_modifier else ""

    prompt = (
        f"You are {persona['name']}, a {persona['age']}-year-old living in {persona['city']}. "
        f"{current_intent} '{focus_topic}'. "
        f"Generate exactly ONE highly specific, casual {platform} search query you would type right now. "
        f"Make it sound human, sometimes slightly poorly phrased. {mod_text} "
        "Do NOT use quotes. Do NOT explain. Just return the raw search string."
    )

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9, # Bumped up for maximum creativity
            max_tokens=20,
            presence_penalty=0.6, # Forces the model to use novel words
            frequency_penalty=0.3
        )
        query = response.choices[0].message.content.strip().strip('"')
        log.info(f"    🧠 LLM generated {platform} query: '{query}'")
        return query
    except Exception as e:
        log.warning(f"    ⚠️ LLM search generation failed: {e}")
        return focus_topic


async def generate_contextual_comment(profile: dict, video_title: str, video_desc: str) -> str:
    """
    Reads the video title and description and generates a mathematically unique, 
    human-like comment using an entropy matrix (randomized vibes and formatting).
    """
    persona = profile["persona"]
    
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
        f"You are {persona['name']}, a {persona['age']}-year-old from {persona['city']}. "
        f"You just watched a YouTube video titled '{video_title}'. "
        f"Context from description: '{safe_desc}'. "
        f"Write a YouTube comment. YOUR VIBE: {current_vibe} "
        f"YOUR FORMATTING RULE: {current_format} "
        "STRICT RULES: Keep it under 15 words. DO NOT use generic bot phrases (e.g., 'Great video!', 'Thanks for sharing!'). "
        "DO NOT use hashtags. DO NOT wrap the output in quotes. Just return the raw comment text."
    )

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.85, # High temperature for creative phrasing
            max_tokens=35,
            presence_penalty=0.4, # Penalizes reusing exact words
            frequency_penalty=0.4 # Discourages repeating structural patterns
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