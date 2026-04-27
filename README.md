# Basic Introduction to Webhooks

A webhook is a way for one application to automatically notify another application when something happens.

Instead of your app repeatedly asking, "Is there anything new?", the other service sends a request to your app as soon as there is an update.

For a Telegram bot, a webhook means:

1. A user sends a message to your bot.
2. Telegram receives the message.
3. Telegram sends the message data to your server URL using an HTTPS POST request.
4. Your server handles the message and can reply using the Telegram Bot API.

This is different from polling, where your app keeps calling Telegram's `getUpdates` method to ask for new messages.

## Telegram BotFather Example

BotFather is used to create and manage Telegram bots. It gives you a bot token, which is required when calling the Telegram Bot API.

### 1. Create a Bot and Get the Token

1. Open Telegram.
2. Search for `@BotFather`.
3. Start a chat with BotFather.
4. Send:

```text
/newbot
```

5. Follow the instructions.
6. Copy the bot token BotFather gives you.

The token usually looks similar to this:

```text
123456789:ABCdefYourBotTokenHere
```

Keep this token private. Anyone with the token can control your bot.

## Create a Webhook Manually

Before creating a webhook, you need a public HTTPS URL that Telegram can reach. If the server is deployed on Render, the URL usually looks like:

Example Render webhook URL:

```text
https://<RENDER_SERVICE_NAME>.onrender.com/telegram_webhook
```

To set the webhook manually, run:

```bash
curl "https://api.telegram.org/bot<BOT_TOKEN>/setWebhook?url=<WEBHOOK_URL>"
```

Example:

```bash
curl "https://api.telegram.org/bot123456789:ABCdefYourBotTokenHere/setWebhook?url=https://my-telegram-bot.onrender.com/telegram_webhook"
```

If successful, Telegram returns a response similar to:

```json
{
  "ok": true,
  "result": true,
  "description": "Webhook was set"
}
```

## Check the Current Webhook

To check whether a webhook is currently set:

```bash
curl "https://api.telegram.org/bot<BOT_TOKEN>/getWebhookInfo"
```

Example:

```bash
curl "https://api.telegram.org/bot123456789:ABCdefYourBotTokenHere/getWebhookInfo"
```

This shows the current webhook URL, pending updates, and recent delivery errors if any exist.

## Delete a Webhook Manually

If you want to remove the webhook and switch back to polling with `getUpdates`, run:

```bash
curl "https://api.telegram.org/bot<BOT_TOKEN>/deleteWebhook"
```

Example:

```bash
curl "https://api.telegram.org/bot123456789:ABCdefYourBotTokenHere/deleteWebhook"
```

If you also want Telegram to drop pending updates that were not delivered yet:

```bash
curl "https://api.telegram.org/bot<BOT_TOKEN>/deleteWebhook?drop_pending_updates=true"
```

## Important Notes

- Telegram webhooks require a public HTTPS endpoint.
- Do not share your bot token in public code, screenshots, or logs.
- A bot cannot use webhook delivery and `getUpdates` polling at the same time.
- Use `getWebhookInfo` when debugging webhook problems.
- Your webhook route should accept POST requests from Telegram.

## Flask App Configuration

The Flask app in `app.py` uses OpenAI with chat memory and web search. It also exposes a Telegram webhook endpoint.

Adjust the OpenAI model, system prompt, and webhook URL in `config.yml`:

```yaml
openai:
  model: gpt-5-mini
  system_prompt: you are helpful assistant

webhook:
  base_url: https://<RENDER_SERVICE_NAME>.onrender.com
  path: /telegram_webhook
```

Keep secrets in environment variables, not in `config.yml`. Set these environment variables on Render:

```text
OPENAI_API_KEY=your_openai_api_key
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
```

Optional environment variables can override `config.yml`:

```text
OPENAI_MODEL=gpt-5-mini
WEBHOOK_BASE_URL=https://<RENDER_SERVICE_NAME>.onrender.com
WEBHOOK_PATH=/telegram_webhook
CONFIG_PATH=config.yml
```

The system prompt is edited in `config.yml` under `openai.system_prompt`.

Render start command:

```bash
gunicorn app:app
```

The app provides:

- `GET /` to show the current webhook information.
- `POST /telegram_webhook` for Telegram webhook updates.

## How the Flask App Works

When the app starts, it first reads `config.yml` and environment variables. The YAML file stores easy-to-change settings like the OpenAI model, system prompt, and webhook URL. Environment variables store private values like `OPENAI_API_KEY` and `TELEGRAM_BOT_TOKEN`.

The app then creates an OpenAI client and configures each response with:

- A system prompt from `config.yml`.
- OpenAI web search.
- A previous response ID per `session_id` or Telegram chat ID, stored in memory.

Each OpenAI response is created with `store=True`. The app then saves the response ID in its local `chats` dictionary and passes that ID as `previous_response_id` on the next message from the same Telegram chat.

The basic flow for `/telegram_webhook` is:

1. A Telegram user sends a message to the bot.
2. Telegram sends the update to `/telegram_webhook`.
3. Flask extracts the chat ID and text.
4. The app sends the text to OpenAI using the Telegram chat ID as memory.
5. The app sends OpenAI's reply back to the user through Telegram.

The `/` route is only for checking the app. It returns information such as the configured OpenAI model, webhook path, and webhook URL.

## Why Delete the Webhook on Startup?

On startup, the app deletes the existing Telegram webhook with `drop_pending_updates=true`, then sets the webhook again.

This helps during tutorials and redeployments because Telegram may have old undelivered messages waiting in its queue. If those pending updates are not dropped, Telegram can send old messages to the newly deployed app as soon as the webhook is restored. That can make the bot reply to stale messages and confuse testing.

Resetting the webhook gives the app a clean start:

1. Remove the old webhook.
2. Drop pending updates.
3. Set the webhook again using the current Render URL.

For production apps, you may choose not to drop pending updates if every message must be processed.

Example webhook info request:

```bash
curl "https://<RENDER_SERVICE_NAME>.onrender.com/"
```
