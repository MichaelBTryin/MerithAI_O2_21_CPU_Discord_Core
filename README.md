# Merith AI Discord Voice Bot
## CPU-Optimized for Surface Pro 5 (and other low-end hardware)

A lightweight Discord bot that uses voice chat in real-time. Runs entirely on CPU with no GPU required.

**Hardware**: Surface Pro 5 (7th gen Intel, 8GB RAM)
**OS**: Windows 10/11
**Python**: 3.9+
**Required**: FFmpeg (for Discord voice audio playback)

---

## Quick Start (2 Steps)

### 1. Installation

Double-click `install.bat` and follow the prompts:

It will:
- Check for Python
- Ask for your Discord bot token
- Create a virtual environment
- Install all dependencies

### 2. Running the Bot

Make sure **LM Studio is running** with your model loaded, then double-click `run.bat`

The bot comes online in Discord. Done!

---

## Voice Chat Commands

### Join Voice Channel
```
/join_mai
```
Makes the bot join your current voice channel.

### Leave Voice Channel
```
/leave_mai
```
Makes the bot leave the voice channel.

### Help
```
/help
```
Lists all available commands.

---

## How It Works

When you speak in a voice channel:

```
1. Recording (5 sec)    → sounddevice captures from microphone
2. STT                  → Whisper Tiny transcribes what you said
3. LLM                  → Gemma-3-1B generates response (on LM Studio)
4. TTS                  → Piper synthesizes response to speech
5. Playback             → Bot plays audio in voice channel

Total latency: 2-5 seconds on Surface Pro 5
```

---

## LM Studio Setup

The bot uses **LM Studio** for AI responses.

### Local Setup (on Surface Pro 5)
1. Download LM Studio from https://lmstudio.ai
2. Load model: `mlabonne/gemma-3-1b-it-abliterated-GGUF (Q4_K_M)`
3. Start LM Studio and leave it running
4. Bot connects to `http://localhost:1234`

### Remote Setup (Faster - Recommended)
For 10x faster inference:
1. Run LM Studio on your main PC with a GPU
2. Allow network access in LM Studio settings
3. Edit `config.json` and change `api_url`:
   ```json
   "api_url": "http://192.168.1.100:1234/v1"
   ```
4. Bot on Surface Pro 5 connects remotely

---

## Personality (Merith)

Merith's personality is defined in `system_prompt.json`:

- **Warm and conversational** - friendly baseline
- **Witty and playful** - when space allows
- **Sassy when earned** - only when appropriate
- **Voice-optimized** - no emojis, formatting, or symbols
- **Responsive to aliases** - merit, meredith, mary, maris, gareth, etc.
- **Natural and spontaneous** - every response is unique

Edit `system_prompt.json` to customize personality.

---

## Configuration Files

### `config.json`
Main bot settings:
- `api_url` - LM Studio endpoint
- `model_name` - Model to use
- `system_prompt_file` - Path to personality file

### `system_prompt.json`
Merith's personality definition:
- Identity and aliases
- Core personality traits
- Voice communication rules
- Behavior guidelines

### `.env`
Created by install.bat - contains your Discord token (KEEP SECRET!)

---

## Troubleshooting

### Bot doesn't come online
- Check Discord token in `.env`
- Verify bot permissions in Discord

### LM Studio connection failed
- Make sure LM Studio is running
- Check that model is loaded
- Verify port 1234 is accessible

### No audio in voice channel
- Piper voice models auto-download on first use
- Check Discord audio permissions

### Audio too slow
- This is normal on CPU (2-5 seconds is expected)
- For faster inference, use remote LM Studio setup
- Or run on a machine with GPU

### Microphone not recording
- Run: `pip install sounddevice` in the venv
- Check system audio input is working

### No audio output from bot
- Install FFmpeg from: https://ffmpeg.org/download.html
- On Windows: Download and add to PATH, or run:
  ```
  choco install ffmpeg
  ```
- Or: `winget install ffmpeg`

---

## Architecture

```
Discord Voice Channel
    ↓
sounddevice (system microphone)
    ↓
Whisper Tiny (STT - CPU optimized)
    ↓
LM Studio (Port 1234)
    ↓
Gemma-3-1B (Local or remote)
    ↓
Piper TTS (Voice synthesis)
    ↓
Discord Voice Playback
```

---

## Credits

- **Merith AI** - MichaelBTryin
- **Discord.py** - https://github.com/Rapptz/discord.py
- **Whisper** - OpenAI
- **Gemma** - Google
- **Piper** - Rhasspy
- **LM Studio** - Local LLM inference

---

## Discord Bot Setup

If you need a Discord bot token:

1. Go to https://discord.com/developers/applications
2. Click "New Application"
3. Go to "Bot" tab → "Add Bot"
4. Copy the TOKEN
5. Go to "OAuth2" → "URL Generator"
   - Scopes: `bot`
   - Permissions: `Connect`, `Speak`
6. Copy the generated URL and open it to invite bot to your server
7. Use the token in install.bat

---

**Happy voice chatting!** 🎤
