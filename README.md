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

## Basic OpenAI API Usage with Memory and Web Search

This app uses the OpenAI Responses API. The important part of the OpenAI call is:

```python
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
```

The `input` field is the user's latest Telegram message.

The `instructions` field is the system prompt from `config.yml`. This is where you define the assistant's behavior:

```yaml
openai:
  system_prompt: you are helpful assistant
```

The `tools` field enables web search:

```python
openai_tools = [{"type": "web_search"}]
```

With `tool_choice` set to `auto`, the model can decide when web search is useful. This is helpful for questions about current events, prices, schedules, recent facts, or anything that may have changed recently.

The `store=True` setting allows the response to be stored by OpenAI so the app can refer to it later by ID.

The `previous_response_id` field gives the model memory. After each response, the app saves:

```python
openai_chat["previous_response_id"] = openai_response.id
```

On the next message from the same Telegram chat, the app sends that saved ID back to OpenAI. This creates a conversation chain, so the model can understand earlier messages in the same chat.

## Memory Limitations

The memory in this tutorial is intentionally simple.

The app stores chat memory in this Python dictionary:

```python
chats = {}
```

This means:

- Memory is kept only while the server process is running.
- Memory is lost when the app restarts, redeploys, crashes, or scales to a different server instance.
- Memory is separate for each Telegram chat ID.
- The app stores only the latest `previous_response_id`, not a full local transcript.
- Longer conversations still have context limits. Very long chats may eventually need summarizing or trimming.
- Previous conversation context can increase token usage because earlier context may be included when the model responds.
- Web search may add latency and tool-call cost when the model decides to search.

This setup is good for a tutorial because it keeps the code short. For production, use persistent storage.

## Adding Persistent Chat History Later

To keep memory after restarts, store the chat state in a database instead of only using the `chats` dictionary.

A simple database table can look like this:

```text
telegram_chat_id
previous_response_id
updated_at
```

The flow becomes:

1. Telegram sends a message.
2. Look up `previous_response_id` by `telegram_chat_id` in the database.
3. If a previous response ID exists, include it in the OpenAI request.
4. Send the message to OpenAI.
5. Save the new `openai_response.id` back to the database.
6. Send `openai_response.output_text` back to Telegram.

For a small project, SQLite is enough. For a deployed app, use a managed database such as PostgreSQL, Redis, or another storage service available on your hosting platform.

If you also want a readable transcript, create a second table:

```text
telegram_chat_id
role
message_text
created_at
```

Then save each user message and assistant reply:

```text
telegram_chat_id | role      | message_text
12345            | user      | What is Python?
12345            | assistant | Python is a programming language...
```

You can use this transcript for debugging, analytics, or rebuilding context if needed. Keep privacy in mind: if you store user messages, tell users what you store and protect the database.

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
