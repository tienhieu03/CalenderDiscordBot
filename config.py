import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
MONGODB_URI = os.getenv('MONGODB_URI')
CALENDAR_ID = os.getenv('CALENDAR_ID', 'primary')  # Sử dụng 'primary' làm giá trị mặc định
GOOGLE_CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), 'credentials.json')
SCOPES = ['https://www.googleapis.com/auth/calendar']
COMMAND_PREFIX = ['B!', 'b!']
