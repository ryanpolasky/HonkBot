# 🦆 HonkBot

**HonkBot** is a fun and chaotic Discord bot that plays sound effects when users send emoji messages in voice channels.  
It automatically discovers sound effects for new emojis using an AI model and the Freesound.org API.

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

### 3. Add your environment variables  
Create a `.env` file in the project root:
```env
DISCORD_BOT_TOKEN=your_discord_bot_token_here
OPENROUTER_API_KEY=your_openrouter_key_here
FREESOUND_API_KEY=your_freesound_api_key_here
```

### 4. Run the bot  
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

1. When a user sends a message with emojis while in a voice channel:
   - HonkBot detects all emojis (including custom and Zero Width Joiner combos like 👨‍👩‍👧‍👦).
   - For unknown emojis, it asks the **LLM** what that emoji should sound like.
   - The bot then searches **Freesound.org** for a matching sound effect.
   - The sound is downloaded, cached, and played back in the Discord VC.

2. The next time that emoji appears, the bot reuses the cached sound instantly.

---

## 🧩 File Structure

```
.
├── bot.py                # Main bot logic and Discord events
├── sound_discovery.py    # LLM + Freesound AI sound discovery
├── sounds/               # Downloaded and cached MP3 files
├── emoji_cache.json      # Cached emoji → sound mapping
└── .env                  # API and bot tokens
```

---

## 🧠 Notes

- Uses the free **OpenRouter** DeepSeek model for interpreting emoji sound meanings.
- Uses **Freesound API** to find short, realistic, reusable sounds (<3 seconds default).
- Can combine multiple emoji-triggered sounds dynamically with **FFmpeg**.

---

## ⚠️ Admin Warnings

- `/adminclear` will *permanently delete all saved sounds* and reset the cache.
- Yes, it’s intentionally locked behind `/adminclear please`. Yes, this is terrible practice & has no real user access control. I know.
- Don’t expose your `.env` file — it contains your bot and API keys.

---

## 🦆 License

Created by **Ryan Polasky**, 2025  
All Rights Reserved.
