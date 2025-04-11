import os
import sys
import json
import datetime
from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables
load_dotenv()

# Get API key from environment variables
api_key = os.environ.get("GOOGLE_API_KEY")

# Configure Gemini API
if not api_key:
    raise ValueError("API key not found in environment variables. Please check your .env file.")

genai.configure(api_key=api_key)

# Initialize the model with the experimental version of Gemini 2.5 Pro
model = genai.GenerativeModel('gemini-2.5-pro-exp-03-25')

# Create sessions directory if it doesn't exist
SESSIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sessions")
os.makedirs(SESSIONS_DIR, exist_ok=True)

def get_session_file(user_id):
    """Get the path to the session file for a user"""
    return os.path.join(SESSIONS_DIR, f"{user_id}.json")

def load_chat_history(user_id):
    """Load chat history for a user from their session file"""
    session_file = get_session_file(user_id)
    if os.path.exists(session_file):
        try:
            with open(session_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading chat history for user {user_id}: {str(e)}")
    return []

def save_chat_history(user_id, chat_history):
    """Save chat history for a user to their session file"""
    session_file = get_session_file(user_id)
    try:
        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump(chat_history, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving chat history for user {user_id}: {str(e)}")

def chat_with_gemini():
    """Simple interactive chat with Gemini"""
    print("\n===== Slack Chatbot with Gemini 2.5 Pro Demo =====")
    print("Type 'exit' to quit the demo")
    print("Type 'clear' to clear chat history")
    print("================================================\n")
    
    # Set a default user ID for the demo
    user_id = "demo_user"
    print(f"Using user ID: {user_id}")
    
    # Load existing chat history
    chat_history = load_chat_history(user_id)
    if chat_history:
        print(f"Loaded existing chat history with {len(chat_history) // 2} previous exchanges.")
    
    # Test connection first
    try:
        test_response = model.generate_content("Hello")
        print(f"Connection test successful. Ready to chat!\n")
    except Exception as e:
        print(f"Error connecting to Gemini API: {str(e)}")
        return
    
    # Main chat loop
    try:
        while True:
            # Get user input with error handling
            try:
                user_input = input("You: ")
            except (EOFError, KeyboardInterrupt):
                print("\nExiting chat...")
                break
                
            # Check if user wants to exit
            if not user_input or user_input.lower() in ['exit', 'quit', 'bye']:
                print("\nThank you for using the Gemini Slack Bot demo!")
                break
            
            # Check if user wants to clear history
            if user_input.lower() == 'clear':
                chat_history = []
                save_chat_history(user_id, chat_history)
                print("\nChat history cleared.\n")
                continue
            
            try:
                # Format chat history for Gemini
                formatted_history = []
                for entry in chat_history[-10:]:  # Use last 10 messages to avoid context limits
                    formatted_history.append({
                        "role": "user" if entry["role"] == "user" else "model",
                        "parts": [entry["content"]]
                    })
                
                # Generate response
                if formatted_history:
                    # Continue the conversation
                    chat = model.start_chat(history=formatted_history)
                    response = chat.send_message(user_input)
                else:
                    # Start a new conversation
                    response = model.generate_content(user_input)
                
                bot_response = response.text
                
                # Print bot response
                print(f"\nBot: {bot_response}\n")
                
                # Add to chat history
                timestamp = datetime.datetime.now().isoformat()
                chat_history.append({"role": "user", "content": user_input, "timestamp": timestamp})
                chat_history.append({"role": "bot", "content": bot_response, "timestamp": timestamp})
                
                # Save the updated chat history
                save_chat_history(user_id, chat_history)
                
            except Exception as e:
                print(f"\nError: {str(e)}")
                print("Please try again with a different query.")
    except Exception as e:
        print(f"\nUnexpected error: {str(e)}")

if __name__ == "__main__":
    try:
        chat_with_gemini()
    except Exception as e:
        print(f"Failed to initialize: {str(e)}")
        print("Please check your API key and internet connection.")
