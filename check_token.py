import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get the token
token = os.environ.get("SLACK_BOT_TOKEN", "")
print(f"Token length: {len(token)}")
print(f"Token starts with: {token[:10]}..." if token else "No token found")
