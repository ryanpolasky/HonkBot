# Created by Ryan Polasky 10/6/25
# HonkBot | All Rights Reserved

import os
import re
import requests
import json
from pathlib import Path
from dotenv import load_dotenv
import asyncio
from concurrent.futures import ThreadPoolExecutor

load_dotenv()

OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
FREESOUND_API_KEY = os.getenv('FREESOUND_API_KEY')

SOUNDS_DIR = Path("sounds")
SOUNDS_DIR.mkdir(exist_ok=True)

executor = ThreadPoolExecutor(max_workers=3)


def query_llm_for_sound(emoji: str, emoji_name: str = None) -> dict:
    """ask the llm what sound fits this emoji"""
    if not OPENROUTER_API_KEY:
        print("Warning: OPENROUTER_API_KEY not set")
        return None

    prompt = f"""You are an expert Foley sound designer that picks perfect sound effects for emojis.

Emoji: {emoji}
{f"Unicode name: {emoji_name}" if emoji_name else ""}

Task:
Return the most *searchable and realistic* Freesound search query for this emoji.

Guidelines:
- Use short, literal, emotionally grounded sound terms (2–4 words max)
- Must be a sound an SFX library would have—avoid conceptual descriptions
- Think of real-world sound sources the emoji evokes
- Prefer familiar, instantly recognizable audio textures
- Avoid adjectives like “funny,” “cool,” or “interesting”
- Prefer nouns and verbs representing sound-emitting actions
- Do NOT use a record scratch sound effect unless it's perfectly matching

Examples:
🐶 → dog bark
😂 → laughter
🔥 → fire crackling
🔔 → bell ringing
👏 → clapping
💬 → notification pop
🧠 → electric spark
🤔 → hmm thinking sound
💀 → skull rattle
🍞 → bread crunch

Return only valid JSON:

{{
  "sound_query": "short search phrase",
  "description": "brief explanation of why this sound fits"
}}

No markdown, no commentary, just JSON."""

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "deepseek/deepseek-chat-v3.1:free",
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 200
            },
            timeout=10
        )

        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content'].strip()

            if content.startswith('```'):
                content = content.split('```')[1]
                if content.startswith('json'):
                    content = content[4:]

            return json.loads(content.strip())
        else:
            print(f"LLM API error: {response.status_code} - {response.text}")
            return None

    except Exception as e:
        print(f"Error querying LLM: {e}")
        return None


def search_freesound(query: str, duration_max: float = 3.0) -> list:
    """search freesound for sound effects"""
    if not FREESOUND_API_KEY:
        print("Warning: FREESOUND_API_KEY not set")
        return []

    try:
        response = requests.get(
            "https://freesound.org/apiv2/search/text/",
            params={
                "query": query,
                "filter": f"duration:[0 TO {duration_max}] is_remix:false",
                "sort": "rating_desc",
                "fields": "id,name,duration,url,previews,download",
                "page_size": 5
            },
            headers={
                "Authorization": f"Token {FREESOUND_API_KEY}"
            },
            timeout=10
        )

        if response.status_code == 200:
            results = response.json().get('results', [])
            return results
        else:
            print(f"Freesound API error: {response.status_code}")
            return []

    except Exception as e:
        print(f"Error searching Freesound: {e}")
        return []


def download_sound(sound_id: int, output_filename: str) -> bool:
    """grab a sound file from freesound given an id"""
    if not FREESOUND_API_KEY:
        return False

    try:
        response = requests.get(
            f"https://freesound.org/apiv2/sounds/{sound_id}/",
            headers={
                "Authorization": f"Token {FREESOUND_API_KEY}"
            },
            timeout=10
        )

        if response.status_code != 200:
            print(f"Failed to get sound info: {response.status_code}")
            return False

        sound_info = response.json()

        preview_url = sound_info.get('previews', {}).get('preview-hq-mp3')

        if not preview_url:
            preview_url = sound_info.get('previews', {}).get('preview-lq-mp3')

        if not preview_url:
            print("No preview URL available")
            return False

        audio_response = requests.get(preview_url, timeout=30)

        if audio_response.status_code == 200:
            output_path = SOUNDS_DIR / output_filename
            with open(output_path, 'wb') as f:
                f.write(audio_response.content)
            print(f"✅ Downloaded: {output_filename}")
            return True
        else:
            print(f"Failed to download audio: {audio_response.status_code}")
            return False

    except Exception as e:
        print(f"Error downloading sound: {e}")
        return False


