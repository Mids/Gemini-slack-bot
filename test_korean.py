import os
import json
from datetime import datetime

# Create sessions directory if it doesn't exist
os.makedirs("sessions", exist_ok=True)

# Test Korean text
test_user_id = "test_user"
korean_text = "안녕하세요! 반갑습니다. 한글 저장 테스트입니다."

# Create a test chat history
chat_history = [
    {
        "role": "user",
        "content": korean_text,
        "timestamp": datetime.now().isoformat()
    },
    {
        "role": "bot",
        "content": "한글 응답 테스트: 네, 안녕하세요! 😊",
        "timestamp": datetime.now().isoformat()
    }
]

# Save to file with ensure_ascii=False to preserve Korean characters
session_file = f"sessions/{test_user_id}.json"
try:
    with open(session_file, 'w', encoding='utf-8') as f:
        json.dump(chat_history, f, indent=2, ensure_ascii=False)
    print(f"Successfully saved Korean text to {session_file}")
    print("Please check the file to verify Korean characters are saved correctly.")
except Exception as e:
    print(f"Error: {str(e)}")
