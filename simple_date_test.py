import os
import google.generativeai as genai
import json

# Configure Gemini API
api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    print("Error: GOOGLE_API_KEY environment variable not set")
    exit(1)

genai.configure(api_key=api_key)

def test_date_query():
    """Test a simple date query with the Gemini model"""
    print("Testing date query with Gemini 2.5...")
    
    # Define a function declaration for web search
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
    
    # Initialize the model
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash-preview-04-17",
        system_instruction="You are a helpful assistant. When asked about current information like dates, news, or events, use search to find the most up-to-date information.",
        tools=[{"function_declarations": [search_function]}]
    )
    
    # Create a chat session
    chat = model.start_chat()
    
    # Test queries
    queries = [
        "오늘 날짜가 뭐야?",
        "What is today's date?",
        "Please search the web and tell me what day of the week it is today"
    ]
    
    for query in queries:
        print(f"\n--- Testing query: '{query}' ---")
        
        try:
            # Send the query
            response = chat.send_message(query)
            
            # Print the response
            print("\nResponse:")
            
            # Handle different response formats
            try:
                # Try to get text directly
                print(response.text)
            except (AttributeError, TypeError):
                # If that fails, try to extract text from parts
                try:
                    for part in response.parts:
                        if hasattr(part, 'text') and part.text:
                            print(part.text)
                        elif hasattr(part, 'function_call'):
                            print(f"Function call: {part.function_call.name}")
                            print(f"Arguments: {part.function_call.args}")
                except Exception as e:
                    print(f"Error extracting parts: {str(e)}")
                    print("Raw response:", response)
            
        except Exception as e:
            print(f"Error: {str(e)}")
    
    print("\nTest completed.")

if __name__ == "__main__":
    test_date_query()
