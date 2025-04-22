# Slack Chatbot with Gemini 2.5 Pro API

A Slack chatbot that uses Google's Gemini 2.5 Pro API to respond to messages and mentions in Slack, with persistent conversation memory for each user.

## Features

- Responds to direct messages in Slack
- Responds to mentions in channels
- Uses Gemini 2.5 Pro for generating intelligent responses
- Built with Flask and Slack Bolt Framework
- **Persistent Memory**: Maintains separate conversation history for each user
- **Context-Aware Responses**: Uses previous conversation context to generate more relevant responses
- **Google Search Grounding**: Uses Google Search to ground responses in real-time web information

## Prerequisites

- Python 3.12+
- A Slack workspace where you can create apps
- Google AI API key for Gemini

## Setup Instructions

### 1. Install Dependencies with uv

[uv](https://github.com/astral-sh/uv) is a fast Python package installer and resolver. Install it first if you don't have it:

```bash
pip install uv
```

Then install the project dependencies:

```bash
uv pip install flask slack-bolt python-dotenv google-generativeai
```

### 2. Create a Slack App

1. Go to [https://api.slack.com/apps](https://api.slack.com/apps) and click "Create New App"
2. Choose "From scratch" and provide a name and workspace
3. Under "OAuth & Permissions", add the following Bot Token Scopes:
   - `app_mentions:read`
   - `chat:write`
   - `im:history`
   - `im:read`
   - `im:write`
4. Install the app to your workspace
5. Copy the "Bot User OAuth Token" (starts with `xoxb-`)
6. Go to "Basic Information" and copy the "Signing Secret"

### 3. Configure Environment Variables

Update the `.env` file with your credentials:

```
GOOGLE_API_KEY=your-google-api-key
SLACK_BOT_TOKEN=xoxb-your-token-here
SLACK_SIGNING_SECRET=your-signing-secret-here
PORT=3000
```

### 4. Configure Event Subscriptions

1. In your Slack App settings, go to "Event Subscriptions"
2. Enable events and set the Request URL to your server URL + `/slack/events`
   - For local development, you'll need a tunneling service like ngrok
3. Subscribe to bot events:
   - `app_mention`
   - `message.im`
4. Save changes

### 5. Run the Server

```bash
python slack_bot.py
```

## Usage

- In a channel where the bot is invited, mention the bot with `@YourBotName` followed by your question
- Send a direct message to the bot with your question
- The bot will remember your previous conversations and maintain context

## Session Memory System

The bot maintains separate conversation history for each user in JSON files stored in the `sessions` directory. This allows the bot to:

1. Remember previous interactions with each user
2. Provide context-aware responses based on conversation history
3. Maintain separate conversation threads for different users

### Clearing Conversation History

To clear a user's conversation history, you can access the following endpoint:

```
GET /clear-history/{user_id}
```

Replace `{user_id}` with the Slack user ID of the user whose history you want to clear.

## Testing

The project includes two test scripts:

1. `test_gemini.py` - Tests the connection to the Gemini API and lists available models
2. `demo_bot.py` - A simple interactive chat demo that uses the Gemini API without requiring Slack

To run the test scripts:

```bash
# Test the Gemini API connection and list available models
python test_gemini.py

# Run the interactive chat demo
python demo_bot.py
```

### Demo Bot Commands

When using the demo bot, you can:
- Type `exit`, `quit`, or `bye` to end the session
- Type `clear` to clear your conversation history

### Model Information

This project uses the `gemini-2.5-flash-preview-04-17` model, which is the experimental version of Google's Gemini 2.5 Pro model. This model is available with the free tier of the Gemini API. If this model is not available with your API key, the application will fall back to other available models like `gemini-1.5-pro`.

## Development

### Local Testing with ngrok

To test your bot locally, you can use ngrok to create a secure tunnel:

1. Install ngrok from [https://ngrok.com/](https://ngrok.com/)
2. Run ngrok: `ngrok http 3000`
3. Copy the https URL provided by ngrok
4. Update your Slack app's Request URL to the ngrok URL + `/slack/events`

## Deployment

For production deployment, consider using a cloud platform like:
- Heroku
- AWS
- Google Cloud Platform
- Microsoft Azure

## License

MIT