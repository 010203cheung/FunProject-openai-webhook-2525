import os

import requests
import yaml
from flask import Flask, jsonify, request
from openai import OpenAI


# Overview:
# This Flask app connects a Telegram bot to OpenAI.
# Telegram sends user messages to the /telegram_webhook route.
# The app forwards each message to OpenAI, using previous response IDs for memory.
# OpenAI is configured with web search and a system prompt.
# The app then sends OpenAI's reply back to the same Telegram chat.

app = Flask(__name__)


# Load settings from config.yml.
# These are non-secret values that are easy to change, such as:
# - OpenAI model
# - system prompt
# - Telegram webhook URL and path
def load_config():
    config_path = os.getenv("CONFIG_PATH", "config.yml")
    if not os.path.exists(config_path):
        return {}

    with open(config_path, "r", encoding="utf-8") as config_file:
        return yaml.safe_load(config_file) or {}


config = load_config()
openai_settings = config.get("openai", {})
webhook_settings = config.get("webhook", {})

# Read secrets and config values.
# Secrets come from environment variables.
# Non-secret settings can come from config.yml, with environment variables as overrides.
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
MODEL_ID = os.getenv("OPENAI_MODEL", openai_settings.get("model", "gpt-5-mini"))
SYSTEM_PROMPT = openai_settings.get("system_prompt", "you are helpful assistant")

WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", webhook_settings.get("path", "/telegram_webhook"))
if not WEBHOOK_PATH.startswith("/"):
    WEBHOOK_PATH = f"/{WEBHOOK_PATH}"

# Build the public webhook base URL.
# On Render, you can set WEBHOOK_BASE_URL manually in the dashboard.
# If Render provides RENDER_EXTERNAL_HOSTNAME, the app can also build the URL from it.
render_hostname = os.getenv("RENDER_EXTERNAL_HOSTNAME")
WEBHOOK_BASE_URL = (
    os.getenv("WEBHOOK_BASE_URL")
    or os.getenv("RENDER_EXTERNAL_URL")
    or webhook_settings.get("base_url")
)
if not WEBHOOK_BASE_URL and render_hostname:
    WEBHOOK_BASE_URL = f"https://{render_hostname}"

# Build the Telegram Bot API base URL.
telegram_api_url = (
    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
    if TELEGRAM_BOT_TOKEN
    else None
)

# Create the OpenAI client and response config.
# The web_search tool allows OpenAI to search the web during a response.
openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
openai_tools = [{"type": "web_search"}]

# Store chat sessions in memory.
# Each Telegram chat ID gets its own OpenAI response state.
# This gives the bot short-term memory while the server is running.
chats = {}


# Find an existing OpenAI chat state or create a new one.
def get_or_create_chat(session_id):
    """Keep one OpenAI response chain per user/session so short-term memory is preserved."""
    if not openai_client:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    if session_id not in chats:
        chats[session_id] = {"previous_response_id": None}

    return chats[session_id]


# Reset the Telegram webhook when the app starts.
# This removes old pending Telegram updates, then points Telegram to this app.
def configure_telegram_webhook():
    if not telegram_api_url or not WEBHOOK_BASE_URL:
        app.logger.info("Telegram webhook setup skipped: missing token or base URL")
        return

    webhook_url = f"{WEBHOOK_BASE_URL.rstrip('/')}{WEBHOOK_PATH}"

    delete_response = requests.post(
        f"{telegram_api_url}/deleteWebhook",
        params={"drop_pending_updates": "true"},
        timeout=20,
    )
    delete_response.raise_for_status()

    set_response = requests.post(
        f"{telegram_api_url}/setWebhook",
        params={"url": webhook_url},
        timeout=20,
    )
    set_response.raise_for_status()

    app.logger.info("Telegram webhook configured: %s", webhook_url)


# Simple info route.
# Open this route in the browser to confirm the app is running and see the webhook URL.
@app.get("/")
def webhook_info():
    webhook_url = None
    if WEBHOOK_BASE_URL:
        webhook_url = f"{WEBHOOK_BASE_URL.rstrip('/')}{WEBHOOK_PATH}"

    return jsonify(
        {
            "status": "ok",
            "model": MODEL_ID,
            "webhook_path": WEBHOOK_PATH,
            "webhook_url": webhook_url,
        }
    )


# Main Telegram webhook route.
# Telegram sends incoming bot messages here as JSON.
# The function extracts the user's message, sends it to OpenAI, then replies in Telegram.
@app.post(WEBHOOK_PATH)
def telegram_webhook():
    update = request.get_json(silent=True) or {}
    message = update.get("message") or update.get("edited_message") or {}
    text = message.get("text")
    chat = message.get("chat") or {}
    chat_id = chat.get("id")

    if not text or not chat_id:
        return jsonify({"ok": True, "ignored": True})

    try:
        openai_chat = get_or_create_chat(f"telegram:{chat_id}")
        request_kwargs = {
            "model": MODEL_ID,
            "instructions": SYSTEM_PROMPT,
            "tools": openai_tools,
            "tool_choice": "auto",
            "store": True,
            "input": text,
        }

        previous_response_id = openai_chat.get("previous_response_id")
        if previous_response_id:
            request_kwargs["previous_response_id"] = previous_response_id

        openai_response = openai_client.responses.create(**request_kwargs)
        openai_chat["previous_response_id"] = openai_response.id
        reply = openai_response.output_text or ""

        telegram_response = requests.post(
            f"{telegram_api_url}/sendMessage",
            json={"chat_id": chat_id, "text": reply},
            timeout=20,
        )
        telegram_response.raise_for_status()
    except Exception as exc:
        app.logger.exception("Telegram webhook failed")
        return jsonify({"ok": False, "error": str(exc)}), 500

    return jsonify({"ok": True})


# Configure the Telegram webhook once when the app process starts.
# If setup fails, the app still starts so the error can be inspected in logs.
try:
    configure_telegram_webhook()
except Exception:
    app.logger.exception("Telegram webhook setup failed")


# Local development entry point.
# Render should use gunicorn app:app instead.
if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
