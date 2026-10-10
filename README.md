# Anime Telegram Bot

Modular Aiogram 3 starter with anime search → episode list → available quality buttons → video delivery.

**Source adapter note:** This repository does not include an extractor for copying or redistributing copyrighted episodes from AnimeAlpha. It includes demo metadata and a JSON catalog adapter for media you own or are authorized to distribute. Plug an authorized source into `scrapers/`.

## Setup

```bash
git clone YOUR_PRIVATE_REPO_URL
cd anime-telegram-bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env
python bot.py
```

Fill `.env` with a bot token, API ID/hash, and MongoDB URI. The API hash shared in chat should be regenerated before production use. Run MongoDB and keep its credentials private. For initial UI testing use `CATALOG_SOURCE=demo`.

## Local Bot API server

```bash
docker run -d \
  --name telegram-bot-api \
  -p 127.0.0.1:8081:8081 \
  -e TELEGRAM_API_ID="$TELEGRAM_API_ID" \
  -e TELEGRAM_API_HASH="$TELEGRAM_API_HASH" \
  -e TELEGRAM_LOCAL=1 \
  -v telegram-bot-api-data:/var/lib/telegram-bot-api \
  --restart unless-stopped \
  aiogram/telegram-bot-api:latest
```

Export the two shell variables before running Docker. The bot uses `TELEGRAM_API_BASE=http://127.0.0.1:8081` and `TELEGRAM_LOCAL_API=true`. Do not expose port 8081 publicly. A local Bot API server increases upload limits (up to 2 GB in local mode under supported conditions) but does not remove every Telegram, bandwidth, timeout, or disk-space limitation.

## Authorized JSON source

Set `CATALOG_SOURCE=authorized_json` and `AUTHORIZED_CATALOG_JSON=./data/catalog.json`. Example:

```json
{
  "anime": [{
    "id": "sample",
    "title": "Sample Anime",
    "episodes": [{
      "id": "ep1",
      "number": 1,
      "title": "Episode 1",
      "qualities": {
        "360p": "https://your-authorized-host.example/ep1-360.mp4",
        "720p": "https://your-authorized-host.example/ep1-720.mp4"
      }
    }]
  }]
}
```

Only available qualities appear. Example URLs are placeholders, not working media links.

## Structure

- `bot.py`: startup and lifecycle
- `config.py`: settings
- `handlers/`: commands and callback navigation
- `keyboards/`: inline keyboards
- `scrapers/`: source abstraction, demo and authorized JSON catalog
- `services/`: downloader and errors
- `database/`: MongoDB connection and cache repository
- `middlewares/`: simple rate limiting
- `tests/`: smoke tests

For production, add monitoring, backups, stronger rate limiting, cache invalidation, and storage cleanup.
