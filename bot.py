import os
import json
import asyncio
import logging
import aiohttp

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.environ["BOT_TOKEN"]
API_URL = os.environ["API_URL"]

DELETE_AFTER_SECONDS = 30
MAX_MESSAGE_CHARS = 3800
used_users = set()  # Resets if Railway/Render restarts.

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def clean_api_response(data):
    """
    For authorized/demo APIs only.
    Remove API metadata from the top-level response.
    """
    if not isinstance(data, dict):
        return data

    cleaned = dict(data)

    for key in ("number", "total", "powered_by", "api_info"):
        cleaned.pop(key, None)

    return cleaned


def format_demo_result(data):
    """Display cleaned data as readable text, not raw JSON."""
    if not isinstance(data, dict):
        return str(data)

    lines = []

    results = data.get("results")

    if isinstance(results, list):
        for i, item in enumerate(results, 1):
            if not isinstance(item, dict):
                lines.append(f"Result {i}: {item}")
                continue

            lines.append(f"Result {i}")

            # Generic demo-safe formatting.
            for key, value in item.items():
                if key == "connected_numbers":
                    continue

                label = key.replace("_", " ").title()
                if value is None:
                    value = "N/A"

                lines.append(f"{label}: {value}")

            lines.append("")

        return "\n".join(lines).strip()

    # Fallback for simple demo JSON.
    for key, value in data.items():
        if key == "results":
            continue
        label = key.replace("_", " ").title()
        lines.append(f"{label}: {value}")

    return "\n".join(lines)


def split_text(text, limit=MAX_MESSAGE_CHARS):
    return [text[i:i + limit] for i in range(0, len(text), limit)] or ["No data"]


async def delete_after(bot, chat_id, message_id):
    await asyncio.sleep(DELETE_AFTER_SECONDS)
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as exc:
        logger.warning("Delete failed: %s", exc)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["waiting_for_input"] = False
    await update.message.reply_text(
        "👋 Welcome!\n\n"
        "Use /lookup for an authorized/ num information lookup.\n"
        "The result is deleted automatically after 30 seconds.\n"
        "One successful lookup per user."
    )


async def lookup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id in used_users:
        await update.message.reply_text(
            "❌ Your one allowed lookup has already been used."
        )
        return

    context.user_data["waiting_for_input"] = True
    await update.message.reply_text("🔎 Send the demo input:")


async def handle_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not context.user_data.get("waiting_for_input"):
        return

    if user_id in used_users:
        context.user_data["waiting_for_input"] = False
        await update.message.reply_text(
            "❌ Your one allowed lookup has already been used."
        )
        return

    value = update.message.text.strip()

    if not value or len(value) > 200:
        await update.message.reply_text("❌ Invalid input.")
        return

    context.user_data["waiting_for_input"] = False

    try:
        # API_URL should be an authorized/demo endpoint with its parameter prefix.
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
                    await update.message.reply_text(
                        "❌ API did not return valid JSON."
                    )
                    return

        if isinstance(result, dict) and result.get("success") is True:
            used_users.add(user_id)

        # Remove API metadata before displaying anything.
        cleaned = clean_api_response(result)

        # Display readable text instead of raw JSON.
        output = format_demo_result(cleaned)

        messages = []
        for chunk in split_text(output):
            msg = await update.message.reply_text(chunk)
            messages.append(msg)

        # Delete all result chunks after 30 seconds.
        for msg in messages:
            asyncio.create_task(
                delete_after(
                    context.bot,
                    msg.chat_id,
                    msg.message_id,
                )
            )

    except asyncio.TimeoutError:
        await update.message.reply_text("❌ API request timed out.")
    except aiohttp.ClientError as exc:
        logger.exception("HTTP error: %s", exc)
        await update.message.reply_text("❌ API connection error.")
    except Exception as exc:
        logger.exception("Unexpected error: %s", exc)
        await update.message.reply_text("❌ Something went wrong.")


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("lookup", lookup))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_input)
    )

    logger.info("Bot started.")
    app.run_polling()


if __name__ == "__main__":
    main()
