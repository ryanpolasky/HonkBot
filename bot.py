# Created by Ryan Polasky 10/6/25
# HonkBot | All Rights Reserved

import discord
from discord import app_commands
from discord.ext import commands
import re
import json
import os
from collections import deque
from pathlib import Path
from dotenv import load_dotenv
import subprocess
import tempfile
from sound_discovery import find_and_download_sound_for_emoji

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix="honkbot", intents=intents)

audio_queues = {}

EMOJI_CACHE_FILE = 'emoji_cache.json'
emoji_cache = {}

discovering_emojis = set()


def load_emoji_cache():
    global emoji_cache
    if os.path.exists(EMOJI_CACHE_FILE):
        with open(EMOJI_CACHE_FILE, 'r', encoding='utf-8') as f:
            emoji_cache = json.load(f)
    print(f"Loaded {len(emoji_cache)} cached emoji mappings")


def save_emoji_cache():
    with open(EMOJI_CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(emoji_cache, f, indent=2, ensure_ascii=False)


UNICODE_EMOJI_PATTERN = re.compile(
    r'[\U0001F600-\U0001F64F'  # Emoticons
    r'\U0001F300-\U0001F5FF'  # Symbols & Pictographs
    r'\U0001F680-\U0001F6FF'  # Transport & Map
    r'\U0001F700-\U0001F77F'  # Alchemical
    r'\U0001F780-\U0001F7FF'  # Geometric Shapes
    r'\U0001F800-\U0001F8FF'  # Supplemental Arrows
    r'\U0001F900-\U0001F9FF'  # Supplemental Symbols
    r'\U0001FA00-\U0001FA6F'  # Chess Symbols
    r'\U0001FA70-\U0001FAFF'  # Symbols and Pictographs Extended-A
    r'\U00002702-\U000027B0'  # Dingbats
    r'\U000024C2-\U0001F251]',
    re.UNICODE
)

CUSTOM_EMOJI_PATTERN = re.compile(r'<a?:(\w+):(\d{17,20})>')


def extract_custom_emoji_name(custom_emoji_str: str) -> str:
    """grab the name out of a custom emoji"""
    match = re.match(r'<a?:(\w+):\d{17,20}>', custom_emoji_str)
    if match:
        return match.group(1)
    return None


def extract_emojis(message_content):
    """extract all emojis from a message in exact order of appearance, preserving ZWJ sequences"""
    emojis = []

    unicode_positions = [(m.start(), m.group()) for m in UNICODE_EMOJI_PATTERN.finditer(message_content)]
    custom_positions = [(m.start(), m.group()) for m in CUSTOM_EMOJI_PATTERN.finditer(message_content)]

    all_emojis = unicode_positions + custom_positions
    all_emojis.sort(key=lambda x: x[0])

    VARIATION_SELECTORS = {'\uFE0E', '\uFE0F', '\u200D'}

    combined_emojis = []
    skip_until = -1
    for i, (pos, emoji) in enumerate(all_emojis):
        if i < skip_until:
            continue
        # glue zwj-linked emoji parts into a single emoji
        combined = emoji
        j = i + 1
        while j < len(all_emojis):
            segment = message_content[pos:all_emojis[j][0]]
            if '\u200D' in segment:
                combined += segment + all_emojis[j][1]
                j += 1
            else:
                break
        skip_until = j
        # trim variation selectors
        cleaned = combined.rstrip('\uFE0E\uFE0F')
        if any(c not in VARIATION_SELECTORS for c in cleaned):
            combined_emojis.append(cleaned)

    return combined_emojis


async def discover_sound_for_emoji(emoji: str) -> str:
    """figure out a sound for a new emoji and download it"""
    # Avoid duplicate discoveries
    if emoji in discovering_emojis:
        return None

    discovering_emojis.add(emoji)

    try:
        print(f"🔍 Discovering sound for new emoji: {emoji}")

        emoji_name = None
        if emoji.startswith('<'):
            emoji_name = extract_custom_emoji_name(emoji)
            if emoji_name:
                print(f"   Custom emoji detected: '{emoji_name}'")

        # use LLM to find and download sound (now with extra async!)
        sound_path = await find_and_download_sound_for_emoji(emoji, emoji_name)

        if sound_path and os.path.exists(sound_path):
            emoji_cache[emoji] = sound_path
            save_emoji_cache()
            print(f"✅ Cached new sound: {emoji} -> {sound_path}")
            return sound_path
        else:
            print(f"❌ Failed to discover sound for: {emoji}")
            emoji_cache[emoji] = None
            save_emoji_cache()
            return None

    except Exception as e:
        print(f"Error discovering sound for {emoji}: {e}")
        return None
    finally:
        discovering_emojis.discard(emoji)


def get_sound_for_emoji(emoji):
    """check cache or mark for discovery"""
    if emoji in emoji_cache:
        cached_path = emoji_cache[emoji]
        # Verify file still exists
        if cached_path and os.path.exists(cached_path):
            return cached_path
        elif cached_path is None:
            return None

    return None


async def play_next_sound(guild_id):
    """play next thing in the queue, mixes overlapping sounds"""
    if guild_id not in audio_queues or not audio_queues[guild_id]:
        return

    voice_client = discord.utils.get(bot.voice_clients, guild__id=guild_id)

    if not voice_client or not voice_client.is_connected():
        audio_queues[guild_id].clear()
        return

    if voice_client.is_playing():
        return

    # pull a few sound files to mix
    sounds_to_mix = []
    max_sounds = min(10, len(audio_queues[guild_id]))

    for _ in range(max_sounds):
        if audio_queues[guild_id]:
            sound_path = audio_queues[guild_id].popleft()
            if os.path.exists(sound_path):
                sounds_to_mix.append(sound_path)

    if not sounds_to_mix:
        return

    # if it’s just one sound just play it raw
    if len(sounds_to_mix) == 1:
        audio_source = discord.FFmpegPCMAudio(
            sounds_to_mix[0],
            options='-vn -filter:a "volume=0.5"'
        )

        def after_playing(error):
            if error:
                print(f"Error playing audio: {error}")
            bot.loop.create_task(play_next_sound(guild_id))

        voice_client.play(audio_source, after=after_playing)
        return

    def get_duration(sound_path):
        try:
            result = subprocess.run(
                ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                 '-of', 'default=noprint_wrappers=1:nokey=1', sound_path],
                capture_output=True,
                text=True,
                timeout=5
            )
            return float(result.stdout.strip())
        except:
            return 1.0

    durations = [get_duration(sound) for sound in sounds_to_mix]

    # little overlap between clips
    OVERLAP_PERCENTAGE = 0.20

    # calculate delays for each bit
    delays = [0.0]
    cumulative_time = 0.0

    for i in range(len(durations) - 1):
        overlap_duration = durations[i] * OVERLAP_PERCENTAGE
        cumulative_time += durations[i] - overlap_duration
        delays.append(cumulative_time)

    # build ffmpeg command filters for overlap
    filter_parts = []

    for i, (sound, delay) in enumerate(zip(sounds_to_mix, delays)):
        delay_ms = int(delay * 1000)
        if delay_ms > 0:
            filter_parts.append(f"[{i}:a]adelay={delay_ms}|{delay_ms},volume=0.5[a{i}]")
        else:
            filter_parts.append(f"[{i}:a]volume=0.5[a{i}]")

    # mix delayed audio tracks together
    mix_inputs = ''.join(f"[a{i}]" for i in range(len(sounds_to_mix)))
    filter_complex = ';'.join(
        filter_parts) + f";{mix_inputs}amix=inputs={len(sounds_to_mix)}:duration=longest:dropout_transition=0[out]"

    # temp output spot
    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
        tmp_path = tmp.name

    try:
        # build the ffmpeg run
        cmd = ['ffmpeg', '-y']
        for sound in sounds_to_mix:
            cmd.extend(['-i', sound])
        cmd.extend([
            '-filter_complex', filter_complex,
            '-map', '[out]',
            '-ar', '48000',
            '-ac', '2',
            tmp_path
        ])

        result = subprocess.run(cmd, capture_output=True, timeout=30)

        if result.returncode != 0:
            print(f"FFmpeg error: {result.stderr.decode()}")
            os.remove(tmp_path)
            await play_next_sound(guild_id)
            return

    except Exception as e:
        print(f"Error mixing audio: {e}")
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        await play_next_sound(guild_id)
        return

    # play the finished audio clip
    audio_source = discord.FFmpegPCMAudio(tmp_path, options='-vn')

    def after_playing(error):
        try:
            os.remove(tmp_path)
        except:
            pass

        if error:
            print(f"Error playing audio: {error}")

        bot.loop.create_task(play_next_sound(guild_id))

    voice_client.play(audio_source, after=after_playing)


