# Telegram Demo Bot - Clean 30s Output

For authorized/demo APIs only.

The bot removes these top-level API metadata fields before display:
- number
- total
- powered_by
- api_info

It displays the remaining response as readable text rather than raw JSON.
Result messages are automatically deleted after 30 seconds.

Environment variables:
BOT_TOKEN=YOUR_NEW_BOT_TOKEN
API_URL=https://example.com/api/demo?value=

The one-use user limit is in memory and resets after a Railway/Render restart.
Use a database for a persistent limit.

Do not use this bot to expose private personal information.
