import os
import json
import logging
import datetime
import google.generativeai as genai
from flat_memory_manager import FlatMemoryManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
MEMORY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory")
SESSIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sessions")

def load_session(file_path):
    """Load a session file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading session file {file_path}: {str(e)}")
        return []

def summarize_session_file(workspace_id="workspace1"):
    """Summarize the session file and extract important information as natural language
    
    Args:
        workspace_id: ID of the workspace to summarize
    """
    # Initialize the flat memory manager
    memory_manager = FlatMemoryManager(MEMORY_DIR, workspace_id)
    
    # Get the session file path
    session_file = os.path.join(SESSIONS_DIR, f"{workspace_id}.json")
    
    if not os.path.exists(session_file):
        logger.error(f"Session file not found: {session_file}")
        return
    
    # Load the session data
    session_data = load_session(session_file)
    
    if not session_data:
        logger.error(f"No data found in session file: {session_file}")
        return
    
    # Initialize Gemini model for summarization
    try:
        model = genai.GenerativeModel('gemini-2.5-flash-preview-04-17')
    except Exception as e:
        logger.error(f"Error initializing Gemini model: {str(e)}")
        return
    
    # Format conversation for analysis
    conversation_text = "\n\n".join([
        f"{msg.get('user_name', 'Bot') if msg.get('role') == 'user' else 'Bot'}: {msg.get('content', '')}" 
        for msg in session_data[-50:]  # Use last 50 messages
    ])
    
    # Extract user information from the session data
    for message in session_data:
        if message.get("role") == "user" and message.get("user_id") and message.get("user_name"):
            user_id = message.get("user_id")
            user_name = message.get("user_name")
            memory_manager.add_memory(f"User {user_id}: {user_name}")
    
    # Extract important memories as natural language
    extract_memories(model, conversation_text, memory_manager)
    
    logger.info(f"Session summarization completed for {workspace_id}")

def extract_memories(model, conversation_text, memory_manager):
    """Extract important memories from conversation as natural language"""
    try:
        # Create a prompt that asks for important information as natural language
        memories_prompt = f"""Below is a conversation. Extract 10-15 important pieces of information that are worth remembering long-term.
        These could be about people, organizations, preferences, facts, or any other significant information.
        Write each memory as a complete, natural language sentence. Be concise but informative.
        Do not categorize or label the memories - just write them as plain text.
        
        CONVERSATION:
        {conversation_text}
        
        IMPORTANT MEMORIES:"""
        
        memories_response = model.generate_content(memories_prompt)
        if memories_response and memories_response.text and memories_response.text.lower() != "none":
            memories = [memory.strip() for memory in memories_response.text.split("\n") if memory.strip()]
            for memory in memories:
                memory_manager.add_memory(memory)
    except Exception as e:
        logger.error(f"Error extracting memories: {str(e)}")

def summarize_all_sessions():
    """Summarize all session files in the sessions directory"""
    if not os.path.exists(SESSIONS_DIR):
        logger.error(f"Sessions directory not found: {SESSIONS_DIR}")
        return
    
    # Get all session files
    session_files = [f for f in os.listdir(SESSIONS_DIR) if f.endswith('.json')]
    
    for session_file in session_files:
        # Extract workspace ID from filename
        workspace_id = session_file.split('.')[0]
        summarize_session_file(workspace_id)

if __name__ == "__main__":
    # If a workspace ID is provided as an argument, summarize only that workspace
    import sys
    if len(sys.argv) > 1:
        summarize_session_file(sys.argv[1])
    else:
        # Otherwise summarize all workspaces
        summarize_all_sessions()