@bot.event
async def on_ready():
    """when bot first connects"""
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is in {len(bot.guilds)} guilds')

    load_emoji_cache()

    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")


@bot.event
async def on_message(message):
    """watch messages and add sounds to queue"""
    if message.author.bot:
        return

    emojis = extract_emojis(message.content)

    if not emojis:
        return

    if not message.author.voice or not message.author.voice.channel:
        return

    user_voice_channel = message.author.voice.channel
    guild_id = message.guild.id

    voice_client = discord.utils.get(bot.voice_clients, guild=message.guild)

    if not voice_client or not voice_client.is_connected():
        return

    if voice_client.channel != user_voice_channel:
        return

    if guild_id not in audio_queues:
        audio_queues[guild_id] = deque()

    sounds_added = 0
    unknown_emojis = []

    for emoji in emojis:
        sound_path = get_sound_for_emoji(emoji)
        if sound_path:
            audio_queues[guild_id].append(sound_path)
            sounds_added += 1
        elif emoji not in discovering_emojis and emoji not in emoji_cache:
            # brand new emoji, gotta handle it
            unknown_emojis.append(emoji)

            if emoji.startswith('<'):
                name = extract_custom_emoji_name(emoji)
                if name:
                    print(f"📝 New custom emoji detected: {name} ({emoji})")

    if unknown_emojis:
        discovered_paths = []

        for emoji in unknown_emojis:
            path = await discover_sound_for_emoji(emoji)
            if path:
                discovered_paths.append(path)

        for path in discovered_paths:
            if path and os.path.exists(path):
                audio_queues[guild_id].append(path)
                sounds_added += 1

    # now actually play them all
    if sounds_added > 0 and not voice_client.is_playing():
        await play_next_sound(guild_id)


