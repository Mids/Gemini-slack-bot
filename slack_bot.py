import os
import json
import logging
import datetime
from flask import Flask, request, jsonify
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
import google.generativeai as genai

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Gemini API
genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))

# Create sessions directory if it doesn't exist
SESSIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sessions")
os.makedirs(SESSIONS_DIR, exist_ok=True)

# Create config directory if it doesn't exist
CONFIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")
os.makedirs(CONFIG_DIR, exist_ok=True)

# Maximum number of messages to keep in history
MAX_HISTORY_SIZE = 50

# Default configuration file path
DEFAULT_CONFIG_PATH = os.path.join(CONFIG_DIR, "slack_config.json")

class SlackBotManager:
    """Manager class to handle multiple Slack bot instances"""
    
    def __init__(self):
        self.bots = {}
        self.handlers = {}
        self.flask_app = Flask(__name__)
        
        # Load configurations
        self.load_configurations()
        
        # Set up Flask routes
        self.setup_routes()
    
    def load_configurations(self):
        """Load bot configurations from the config file"""
        try:
            if not os.path.exists(DEFAULT_CONFIG_PATH):
                # Create default config if it doesn't exist
                default_config = [{
                    "app_id": "default",
                    "team_id": os.environ.get("SLACK_TEAM_ID", ""),
                    "bot_token": os.environ.get("SLACK_BOT_TOKEN", ""),
                    "signing_secret": os.environ.get("SLACK_SIGNING_SECRET", ""),
                    "model": "gemini-2.0-flash-lite",
                    "system_instruction": "Keep your responses simple, short, and conversational like a Slack chat. Avoid lengthy explanations. Be direct and concise."
                }]
                
                with open(DEFAULT_CONFIG_PATH, 'w', encoding='utf-8') as f:
                    json.dump(default_config, f, indent=2)
                
                logger.info(f"Created default configuration at {DEFAULT_CONFIG_PATH}")
            
            # Load configuration
            with open(DEFAULT_CONFIG_PATH, 'r', encoding='utf-8') as f:
                configs = json.load(f)
            
            # Initialize bots for each configuration
            for config in configs:
                app_id = config.get("app_id", "default")
                bot_token = config.get("bot_token", os.environ.get("SLACK_BOT_TOKEN"))
                signing_secret = config.get("signing_secret", os.environ.get("SLACK_SIGNING_SECRET"))
                model_name = config.get("model", "gemini-2.0-flash-lite")
                system_instruction = config.get("system_instruction", 
                                              "Keep your responses simple, short, and conversational like a Slack chat. Avoid lengthy explanations. Be direct and concise.")
                
                if not bot_token or not signing_secret:
                    logger.warning(f"Missing credentials for app {app_id}. Skipping.")
                    continue
                
                # Initialize Slack app
                app = App(token=bot_token, signing_secret=signing_secret)
                
                # Initialize Gemini model
                model = genai.GenerativeModel(model_name, system_instruction=system_instruction)
                
                # Store app, handler, and model
                self.bots[app_id] = {
                    "app": app,
                    "model": model,
                    "config": config
                }
                
                self.handlers[app_id] = SlackRequestHandler(app)
                
                # Register event handlers
                self.register_event_handlers(app_id)
                
                logger.info(f"Initialized bot for app {app_id}")
        
        except Exception as e:
            logger.error(f"Error loading configurations: {str(e)}")
            # Fall back to environment variables if config fails
            self.initialize_default_bot()
    
    def initialize_default_bot(self):
        """Initialize a default bot using environment variables"""
        try:
            app_id = "default"
            bot_token = os.environ.get("SLACK_BOT_TOKEN")
            signing_secret = os.environ.get("SLACK_SIGNING_SECRET")
            
            if not bot_token or not signing_secret:
                logger.error("Missing required environment variables SLACK_BOT_TOKEN and SLACK_SIGNING_SECRET")
                return
            
            # Initialize Slack app
            app = App(token=bot_token, signing_secret=signing_secret)
            
            # Initialize Gemini model
            system_instruction = "Keep your responses simple, short, and conversational like a Slack chat. Avoid lengthy explanations. Be direct and concise."
            model = genai.GenerativeModel('gemini-2.0-flash-lite', system_instruction=system_instruction)
            
            # Store app, handler, and model
            self.bots[app_id] = {
                "app": app,
                "model": model,
                "config": {
                    "app_id": app_id,
                    "bot_token": bot_token,
                    "signing_secret": signing_secret,
                    "model": "gemini-2.0-flash-lite",
                    "system_instruction": system_instruction
                }
            }
            
            self.handlers[app_id] = SlackRequestHandler(app)
            
            # Register event handlers
            self.register_event_handlers(app_id)
            
            logger.info(f"Initialized default bot from environment variables")
        
        except Exception as e:
            logger.error(f"Error initializing default bot: {str(e)}")
    
    def register_event_handlers(self, app_id):
        """Register event handlers for a specific app"""
        app = self.bots[app_id]["app"]
        
        @app.event("app_mention")
        def handle_app_mention(body, say):
            """Handle mentions of the bot in channels"""
            try:
                # Extract the text, user ID, and channel ID from the mention
                text = body["event"]["text"]
                user_id = body["event"]["user"]
                channel_id = body["event"]["channel"]
                
                # Get user info
                user_info = self.get_user_info(app_id, user_id)
                user_name = user_info.get("name")
                
                # Get thread_ts only if the message is in a thread
                thread_ts = body["event"].get("thread_ts")
                
                # Extract the bot ID from the event
                bot_id = body["event"].get("bot_id") or app.client.auth_test()["user_id"]
                bot_mention = f"<@{bot_id}>"
                
                # Remove the bot mention to get the query, regardless of where it appears
                query = text.replace(bot_mention, "").strip()
                
                if not query:
                    # Respond in thread if in thread, otherwise in channel
                    if thread_ts:
                        say(text="How can I help you today?", thread_ts=thread_ts)
                    else:
                        say(text="How can I help you today?")
                    return
                
                # Log the incoming query
                logger.info(f"[{app_id}] Received query from user {user_name} ({user_id}) in channel {channel_id}: {query}")
                
                # For threads, use the user's history
                # For channel messages, use the channel's history
                if thread_ts:
                    # Use user history for threads
                    history_id = f"{app_id}_{user_id}"
                    is_channel = False
                    response_text = self.generate_response_with_history(app_id, history_id, query, is_channel)
                else:
                    # Use channel history for main channel
                    history_id = f"{app_id}_channel_{channel_id}"
                    is_channel = True
                    response_text = self.generate_response_with_history(app_id, history_id, query, is_channel, user_id, user_name)
                
                # Send the response back to Slack in the same thread if applicable
                if thread_ts:
                    say(text=response_text, thread_ts=thread_ts)
                else:
                    say(text=response_text)
                
            except Exception as e:
                logger.error(f"[{app_id}] Error handling app mention: {str(e)}")
                say("Sorry, I encountered an error processing your request.")
        
        @app.event("message")
        def handle_direct_message(body, say):
            """Handle direct messages to the bot"""
            try:
                # Skip messages from the bot itself to avoid loops
                if body.get("event", {}).get("bot_id"):
                    return
                
                # Extract the message text and user ID
                text = body["event"]["text"]
                user_id = body["event"]["user"]
                
                # Get user info
                user_info = self.get_user_info(app_id, user_id)
                user_name = user_info.get("name")
                
                # Get thread_ts only if the message is in a thread
                thread_ts = body["event"].get("thread_ts")
                
                if not text:
                    # Respond in thread if in thread, otherwise in channel
                    if thread_ts:
                        say(text="How can I help you today?", thread_ts=thread_ts)
                    else:
                        say(text="How can I help you today?")
                    return
                
                # Log the incoming message
                logger.info(f"[{app_id}] Received DM from user {user_name} ({user_id}): {text}")
                
                # Generate response using Gemini with user's chat history
                history_id = f"{app_id}_{user_id}"
                response_text = self.generate_response_with_history(app_id, history_id, text, False, user_id, user_name)
                
                # Send the response back to Slack in the same thread if applicable
                if thread_ts:
                    say(text=response_text, thread_ts=thread_ts)
                else:
                    say(text=response_text)
                
            except Exception as e:
                logger.error(f"[{app_id}] Error handling direct message: {str(e)}")
                say("Sorry, I encountered an error processing your request.")
    
    def setup_routes(self):
        """Set up Flask routes for all bots"""
        
        @self.flask_app.route("/slack/events", methods=["POST"])
        def slack_events():
            """Endpoint for Slack events"""
            # Check if this is a URL verification challenge
            if request.json and request.json.get("type") == "url_verification":
                logger.info("Received URL verification challenge")
                return jsonify({"challenge": request.json.get("challenge")})
            
            # Determine which app should handle this request based on the team_id
            # Team ID could be at the top level or in the event/team object
            team_id = request.json.get("team_id")
            if not team_id and request.json.get("event"):
                team_id = request.json.get("event", {}).get("team")
            
            # Log the incoming request details for debugging
            logger.info(f"Received request from team_id: {team_id}")
            logger.info(f"Request type: {request.json.get('type')}")
            
            # If we still don't have a team_id but have a token, try to match by token
            if not team_id and request.headers.get("X-Slack-Signature"):
                logger.info("No team_id found, trying to match by signature")
                # Try each handler until one accepts the request
                for app_id, handler in self.handlers.items():
                    try:
                        response = handler.handle(request)
                        logger.info(f"Handler for app {app_id} accepted the request")
                        return response
                    except Exception as e:
                        logger.debug(f"Handler for app {app_id} rejected: {str(e)}")
                        continue
            
            # Find the appropriate handler based on team_id
            handler = None
            for app_id, bot_data in self.bots.items():
                config_team_id = bot_data["config"].get("team_id")
                logger.info(f"Checking app {app_id} with team_id {config_team_id}")
                if config_team_id == team_id:
                    handler = self.handlers[app_id]
                    logger.info(f"Found handler for app {app_id}")
                    break
            
            # If no specific handler found, use the default
            if not handler and "default" in self.handlers:
                handler = self.handlers["default"]
                logger.info("Using default handler as fallback")
            
            if handler:
                try:
                    response = handler.handle(request)
                    return response
                except Exception as e:
                    logger.error(f"Error handling request: {str(e)}")
                    return jsonify({"error": str(e)}), 500
            else:
                logger.error(f"No handler available for team {team_id}")
                return jsonify({"error": "No handler available for this team"}), 400
        
        @self.flask_app.route("/slack/events/<app_id>", methods=["POST"])
        def slack_events_by_app(app_id):
            """Endpoint for Slack events for a specific app"""
            if app_id in self.handlers:
                return self.handlers[app_id].handle(request)
            else:
                return jsonify({"error": f"No handler available for app {app_id}"}), 400
        
        @self.flask_app.route("/health", methods=["GET"])
        def health_check():
            """Health check endpoint"""
            return jsonify({"status": "ok"})
        
        @self.flask_app.route("/clear-history/<app_id>/<user_id_or_channel>", methods=["GET"])
        def clear_history(app_id, user_id_or_channel):
            """Clear chat history for a user or channel in a specific app"""
            try:
                history_id = f"{app_id}_{user_id_or_channel}"
                session_file = self.get_session_file(history_id)
                if os.path.exists(session_file):
                    os.remove(session_file)
                    return jsonify({"status": "success", "message": f"Chat history cleared for {app_id}/{user_id_or_channel}"})
                return jsonify({"status": "success", "message": f"No chat history found for {app_id}/{user_id_or_channel}"})
            except Exception as e:
                return jsonify({"status": "error", "message": str(e)})
    
    def get_session_file(self, user_id_or_channel):
        """Get the path to the session file for a user or channel"""
        return os.path.join(SESSIONS_DIR, f"{user_id_or_channel}.json")
    
    def load_chat_history(self, user_id_or_channel):
        """Load chat history for a user or channel from their session file"""
        session_file = self.get_session_file(user_id_or_channel)
        if os.path.exists(session_file):
            try:
                with open(session_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading chat history for {user_id_or_channel}: {str(e)}")
        return []
    
    def save_chat_history(self, user_id_or_channel, chat_history):
        """Save chat history for a user or channel to their session file"""
        # Limit the history size
        if len(chat_history) > MAX_HISTORY_SIZE * 2:  # *2 because each exchange has user and bot messages
            # Keep only the most recent messages
            chat_history = chat_history[-MAX_HISTORY_SIZE * 2:]
        
        session_file = self.get_session_file(user_id_or_channel)
        try:
            with open(session_file, 'w', encoding='utf-8') as f:
                json.dump(chat_history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving chat history for {user_id_or_channel}: {str(e)}")
    
    def get_user_info(self, app_id, user_id):
        """Get user information from Slack API"""
        try:
            app = self.bots[app_id]["app"]
            result = app.client.users_info(user=user_id)
            if result["ok"]:
                user = result["user"]
                return {
                    "id": user_id,
                    "name": user.get("real_name") or user.get("name", "Unknown User"),
                    "display_name": user.get("profile", {}).get("display_name", "")
                }
        except Exception as e:
            logger.error(f"[{app_id}] Error getting user info: {str(e)}")
        return {"id": user_id, "name": "Unknown User", "display_name": ""}
    
    def generate_response_with_history(self, app_id, user_id_or_channel, query, is_channel=False, user_id=None, user_name=None):
        """Generate a response using Gemini with the user's or channel's chat history"""
        # Load the chat history
        chat_history = self.load_chat_history(user_id_or_channel)
        
        try:
            # Get the model for this app
            model = self.bots[app_id]["model"]
            
            # Format chat history for Gemini
            formatted_history = []
            for entry in chat_history[-20:]:  # Use last 20 messages to avoid context limits
                content = entry["content"]
                
                # If this is a channel message and has user info, prefix with user name
                if is_channel and entry.get("user_name") and entry["role"] == "user":
                    content = f"{entry['user_name']}: {content}"
                    
                formatted_history.append({
                    "role": "user" if entry["role"] == "user" else "model",
                    "parts": [content]
                })
            
            # Format the current query with user name for channel messages
            current_query = query
            if is_channel and user_name:
                current_query = f"{user_name}: {query}"
            
            # Add the current query
            if formatted_history:
                # Continue the conversation with history
                chat = model.start_chat(history=formatted_history)
                response = chat.send_message(current_query)
            else:
                # Start a new conversation
                chat = model.start_chat()
                response = chat.send_message(current_query)
            
            # Get the response text
            response_text = response.text
            
            # Add the query and response to chat history
            timestamp = datetime.datetime.now().isoformat()
            
            # For channels, include the user ID and name in the content to track who said what
            if is_channel and user_id:
                user_message = {
                    "role": "user", 
                    "content": query,  # Store original query without name prefix
                    "timestamp": timestamp,
                    "user_id": user_id,  # Store the user ID explicitly
                    "user_name": user_name or "Unknown User"  # Store the user name if available
                }
                chat_history.append(user_message)
            else:
                chat_history.append({"role": "user", "content": query, "timestamp": timestamp})
            
            chat_history.append({"role": "bot", "content": response_text, "timestamp": timestamp})
            
            # Save the updated chat history
            self.save_chat_history(user_id_or_channel, chat_history)
            
            return response_text
            
        except Exception as e:
            logger.error(f"[{app_id}] Error generating response: {str(e)}")
            return f"Sorry, I encountered an error: {str(e)}"
    
    def run(self, host='0.0.0.0', port=3000):
        """Run the Flask app"""
        self.flask_app.run(host=host, port=port)

# Create and run the bot manager
if __name__ == "__main__":
    bot_manager = SlackBotManager()
    bot_manager.run()
