import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
MONGODB_URI = os.getenv('MONGODB_URI')
# Sử dụng đường dẫn tuyệt đối đến file credentials.json
GOOGLE_CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), 'credentials.json')
SCOPES = ['https://www.googleapis.com/auth/calendar']
CALENDAR_ID = os.getenv('CALENDAR_ID')
COMMAND_PREFIX = ['B!', 'b!']  # Thay đổi từ string thành list