@bot.tree.command(name="join", description="Make the bot join your voice channel")
async def join(interaction: discord.Interaction):
    """bot hops into user vc"""
    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.response.send_message(
            "❌ bruh you're not even in a call!",
            ephemeral=True
        )
        return

    user_voice_channel = interaction.user.voice.channel
    voice_client = discord.utils.get(bot.voice_clients, guild=interaction.guild)

    if voice_client and voice_client.is_connected():
        if voice_client.channel == user_voice_channel:
            await interaction.response.send_message(
                "✅ i'm already in your call?",
                ephemeral=True
            )
            return
        else:
            try:
                await voice_client.move_to(user_voice_channel)
                await interaction.response.send_message(
                    f"🔊 On My Way! to {user_voice_channel.name}!",
                    ephemeral=True
                )
            except Exception as e:
                await interaction.response.send_message(
                    f"❌ bruh: {e}",
                    ephemeral=True
                )
    else:
        try:
            await user_voice_channel.connect()
            await interaction.response.send_message(
                f"🔊 in {user_voice_channel.name} now fr fr",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ bruh: {e}",
                ephemeral=True
            )


@bot.tree.command(name="leave", description="Make the bot leave the voice channel")
async def leave(interaction: discord.Interaction):
    """bot leaves vc"""
    voice_client = discord.utils.get(bot.voice_clients, guild=interaction.guild)

    if voice_client and voice_client.is_connected():
        if interaction.guild.id in audio_queues:
            audio_queues[interaction.guild.id].clear()

        await voice_client.disconnect()
        await interaction.response.send_message("👋 adieu", ephemeral=True)
    else:
        await interaction.response.send_message("i'm not even in the call?", ephemeral=True)


@bot.tree.command(name="skip", description="Skip all sounds and clear the queue")
async def skip(interaction: discord.Interaction):
    """stop everything and empty the queue"""
    voice_client = discord.utils.get(bot.voice_clients, guild=interaction.guild)
    guild_id = interaction.guild.id

    if guild_id in audio_queues:
        queue_size = len(audio_queues[guild_id])
        audio_queues[guild_id].clear()
    else:
        queue_size = 0

    if voice_client and voice_client.is_playing():
        voice_client.stop()
        await interaction.response.send_message(
            f"⏭️ thank god, {queue_size} sound(s) cleared from queue.",
            ephemeral=True
        )
    else:
        if queue_size > 0:
            await interaction.response.send_message(
                f"🗑️ removed {queue_size} awful sound(s) from queue.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "there's nothing playing rn?",
                ephemeral=True
            )


@bot.tree.command(name="sounds", description="Show all available emoji sounds")
async def sounds(interaction: discord.Interaction):
    """show what emojis have sounds"""
    total_sounds = len([v for v in emoji_cache.values() if v is not None])

    embed = discord.Embed(
        title="🔊 Available Emoji Sounds",
        description=f"Using /join first, then type messages with emojis to play sounds!\n\n**{total_sounds}** sounds available (and growing!)",
        color=discord.Color.blue()
    )

    if emoji_cache:
        cached_emojis = [k for k, v in emoji_cache.items() if v is not None][:20]
        if cached_emojis:
            cached_list = " ".join(cached_emojis)
            embed.add_field(name="Discovered Emojis (sample)", value=cached_list, inline=False)

    embed.add_field(
        name="How to use",
        value="1. Use `/join` to add me to your voice channel\n2. Type messages with emojis\n3. New emojis are automatically discovered and downloaded!\n4. Sounds are cached for instant replay",
        inline=False
    )

    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="queue", description="Show current sound queue")
