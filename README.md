# Telegram Demo Bot

## Render Environment Variables

Set these in Render:
- BOT_TOKEN = your NEW Telegram bot token
- API_URL = your authorized/demo API endpoint including the parameter prefix

Example:
API_URL=https://example.com/api/demo?value=

## Commands
/start
/lookup

The successful result message is deleted after 10 seconds.

IMPORTANT:
The one-use restriction is stored in memory and resets when the Render
worker restarts/redeploys. Use a database such as PostgreSQL if you need
a persistent one-use limit.

Use this only with an API and data you are authorized to access.
