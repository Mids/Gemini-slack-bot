import os
import json
import logging
import datetime
import os
from flask import Flask, request, jsonify
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from flat_memory_manager import FlatMemoryManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Gemini API
genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))

# Define search function for Gemini
search_function = {
    "name": "search_web",
    "description": "Search the web for current information",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query"
            }
        },
        "required": ["query"]
    }
}

# Create sessions directory if it doesn't exist
SESSIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sessions")
os.makedirs(SESSIONS_DIR, exist_ok=True)

# Create config directory if it doesn't exist
CONFIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")
os.makedirs(CONFIG_DIR, exist_ok=True)

# Create memory directory if it doesn't exist
MEMORY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory")
os.makedirs(MEMORY_DIR, exist_ok=True)

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
        
        # Initialize memory manager
        self.memory = {}
        for workspace_id in ["workspace1", "workspace2"]:
            self.memory[workspace_id] = FlatMemoryManager(MEMORY_DIR, workspace_id)
        
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
                    "model": "gemini-2.5-flash-preview-04-17",
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
                model_name = config.get("model", "gemini-2.5-flash-preview-04-17")
                # Get current date and time
                current_date = datetime.datetime.now().strftime("%Y-%m-%d")
                current_day = datetime.datetime.now().strftime("%A")
                current_time = datetime.datetime.now().strftime("%H:%M:%S")
                
                # Add current date and time to system instruction
                base_instruction = config.get("system_instruction", 
                                            "Keep your responses simple, short, and conversational like a Slack chat. Avoid lengthy explanations. Be direct and concise.")
                
                # Encourage keyword extraction for search tool
                base_instruction += " When searching for current information, first extract concise search keywords from the user's question and use them as the query for your search_web tool."
                
                system_instruction = f"{base_instruction}\n\nIMPORTANT: Today's date is {current_date} ({current_day}), and the current time is {current_time}. Always use this information when asked about the current date or time."
                
                # Configure safety settings
                safety_settings = {
                    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
                }
                
                if not bot_token or not signing_secret:
                    logger.warning(f"Missing credentials for app {app_id}. Skipping.")
                    continue
                
                # Initialize Slack app
                app = App(token=bot_token, signing_secret=signing_secret)
                
                # Initialize Gemini model with Google Search capability
                model = genai.GenerativeModel(
                    model_name, 
                    system_instruction=system_instruction,
                    safety_settings=safety_settings,
                    generation_config={
                        "temperature": 0.7,
                        "top_p": 0.95,
                        "top_k": 40,
                    },
                    tools=[{"function_declarations": [search_function]}]  # Enable Google Search
                )
                
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
            
            # Configure safety settings
            safety_settings = {
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }
            
            generation_config = {
                "temperature": 0.7,
                "top_p": 0.95,
                "top_k": 40
            }
            
            # Initialize Gemini model with Google Search grounding
            system_instruction = ("Keep your responses simple, short, and conversational like a Slack chat. Avoid lengthy explanations. Be direct and concise. "
                                  "When searching for current information, first extract concise search keywords from the user's question and use them as the query for your search_web tool.")
            
            # For Gemini 2.5, we need to define function declarations for search
            search_function = {
                "name": "search_web",
                "description": "Search the web for information about a topic",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query"
                        }
                    },
                    "required": ["query"]
                }
            }
            
            # Initialize the model with the search function
            model = genai.GenerativeModel(
                'gemini-2.5-flash-preview-04-17', 
                system_instruction=system_instruction,
                safety_settings=safety_settings,
                generation_config=generation_config,
                tools=[{"function_declarations": [search_function]}]  # Enable Google Search as a tool
            )
            
            # Store app, handler, and model
            self.bots[app_id] = {
                "app": app,
                "model": model,
                "config": {
                    "app_id": app_id,
                    "bot_token": bot_token,
                    "signing_secret": signing_secret,
                    "model": "gemini-2.5-flash-preview-04-17",
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
                
                # Use workspace-wide history for both threads and channel messages
                history_id = f"{app_id}_channel_{channel_id}"
                is_channel = True
                response_text = self.generate_response_with_history(app_id, history_id, query, is_channel, user_id, user_name, thread_ts)
                
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
                
                # Generate response using Gemini with workspace-wide chat history
                # For DMs, we'll use the user ID as the channel ID to maintain separation between workspaces
                history_id = f"{app_id}_channel_{user_id}"
                response_text = self.generate_response_with_history(app_id, history_id, text, True, user_id, user_name, thread_ts)
                
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
                logger.info("Using default handler")
            
            # If we have a handler, use it to handle the request
            if handler:
                return handler.handle(request)
            else:
                logger.error(f"No handler found for team_id: {team_id}")
                return jsonify({"error": "No handler available for this team"}), 400
    

    
    def load_chat_history(self, user_id_or_channel):
        """Load chat history for a user or channel from their session file"""
        # For workspace-wide history, extract the workspace ID
        if user_id_or_channel.startswith("workspace") and "_channel_" in user_id_or_channel:
            # Extract workspace ID from the format "workspace{id}_channel_{channel_id}"
            workspace_id = user_id_or_channel.split("_channel_")[0]
            session_file = os.path.join(SESSIONS_DIR, f"{workspace_id}.json")
        else:
            session_file = os.path.join(SESSIONS_DIR, f"{user_id_or_channel}.json")
            
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
        
        # For workspace-wide history, extract the workspace ID
        if user_id_or_channel.startswith("workspace") and "_channel_" in user_id_or_channel:
            # Extract workspace ID from the format "workspace{id}_channel_{channel_id}"
            workspace_id = user_id_or_channel.split("_channel_")[0]
            session_file = os.path.join(SESSIONS_DIR, f"{workspace_id}.json")
        else:
            session_file = os.path.join(SESSIONS_DIR, f"{user_id_or_channel}.json")
            
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
    
    def generate_response_with_history(self, app_id, user_id_or_channel, query, is_channel=False, user_id=None, user_name=None, thread_ts=None):
        """Generate a response using Gemini with the user's or channel's chat history"""
        # Load the chat history
        chat_history = self.load_chat_history(user_id_or_channel)
        
        # Extract workspace ID from user_id_or_channel
        workspace_id = app_id
        if "_channel_" in user_id_or_channel:
            parts = user_id_or_channel.split("_channel_")
            if len(parts) > 0:
                workspace_id = parts[0]
        
        try:
            # Get the model for this app
            model = self.bots[app_id]["model"]
            
            # Get memory context
            memory_context = ""
            
            try:
                # Get memory context for this workspace
                if user_id and not is_channel:
                    memory_context = self.memory[workspace_id].get_context_for_user(user_id)
                else:
                    # For channels, just get general context
                    memory_context = self.memory[workspace_id].get_context_for_user()
            except Exception as e:
                logger.error(f"Error getting memory context: {str(e)}")
            
            # Format chat history for Gemini
            formatted_history = []
            
            # Add memory prompt as system message if it's not empty
            if memory_context.strip():
                formatted_history.append({
                    "role": "model",
                    "parts": [f"I have access to the following important information that I should remember:\n\n{memory_context}"]
                })
            
            # Add recent conversation history
            for entry in chat_history[-20:]:  # Use last 20 messages to avoid context limits
                content = entry["content"]
                
                # If this is a channel message and has user info, prefix with user name only (no channel prefix)
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
                # Create a generation config for the message
                generation_config = {
                    "response_mime_type": "text/plain"
                }
                
                # Send the message with standard parameters
                response = chat.send_message(
                    current_query,
                    generation_config=generation_config,
                    stream=False
                )
                
                # Handle function calling for search_web
                response_text = self._process_function_calls(response, chat, current_query)
            else:
                # Start a new conversation
                chat = model.start_chat()
                # Create a generation config for the message
                generation_config = {
                    "response_mime_type": "text/plain"
                }
                
                # Send the message with standard parameters
                response = chat.send_message(
                    current_query,
                    generation_config=generation_config,
                    stream=False
                )
                
                # Handle function calling for search_web
                response_text = self._process_function_calls(response, chat, current_query)
            
            # Get the response text and handle grounding information
            response_text = response_text
            
            # For now, we'll just use the response text as is
            # In the future, when Google Search retrieval is properly supported in the API version,
            # we can add back the citation handling code
            
            # Add the query and response to chat history
            timestamp = datetime.datetime.now().isoformat()
            
            # For channels, include the user ID, name, and channel ID in the content to track who said what and where
            if is_channel and user_id:
                # Extract channel ID from the format "workspace{id}_channel_{channel_id}"
                channel_id = None
                if "_channel_" in user_id_or_channel:
                    channel_id = user_id_or_channel.split("_channel_")[1]
                
                user_message = {
                    "role": "user", 
                    "content": query,  # Store original query without name prefix
                    "timestamp": timestamp,
                    "user_id": user_id,  # Store the user ID explicitly
                    "user_name": user_name or "Unknown User",  # Store the user name if available
                    "channel_id": channel_id  # Store the channel ID to track where the message was sent
                }
                chat_history.append(user_message)
            else:
                chat_history.append({"role": "user", "content": query, "timestamp": timestamp})
            
            # For channel messages, include the channel ID in the bot response as well
            if is_channel and "_channel_" in user_id_or_channel:
                channel_id = user_id_or_channel.split("_channel_")[1]
                chat_history.append({
                    "role": "bot", 
                    "content": response_text, 
                    "timestamp": timestamp,
                    "channel_id": channel_id  # Store the channel ID for bot responses too
                })
            else:
                chat_history.append({"role": "bot", "content": response_text, "timestamp": timestamp})
            
            # Save the updated chat history
            self.save_chat_history(user_id_or_channel, chat_history)
            
            # Periodically summarize the session and update memory
            if len(chat_history) % 10 == 0:  # Every 10 messages
                try:
                    # Summarize the session and extract important information
                    summary = self.memory[workspace_id].summarize_session(chat_history)
                    
                    # Memory updates are handled in the summarize_session method
                    # No additional processing needed
                        
                except Exception as e:
                    logger.error(f"Error summarizing session: {str(e)}")
            
            return response_text
            
        except Exception as e:
            logger.error(f"[{app_id}] Error generating response: {str(e)}")
            return f"Sorry, I encountered an error: {str(e)}"
    

    
    def _process_function_calls(self, response, chat, original_query):
        """Process function calls in the response"""
        # If we can get the text directly, return it
        try:
            return response.text
        except (AttributeError, TypeError):
            pass
            
        # Check for function calls
        try:
            # Extract parts from the response
            if not hasattr(response, 'candidates') or not response.candidates:
                return "I couldn't generate a response. Please try again."
                
            candidate = response.candidates[0]
            if not hasattr(candidate, 'content') or not candidate.content:
                return "I couldn't generate a response. Please try again."
                
            content = candidate.content
            if not hasattr(content, 'parts') or not content.parts:
                return "I couldn't generate a response. Please try again."
                
            # Process each part
            result_text = ""
            has_function_call = False
            
            for part in content.parts:
                # Extract text if available
                if hasattr(part, 'text') and part.text:
                    result_text += part.text
                
                # Handle function calls
                if hasattr(part, 'function_call'):
                    has_function_call = True
                    function_call = part.function_call
                    
                    if function_call.name == "search_web":
                        try:
                            # Extract search query
                            # Handle different types of args (string or object)
                            try:
                                if isinstance(function_call.args, str):
                                    args = json.loads(function_call.args)
                                    query = args.get("query", original_query)
                                else:
                                    # If args is already an object (MapComposite)
                                    query = getattr(function_call.args, "query", original_query)
                            except Exception as e:
                                logger.error(f"Error parsing function args: {str(e)}")
                                query = original_query
                            
                            logger.info(f"Searching web for: {query}")
                            
                            # Get current date and time for accurate search context
                            current_date = datetime.datetime.now().strftime("%Y-%m-%d")
                            current_day = datetime.datetime.now().strftime("%A")
                            current_time = datetime.datetime.now().strftime("%H:%M:%S")
                            
                            # Create a direct search instruction that forces the model to use its search tool
                            search_prompt = f"""I need you to search the web for current information about: {query}
                            
                            IMPORTANT INSTRUCTIONS:
                            1. You MUST use your search_web function to find this information
                            2. Today's date is {current_date} ({current_day}), and the current time is {current_time}
                            3. Make sure your search results reflect the most up-to-date information available
                            4. DO NOT respond until you have completed the search
                            5. Include specific details from your search results
                            
                            Please execute the search_web function now."""
                            
                            # Force the model to use the search tool by explicitly requesting it
                            search_message = chat.send_message(search_prompt, stream=False)
                            
                            # Check if the search was actually performed
                            search_performed = False
                            if hasattr(search_message, 'candidates') and search_message.candidates:
                                for candidate in search_message.candidates:
                                    if hasattr(candidate, 'content') and candidate.content:
                                        for part in candidate.content.parts:
                                            if hasattr(part, 'function_call') and part.function_call:
                                                search_performed = True
                            
                            # If search wasn't performed in the first attempt, try again with a more direct approach
                            if not search_performed:
                                direct_search_prompt = f"""USE YOUR SEARCH_WEB FUNCTION to find information about: {query}
                                
                                This is EXTREMELY IMPORTANT. You MUST use your search_web function.
                                Do not respond with anything except the search results.
                                
                                Function name: search_web
                                Parameter: query = \"{query}\"
                                
                                Execute this function now."""
                                
                                search_message = chat.send_message(direct_search_prompt, stream=False)
                            
                            # Now ask for a comprehensive response based on the search results
                            follow_up_prompt = f"""Based on your search about '{query}', provide a detailed response with the information you found.
                            
                            IMPORTANT:
                            1. Today's date is {current_date} ({current_day})
                            2. Include specific facts and details from your search results
                            3. If you didn't find any information, explicitly state that you couldn't find information about {query}
                            4. Format your response in a conversational, helpful way
                            
                            What did you find about '{query}'?"""
                            
                            # Get the final response
                            follow_up = chat.send_message(follow_up_prompt, stream=False)
                            
                            # Return the follow-up response
                            try:
                                return follow_up.text
                            except (AttributeError, TypeError):
                                # If we can't get text directly, try to extract it from parts
                                follow_up_text = ""
                                for follow_part in follow_up.candidates[0].content.parts:
                                    if hasattr(follow_part, 'text') and follow_part.text:
                                        follow_up_text += follow_part.text
                                return follow_up_text if follow_up_text else "I found some information, but couldn't process it properly."
                                
                        except Exception as e:
                            logger.error(f"Error processing search_web function: {str(e)}")
                            return f"I tried to search for information about '{original_query}', but encountered an error. {result_text}"
            
            # If there was a function call but we didn't return from it, return a default message
            if has_function_call:
                return "I need to search for more information to answer your question accurately, but I'm currently unable to perform web searches."
                
            # If there was no function call but we have some text, return it
            if result_text:
                return result_text
                
            # Default response if we couldn't extract anything
            return "I couldn't generate a response. Please try again."
            
        except Exception as e:
            logger.error(f"Error processing function calls: {str(e)}")
            return f"I encountered an error while processing your request. Please try again."
    

    
    def run(self, host='0.0.0.0', port=3000):
        """Run the Flask app"""
        self.flask_app.run(host=host, port=port)

# Create and run the bot manager
if __name__ == "__main__":
    bot_manager = SlackBotManager()
    bot_manager.run()
