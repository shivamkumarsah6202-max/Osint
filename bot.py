import os
import json
import asyncio
import logging
import aiohttp

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# Set these in Railway/Render environment variables.
BOT_TOKEN = os.environ["BOT_TOKEN"]
API_URL = os.environ["API_URL"]

DELETE_AFTER_SECONDS = 30
MAX_TELEGRAM_MESSAGE = 4000

# In-memory one-use limit. This resets after a service restart/redeploy.
used_users = set()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def split_text(text: str, limit: int = MAX_TELEGRAM_MESSAGE):
    """Split a large string into Telegram-safe chunks."""
    return [text[i:i + limit] for i in range(0, len(text), limit)] or ["{}"]


def pretty_json(data):
    return json.dumps(data, indent=2, ensure_ascii=False)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["waiting_for_input"] = False
    await update.message.reply_text(
        "👋 Welcome!\n\n"
        "Demo num lookup ke liye /lookup use karein.\n"
        "Successful lookup ke baad result 30 seconds mein delete ho jayega.\n"
        "Har user ko 1 successful lookup allowed hai. (Api expire:-04-09-26) "
    )


async def lookup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id in used_users:
        await update.message.reply_text(
            "❌ Aap apna allowed lookup already use kar chuke hain."
        )
        return

    context.user_data["waiting_for_input"] = True
    await update.message.reply_text("🔎 Demo input bhejiye:")


async def delete_later(chat_id, message_id, delay):
    await asyncio.sleep(delay)
    try:
        await context_bot_delete(chat_id, message_id)
    except Exception as exc:
        logger.warning("Could not delete message %s: %s", message_id, exc)


# Telegram Bot API access is supplied through this lightweight helper.
_bot_app = None


async def context_bot_delete(chat_id, message_id):
    if _bot_app is None:
        return
    await _bot_app.bot.delete_message(chat_id=chat_id, message_id=message_id)


async def send_json_result(update: Update, data):
    text = pretty_json(data)
    chunks = split_text(text)

    sent_messages = []
    for index, chunk in enumerate(chunks):
        prefix = f"JSON ({index + 1}/{len(chunks)})\n" if len(chunks) > 1 else ""
        # Plain text avoids MarkdownV2 escaping failures with arbitrary JSON.
        msg = await update.message.reply_text(
            prefix + chunk,
            disable_web_page_preview=True,
        )
        sent_messages.append(msg)

    # Delete every result chunk after 30 seconds.
    for msg in sent_messages:
        asyncio.create_task(
            delete_later(
                msg.chat_id,
                msg.message_id,
                DELETE_AFTER_SECONDS,
            )
        )


async def handle_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not context.user_data.get("waiting_for_input"):
        return

    if user_id in used_users:
        context.user_data["waiting_for_input"] = False
        await update.message.reply_text(
            "❌ Aapka allowed lookup already use ho chuka hai."
        )
        return

    value = update.message.text.strip()

    if not value or len(value) > 200:
        await update.message.reply_text("❌ Invalid demo input.")
        return

    context.user_data["waiting_for_input"] = False

    try:
        # API_URL must point to an authorized/demo endpoint and already
        # contain the parameter prefix, e.g. ...?value=
        url = f"{API_URL}{value}"

        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                if response.status != 200:
                    await update.message.reply_text(
                        f"❌ API error: HTTP {response.status}"
                    )
                    return

                try:
                    result = await response.json(content_type=None)
                except Exception:
                    raw = await response.text()
                    await update.message.reply_text(
                        "❌ API ne valid JSON return nahi kiya."
                    )
                    logger.warning("Non-JSON API response: %s", raw[:500])
                    return

        # Only successful responses consume the one-use allowance.
        if isinstance(result, dict) and result.get("success") is True:
            used_users.add(user_id)

        await send_json_result(update, result)

    except asyncio.TimeoutError:
        await update.message.reply_text("❌ API request timeout.")
    except aiohttp.ClientError as exc:
        logger.exception("HTTP error: %s", exc)
        await update.message.reply_text("❌ API connection error.")
    except Exception as exc:
        logger.exception("Unexpected error: %s", exc)
        await update.message.reply_text("❌ Data fetch nahi ho saka.")


def main():
    global _bot_app

    _bot_app = Application.builder().token(BOT_TOKEN).build()

    _bot_app.add_handler(CommandHandler("start", start))
    _bot_app.add_handler(CommandHandler("lookup", lookup))
    _bot_app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_input)
    )

    logger.info("🤖 Bot started")
    _bot_app.run_polling()


if __name__ == "__main__":
    main()