async def queue(interaction: discord.Interaction):
    """show what’s waiting to play"""
    guild_id = interaction.guild.id

    if guild_id not in audio_queues or not audio_queues[guild_id]:
        await interaction.response.send_message("Queue is empty!", ephemeral=True)
        return

    queue_size = len(audio_queues[guild_id])
    await interaction.response.send_message(
        f"🎵 **{queue_size}** sound(s) in queue",
        ephemeral=True
    )


@bot.tree.command(name="discover", description="Manually trigger sound discovery for an emoji")
async def discover(interaction: discord.Interaction, emoji: str):
    """manually grab a sound for some emoji"""
    await interaction.response.defer(ephemeral=True)

    emojis = extract_emojis(emoji)

    if not emojis:
        await interaction.followup.send("❌ No valid emoji found!", ephemeral=True)
        return

    target_emoji = emojis[0]

    if target_emoji in emoji_cache and emoji_cache[target_emoji]:
        existing_path = emoji_cache[target_emoji]

        display_name = ""
        if target_emoji.startswith('<'):
            name = extract_custom_emoji_name(target_emoji)
            if name:
                display_name = f" ({name})"

        await interaction.followup.send(
            f"✅ sound already exists for {target_emoji}{display_name}\nPath: `{existing_path}`",
            ephemeral=True
        )
        return

    sound_path = await discover_sound_for_emoji(target_emoji)

    display_name = ""
    if target_emoji.startswith('<'):
        name = extract_custom_emoji_name(target_emoji)
        if name:
            display_name = f" ({name})"

    if sound_path:
        await interaction.followup.send(
            f"✅ discovered and downloaded sound for {target_emoji}{display_name}!\nPath: `{sound_path}`",
            ephemeral=True
        )
    else:
        await interaction.followup.send(
            f"❌ failed to discover sound for {target_emoji}{display_name}",
            ephemeral=True
        )


@bot.tree.command(name="redo", description="Redo LLM sound discovery for an emoji if the current sound is bad")
async def redo(interaction: discord.Interaction, emoji: str):
    """redo discovery on a bad pick"""
    await interaction.response.defer(ephemeral=True)

    emojis = extract_emojis(emoji)
    if not emojis:
        await interaction.followup.send("❌ No valid emoji found!", ephemeral=True)
        return

    target_emoji = emojis[0]

    if target_emoji in emoji_cache:
        old_path = emoji_cache.get(target_emoji)
        if old_path and os.path.exists(old_path):
            try:
                os.remove(old_path)
                await interaction.followup.send(f"🗑️ Removed old sound file for {target_emoji}", ephemeral=True)
            except Exception as e:
                await interaction.followup.send(f"⚠️ Could not delete old file ({e})", ephemeral=True)
        emoji_cache.pop(target_emoji, None)
        save_emoji_cache()

    # tell LLM that previous choice was bad
    print(f"🔁 Redoing sound discovery for {target_emoji} due to poor fit")

    emoji_name = None
    if target_emoji.startswith('<'):
        emoji_name = extract_custom_emoji_name(target_emoji)

    new_path = await find_and_download_sound_for_emoji(
        emoji=target_emoji,
        emoji_name=emoji_name
    )

    if new_path and os.path.exists(new_path):
        emoji_cache[target_emoji] = new_path
        save_emoji_cache()
        await interaction.followup.send(f"✅ Redid and downloaded new sound for {target_emoji}\nPath: `{new_path}`", ephemeral=True)
    else:
        await interaction.followup.send(f"❌ Redo failed for {target_emoji}", ephemeral=True)


@bot.tree.command(name="adminclear", description="🧨 DANGEROUS: Deletes all sounds and clears emoji cache")
async def adminclear(interaction: discord.Interaction, confirm: str):
    """wipe out every sound + clear emoji_cache if confirm == please"""
    await interaction.response.defer(ephemeral=True)

    if confirm.lower().strip() != "please":
        await interaction.followup.send("❌ Nice try. You must pass 'please' to confirm.", ephemeral=True)
        return

    deleted = 0
    sounds_dir = Path("sounds")

    if sounds_dir.exists():
        for sound_file in sounds_dir.glob("*.mp3"):
            try:
                sound_file.unlink()
                deleted += 1
            except Exception as e:
                print(f"Failed to delete {sound_file}: {e}")

    emoji_cache.clear()
    save_emoji_cache()

    await interaction.followup.send(f"💣 Nuked {deleted} sound(s) and cleared emoji cache. It's all gone now.", ephemeral=True)


if __name__ == "__main__":
    Path("sounds").mkdir(exist_ok=True)

    TOKEN = os.getenv('DISCORD_BOT_TOKEN')

    if not TOKEN:
        print("Error: DISCORD_BOT_TOKEN environment variable not set!")
        print("Create a .env file with: DISCORD_BOT_TOKEN=your_token_here")
        exit(1)

    bot.run(TOKEN)
