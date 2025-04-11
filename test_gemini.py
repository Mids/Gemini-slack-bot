import os
import google.generativeai as genai

# Get API key from environment variable
api_key = os.environ.get("GOOGLE_API_KEY")

# Configure Gemini API
if not api_key:
    raise ValueError("API key not found in environment variables. Please set GOOGLE_API_KEY.")

genai.configure(api_key=api_key)

# List available models to find the correct one
def list_available_models():
    try:
        models = genai.list_models()
        print("Available models:")
        for model in models:
            print(f"- {model.name}")
        return models
    except Exception as e:
        print(f"Error listing models: {str(e)}")
        return []

def test_gemini(model_name):
    """Test the Gemini API with a simple prompt"""
    try:
        # Initialize the model with the provided name
        model = genai.GenerativeModel(model_name)
        
        # Simple test prompt
        prompt = "Hello! Please give me a brief introduction about yourself in 2-3 sentences."
        
        # Generate response
        response = model.generate_content(prompt)
        
        # Print response
        print("\nGemini API Test Result:")
        print("-----------------------")
        print(f"Model: {model_name}")
        print(f"Prompt: {prompt}")
        print(f"Response: {response.text}")
        print("-----------------------")
        print("Gemini API connection successful!")
        return True
        
    except Exception as e:
        print(f"\nTest with model '{model_name}' failed:")
        print(f"Error: {str(e)}")
        return False

if __name__ == "__main__":
    # First list all available models
    print("Listing available models...")
    models = list_available_models()
    
    # Try with the experimental version of Gemini 2.5 Pro and fallbacks
    model_names = ["gemini-2.5-pro-exp-03-25"]
    
    success = False
    for model_name in model_names:
        print(f"\nTrying with model: {model_name}")
        if test_gemini(model_name):
            success = True
            break
    
    if not success:
        print("\nFailed to connect with any of the known models.")
        print("Please check your API key and internet connection.")
