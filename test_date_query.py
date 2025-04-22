import os
import json
import logging
import datetime
import google.generativeai as genai
from flat_memory_manager import FlatMemoryManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Gemini API
genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))

# Constants
MEMORY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory")

def test_date_query():
    """Test the bot's response to a date query with Google Search enabled"""
    # Set up the model with Google Search enabled
    safety_settings = {
        "HARM_CATEGORY_HARASSMENT": "BLOCK_NONE",
        "HARM_CATEGORY_HATE_SPEECH": "BLOCK_NONE",
        "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_NONE",
        "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_NONE",
    }
    
    system_instruction = "Keep your responses simple, short, and conversational like a Slack chat. Avoid lengthy explanations. Be direct and concise. Use Google Search to find current information when needed."
    
    # Initialize the model with Google Search as a tool
    # For Gemini 2.5, we need to define function declarations for search
    search_tool = {
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
    
    model = genai.GenerativeModel(
        'gemini-2.5-flash-preview-04-17',
        system_instruction=system_instruction,
        safety_settings=safety_settings,
        generation_config={
            "temperature": 0.7,
            "top_p": 0.95,
            "top_k": 40
        },
        tools=[{"function_declarations": [search_tool]}]  # Enable Google Search as a tool
    )
    
    # Initialize memory manager to get context
    memory_manager = FlatMemoryManager(MEMORY_DIR, "workspace1")
    memory_context = memory_manager.get_context_for_user()
    
    # Create a chat session
    chat = model.start_chat()
    
    # Add memory context as system message
    if memory_context.strip():
        chat.send_message(
            f"I have access to the following important information that I should remember:\n\n{memory_context}",
            stream=False
        )
    
    # Simulate a user asking what date it is today
    query = "오늘 날짜가 뭐야?"
    
    print(f"\n--- Testing query: '{query}' ---\n")
    
    # Send the query
    response = chat.send_message(
        query,
        generation_config={
            "response_mime_type": "text/plain"
        },
        stream=False
    )
    
    # Print the response
    print(f"Bot response: {response.text}\n")
    
    # Try another date-related query to see if Google Search is used
    query = "What is today's date and day of the week?"
    
    print(f"\n--- Testing query: '{query}' ---\n")
    
    # Send the query
    response = chat.send_message(
        query,
        generation_config={
            "response_mime_type": "text/plain"
        },
        stream=False
    )
    
    # Print the response
    print(f"Bot response: {response.text}\n")
    
    # Try a query that explicitly asks for a web search
    query = "Please search the web and tell me what date it is today"
    
    print(f"\n--- Testing query: '{query}' ---\n")
    
    # Send the query
    response = chat.send_message(
        query,
        generation_config={
            "response_mime_type": "text/plain"
        },
        stream=False
    )
    
    # Print the response
    print(f"Bot response: {response.text}\n")

if __name__ == "__main__":
    test_date_query()
