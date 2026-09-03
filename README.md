# Telegram Demo Bot — 30 Second Auto Delete

This package is intended for authorized/demo APIs only.

## Files

- `bot.py` — Telegram bot
- `requirements.txt` — dependencies
- `README.md` — setup instructions

## Railway / Render environment variables

Set:

`BOT_TOKEN=YOUR_NEW_BOT_TOKEN`

`API_URL=https://example.com/api/demo?value=`

Do NOT put a bot token directly in `bot.py`.

## Features

- `/start`
- `/lookup`
- JSON response formatting
- Large JSON is split into Telegram-safe chunks
- Every result chunk is deleted after 30 seconds
- HTTP timeout and API error handling
- One successful lookup per Telegram user while the process is running

## Important limitation

`used_users` is stored in RAM. Railway/Render restarts clear it.

For a permanent one-use restriction, use a database such as PostgreSQL.

Use only data and APIs you are authorized to access. Do not use the bot to retrieve or expose private personal information.
