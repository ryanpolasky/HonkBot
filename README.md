# 🦆 HonkBot

**HonkBot** is your unhinged little friend that can *actually* make your emojis scream, laugh, bark, and explode right in your voice calls.  
It finds, downloads, and plays sound effects for every emoji you throw its way using an AI model and Freesound.org. It’s part chaos, part genius, 100% loud.

---

## 🚀 Features

- 🔊 **Emoji-triggered sounds** — whenever someone sends an emoji, the corresponding sound plays in the call.
- 🧠 **AI-powered sound discovery** — automatically figures out what sound best matches an emoji using an LLM.
- 📦 **Freesound integration** — downloads matching sounds directly from [freesound.org](https://freesound.org).
- ⚡ **Smart sound overlap** — mixes multiple sounds dynamically for a more natural, chaotic effect.
- 💾 **Emoji caching** — once a sound is found, it’s saved locally and reused instantly.
- 🧹 **Admin utilities** — redo bad LLM choices, nuke all sounds, or rediscover better fits.

---

## ⚙️ Setup

### 1. Clone the repo
```bash
git clone https://github.com/ryanpolasky/honkbot.git
cd honkbot
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Make sure FFmpeg is installed
Grab **ffmpeg.exe** and drop it next to `bot.py`.   
No FFmpeg, no sound. You can get it from: [https://ffmpeg.org/download.html](https://ffmpeg.org/download.html)

### 4. Add your environment variables  
Create a `.env` file in the project root:
```env
DISCORD_BOT_TOKEN=your_discord_bot_token_here
OPENROUTER_API_KEY=your_openrouter_key_here
FREESOUND_API_KEY=your_freesound_api_key_here
```

### 5. Run the bot  
```bash
python bot.py
```

---

## 🗣 Commands

| Command              | Description                                   |
|----------------------|-----------------------------------------------|
| `/join`              | Bot joins your current voice channel.         |
| `/leave`             | Disconnects from the voice channel.           |
| `/skip`              | Stops current playback and clears the queue.  |
| `/sounds`            | Lists all emojis with saved sounds.           |
| `/queue`             | Displays the current sound queue.             |
| `/discover <emoji>`  | Manually triggers AI discovery for an emoji.  |
| `/redo <emoji>`      | Redoes AI discovery for a bad emoji sound.    |
| `/adminclear please` | ⚠️ Deletes *all* sounds and clears the cache. |

---

## 🤖 How it works

1. When someone drops an emoji in chat while in a call:
   - HonkBot spots it like a hawk (even uncommon ones like 👨‍👩‍👧‍👦).
   - It pings an LLM like: “yo, what’s this supposed to sound like?”
   - LLM goes ✨beep boop✨ (or somethin like that, I don't know how they work /hj) and responds with something like “dog bark” or “sad trombone.”
   - The bot hunts down the sound on **Freesound.org**, downloads it, and plays it through Discord.
   - Boom. Chaos.
2. Next time? It just reuses the cached file — no AI delay, just awful noise.

---

## 🧩 File Structure

```
.
├── bot.py                # Main bot logic and Discord events
├── sound_discovery.py    # LLM + Freesound AI sound discovery
├── sounds/               # Downloaded and cached MP3 files
├── emoji_cache.json      # Cached emoji → sound mapping
├── ffmpeg.exe            # You need to download this 
└── .env                  # API and bot tokens
```

---

## 🧠 Notes

- Uses the free **OpenRouter** DeepSeek model for interpreting emoji sound meanings.
- Uses **Freesound API** to find short, realistic, reusable sounds (<3 seconds default).
- Can combine multiple emoji-triggered sounds dynamically with **FFmpeg**.

---

## ⚠️ Admin Warnings

- `/adminclear` will *nuke every single sound* and wipe your cache clean. RIP honks.
- Yes, it literally asks for “please.” That’s your *one-layer security system*.
  - Yes, there is literally no other protection for this. If you want to use this in a real server, feel free to fix this.
- Don’t ever leak `.env` — that’s your golden ticket (bot + API keys).

---

## 🦆 License

Created by **Ryan Polasky**, 2025  
All Rights Reserved.  
*(and probably semi-regretted after hearing 👀💀💥 fifty times in one call)*