def _sync_find_and_download_sound(emoji: str, emoji_name: str = None) -> str:
    """sync version that handles finding + downloading"""
    print(f"\n🔍 Finding sound for emoji: {emoji}")

    llm_result = query_llm_for_sound(emoji, emoji_name)

    if not llm_result:
        print("❌ LLM query failed")
        return None

    sound_query = llm_result.get('sound_query', '')
    description = llm_result.get('description', '')

    print(f"🤖 LLM suggests: '{sound_query}' - {description}")

    results = search_freesound(sound_query)

    retries = 0
    while not results and retries < 2:
        retries += 1
        print(f"⚠️  No sounds found for '{sound_query}'. Retrying with a simpler query (attempt {retries})...")
        simpler_prompt = f"""Simplify this Freesound search query to something shorter and common.
Current query: "{sound_query}"
Respond only with a simpler 1–3 word phrase for sound search.
Example: "angry cartoon face" → "angry voice", "fireworks celebration" → "fireworks explosion"
Return ONLY a JSON object: {{"sound_query": "simpler phrase"}}"""
        try:
            simple_resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "deepseek/deepseek-chat-v3.1:free",
                    "messages": [
                        {"role": "user", "content": simpler_prompt}
                    ],
                    "temperature": 0.3,
                    "max_tokens": 100
                },
                timeout=10
            )
            if simple_resp.status_code == 200:
                content = simple_resp.json()["choices"][0]["message"]["content"].strip()
                if content.startswith("```"):
                    content = content.split("```")[1]
                    if content.startswith("json"):
                        content = content[4:]
                new_query_data = json.loads(content.strip())
                new_query = new_query_data.get("sound_query")
                if new_query and new_query != sound_query:
                    print(f"🔁 Retrying with simplified query: '{new_query}'")
                    sound_query = new_query
                    results = search_freesound(sound_query)
                else:
                    break
            else:
                print(f"Simplify LLM API error: {simple_resp.status_code}")
                break
        except Exception as e:
            print(f"Error simplifying query: {e}")
            break

    if not results:
        print("❌ No sounds found on Freesound after retries")
        return None

    print(f"📦 Found {len(results)} sound(s)")

    best_sound = results[0]
    sound_id = best_sound['id']

    if emoji_name:
        safe_name = emoji_name.lower().replace(' ', '_').replace('-', '_')
        safe_name = re.sub(r'[^a-zA-Z0-9_]+', '', safe_name)
        # trim out user-provided text that got appended (if any)
        if "|" in safe_name:
            safe_name = safe_name.split("|")[0].strip("_")
    else:
        codepoint = '-'.join(f'{ord(c):04x}' for c in emoji)
        safe_name = f"emoji_{codepoint}"

    output_filename = f"{safe_name}.mp3"

    output_path = SOUNDS_DIR / output_filename
    if output_path.exists():
        print(f"ℹ️  Sound already exists: {output_filename}")
        return f"sounds/{output_filename}"

    # Download
    success = download_sound(sound_id, output_filename)

    if success:
        return f"sounds/{output_filename}"
    else:
        return None


async def find_and_download_sound_for_emoji(emoji: str, emoji_name: str = None) -> str:
    """async wrapper so event loop doesn’t freeze while downloading"""
    loop = asyncio.get_event_loop()

    try:
        result = await loop.run_in_executor(
            executor,
            _sync_find_and_download_sound,
            emoji,
            emoji_name
        )
        return result
    except Exception as e:
        print(f"Error in async sound discovery: {e}")
        return None
