from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import pickle
import os
from datetime import datetime
from config import SCOPES, GOOGLE_CREDENTIALS_FILE, CALENDAR_ID

class CalendarManager:
    def __init__(self):
        self.creds = None
        self.service = None
        self.authenticate()

    def authenticate(self):
        try:
            # Kiểm tra và sử dụng token đã lưu
            if os.path.exists('token.pickle'):
                with open('token.pickle', 'rb') as token:
                    self.creds = pickle.load(token)

            # Nếu không có token hoặc token hết hạn
            if not self.creds or not self.creds.valid:
                # Nếu token hết hạn và có refresh token
                if self.creds and self.creds.expired and self.creds.refresh_token:
                    print("Token hết hạn, đang làm mới...")
                    self.creds.refresh(Request())
                else:
                    print("Đang yêu cầu xác thực mới...")
                    if not os.path.exists(GOOGLE_CREDENTIALS_FILE):
                        raise FileNotFoundError(
                            f"credentials.json không tồn tại tại đường dẫn: {GOOGLE_CREDENTIALS_FILE}"
                        )
                    
                    flow = InstalledAppFlow.from_client_secrets_file(
                        GOOGLE_CREDENTIALS_FILE, 
                        SCOPES,
                        redirect_uri='http://localhost:8080/'
                    )
                    
                    self.creds = flow.run_local_server(
                        port=8080,
                        success_message='Xác thực thành công! Bạn có thể đóng tab này.',
                        open_browser=True
                    )
                
                # Lưu hoặc cập nhật token
                with open('token.pickle', 'wb') as token:
                    pickle.dump(self.creds, token)
                    print("Đã lưu token mới")

            self.service = build('calendar', 'v3', credentials=self.creds)
            print("✓ Kết nối Google Calendar thành công!")
            
        except Exception as e:
            print(f"Lỗi xác thực Google Calendar: {str(e)}")
            raise

    async def add_event(self, title, datetime_str, description):
        try:
            event_datetime = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M')
            event = {
                'summary': title,
                'description': description,
                'start': {
                    'dateTime': event_datetime.isoformat(),
                    'timeZone': 'Asia/Ho_Chi_Minh',
                },
                'end': {
                    'dateTime': event_datetime.isoformat(),
                    'timeZone': 'Asia/Ho_Chi_Minh',
                }
            }
            
            event = self.service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
            return event['id']
        except Exception as e:
            print(f"Error adding event: {e}")
            return None

    async def delete_event(self, event_id):
        try:
            self.service.events().delete(calendarId=CALENDAR_ID, eventId=event_id).execute()
            return True
        except Exception as e:
            print(f"Error deleting event: {e}")
            return False

    async def list_events(self):
        try:
            now = datetime.utcnow().isoformat() + 'Z'
            events_result = self.service.events().list(
                calendarId=CALENDAR_ID, timeMin=now,
                maxResults=10, singleEvents=True,
                orderBy='startTime').execute()
            return events_result.get('items', [])
        except Exception as e:
            print(f"Error listing events: {e}")
            return []
