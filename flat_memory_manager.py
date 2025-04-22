import os
import json
import logging
import datetime
import google.generativeai as genai
from typing import Dict, List, Any, Optional

# Configure logging
logger = logging.getLogger(__name__)

class FlatMemoryManager:
    """Simplified manager class to handle memory for workspace1 in a single flat list"""
    
    def __init__(self, memory_dir: str, workspace_id: str = "workspace1"):
        """Initialize the memory manager
        
        Args:
            memory_dir: Directory to store memory files
            workspace_id: ID of the workspace to manage memory for
        """
        self.memory_dir = memory_dir
        self.workspace_id = workspace_id
        os.makedirs(memory_dir, exist_ok=True)
        
        # Memory file path
        self.memory_file = os.path.join(memory_dir, f"{workspace_id}_memory.json")
        
        # Initialize memory structure
        self.memory = self._load_memory()
        
        # Initialize Gemini model for memory processing
        try:
            self.memory_model = genai.GenerativeModel('gemini-2.5-flash-preview-04-17')
        except Exception as e:
            logging.error(f"Error initializing Gemini model: {str(e)}")
            self.memory_model = None
    
    def _load_memory(self) -> Dict:
        """Load memory from file
        
        Returns:
            Dictionary containing the memory data
        """
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logging.error(f"Error loading memory from {self.memory_file}: {str(e)}")
        
        # Return default memory structure if file doesn't exist or there's an error
        return {
            "memory": []
        }
    
    def _save_memory(self):
        """Save memory to file"""
        try:
            with open(self.memory_file, 'w', encoding='utf-8') as f:
                json.dump(self.memory, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logging.error(f"Error saving memory to {self.memory_file}: {str(e)}")
            
    def _append_memory_item(self, memory_item):
        """Append a single memory item to the file without updating the entire file
        
        Args:
            memory_item: Memory item to append
        """
        try:
            # First, check if the memory item already exists in the file
            if os.path.exists(self.memory_file):
                with open(self.memory_file, 'r', encoding='utf-8') as f:
                    current_memory = json.load(f)
                    if "memory" in current_memory and memory_item in current_memory["memory"]:
                        # Memory item already exists, no need to append
                        return
            
            # Update the in-memory representation
            if "memory" not in self.memory:
                self.memory["memory"] = []
            if memory_item not in self.memory["memory"]:
                self.memory["memory"].append(memory_item)
            
            # Append to the file
            with open(self.memory_file, 'r+', encoding='utf-8') as f:
                try:
                    current_memory = json.load(f)
                    if "memory" not in current_memory:
                        current_memory["memory"] = []
                    
                    # Only append if it doesn't already exist
                    if memory_item not in current_memory["memory"]:
                        current_memory["memory"].append(memory_item)
                        
                        # Move file pointer to beginning and truncate
                        f.seek(0)
                        f.truncate()
                        
                        # Write the updated memory
                        json.dump(current_memory, f, indent=2, ensure_ascii=False)
                except json.JSONDecodeError:
                    # File might be empty or invalid, write the full memory
                    f.seek(0)
                    f.truncate()
                    json.dump(self.memory, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logging.error(f"Error appending memory item to {self.memory_file}: {str(e)}")
    
    def add_memory(self, memory_item: str):
        """Add a memory item to the list
        
        Args:
            memory_item: Memory item to add
        """
        # Use the append method to only update the file if there's a new memory item
        self._append_memory_item(memory_item)
    
    def get_memory(self) -> List[str]:
        """Get all memory items
        
        Returns:
            List of memory items
        """
        return self.memory.get("memory", [])
    
    def extract_important_info(self, message: Dict) -> List[str]:
        """Extract important information from a single chat message using Gemini API
        
        Args:
            message: A single chat message
            
        Returns:
            List of extracted important information
        """
        # If Gemini model is not available, return empty list
        if not self.memory_model or message.get("role") != "user":
            return []
        
        try:
            # Get the content of the current message
            content = message.get("content", "")
            user_name = message.get("user_name", "User")
            
            # Only process messages with meaningful content
            if len(content.strip()) < 10:  # Skip very short messages
                return []
            
            # Ask Gemini to extract important information as natural language
            memory_prompt = f"""Below is a message from a user. If this message contains any important information worth remembering long-term, extract it.
            Important information could be about people, organizations, preferences, facts, or any other significant information.
            If there's nothing worth remembering, return NOTHING.
            If there is something worth remembering, write each memory as a complete, natural language sentence. Be concise but informative.
            Return ONLY the memories, one per line, with no prefixes or categorization.
            
            USER MESSAGE:
            {user_name}: {content}
            
            IMPORTANT INFORMATION (or NOTHING if none):"""
            
            memory_response = self.memory_model.generate_content(memory_prompt)
            if memory_response and memory_response.text:
                text = memory_response.text.strip()
                if text.lower() == "nothing" or "nothing worth remembering" in text.lower():
                    return []
                    
                memories = [memory.strip() for memory in text.split("\n") if memory.strip() and memory.lower() != "nothing"]
                return memories
            
        except Exception as e:
            logger.error(f"Error extracting information with Gemini: {str(e)}")
        
        return []
    
    def summarize_session(self, chat_history: List[Dict]) -> Dict[str, Any]:
        """Summarize a chat session to extract important information using Gemini API
        
        Args:
            chat_history: List of chat messages
            
        Returns:
            Dictionary containing extracted information
        """
        summary = {
            "user_info": {},
            "memories": [],
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        # Extract user information from chat history
        for message in chat_history:
            if message.get("role") == "user" and message.get("user_id") and message.get("user_name"):
                user_id = message.get("user_id")
                if user_id not in summary["user_info"]:
                    summary["user_info"][user_id] = {
                        "name": message.get("user_name"),
                        "last_active": message.get("timestamp")
                    }
                    # Remember user name
                    self.add_memory(f"User {user_id}: {message.get('user_name')}")
        
        # Consolidate full chat history and extract important information
        history_text = "\n".join(
            f"{entry.get('user_name', 'Bot')}: {entry.get('content', '')}"
            for entry in chat_history
        )
        if history_text.strip():
            synthetic_message = {
                "role": "user",
                "content": history_text,
                "user_name": "History"
            }
            memories = self.extract_important_info(synthetic_message)
            summary["memories"] = memories
            for memory in memories:
                self.add_memory(memory)
        return summary
    
    def get_context_for_user(self, user_id: str = None) -> str:
        """Get memory context for a specific user or general context
        
        Args:
            user_id: Optional ID of the user
            
        Returns:
            String containing relevant memory context
        """
        memory_items = self.get_memory()
        
        # Limit to a reasonable number of items (max 20)
        if len(memory_items) > 20:
            memory_items = memory_items[:20]
        
        return "\n".join(memory_items)
