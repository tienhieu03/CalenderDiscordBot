from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import pickle
import os
import asyncio
from datetime import datetime
from config import SCOPES, GOOGLE_CREDENTIALS_FILE
from aiohttp import ClientSession

class CalendarManager:
    def __init__(self):
        self.services = {}
        self.auth_locks = {}  # Thêm locks để tránh race condition

    async def authenticate(self, user_id: str):
        """Xác thực không đồng bộ cho từng user"""
        try:
            # Sử dụng lock để tránh nhiều request cùng lúc
            if user_id not in self.auth_locks:
                self.auth_locks[user_id] = asyncio.Lock()
            
            async with self.auth_locks[user_id]:
                creds = None
                token_path = f'tokens/token_{user_id}.pickle'
                os.makedirs('tokens', exist_ok=True)

                if os.path.exists(token_path):
                    with open(token_path, 'rb') as token:
                        creds = pickle.load(token)

                if not creds or not creds.valid:
                    if creds and creds.expired and creds.refresh_token:
                        await asyncio.get_event_loop().run_in_executor(
                            None, creds.refresh, Request()
                        )
                    else:
                        flow = InstalledAppFlow.from_client_secrets_file(
                            GOOGLE_CREDENTIALS_FILE, 
                            SCOPES,
                            redirect_uri='urn:ietf:wg:oauth:2.0:oob'  # Sử dụng OOB flow
                        )
                        
                        # Lấy URL xác thực
                        auth_url = flow.authorization_url()[0]
                        
                        # Ném exception với URL xác thực
                        raise Exception(
                            f"🔑 Vui lòng xác thực Google Calendar bằng cách:\n"
                            f"1. Truy cập link: {auth_url}\n"
                            f"2. Đăng nhập và cho phép quyền truy cập\n"
                            f"3. Sao chép mã xác thực\n"
                            f"4. Sử dụng lệnh: `B!auth <mã xác thực>`"
                        )

                    with open(token_path, 'wb') as token:
                        pickle.dump(creds, token)

                service = build('calendar', 'v3', credentials=creds)
                self.services[user_id] = service
                return True

        except Exception as e:
            print(f"Lỗi xác thực cho user {user_id}: {str(e)}")
            raise  # Re-raise exception để bot có thể hiển thị hướng dẫn

    async def verify_auth_code(self, user_id: str, auth_code: str):
        """Xác minh mã xác thực từ user"""
        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                GOOGLE_CREDENTIALS_FILE,
                SCOPES,
                redirect_uri='urn:ietf:wg:oauth:2.0:oob'
            )
            
            # Đổi auth code lấy credentials
            flow.fetch_token(code=auth_code)
            creds = flow.credentials

            # Lưu credentials
            token_path = f'tokens/token_{user_id}.pickle'
            with open(token_path, 'wb') as token:
                pickle.dump(creds, token)

            # Tạo service mới
            service = build('calendar', 'v3', credentials=creds)
            self.services[user_id] = service
            
            return True

        except Exception as e:
            print(f"Lỗi xác minh mã xác thực: {str(e)}")
            return False

    async def get_service(self, user_id: str):
        """Lấy service cho user một cách không đồng bộ"""
        if user_id not in self.services:
            if not await self.authenticate(user_id):
                return None
        return self.services.get(user_id)

    async def add_event(self, title, datetime_str, description, user_id: str, calendar_id='primary'):
        """Thêm sự kiện với xác thực theo user"""
        try:
            service = await self.get_service(user_id)
            if not service:
                raise Exception("Chưa xác thực Google Calendar")

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
            
            event = await asyncio.get_event_loop().run_in_executor(
                None, service.events().insert(calendarId=calendar_id, body=event).execute
            )
            return event['id']
            
        except Exception as e:
            print(f"Error adding event: {e}")
            return None

    async def delete_event(self, event_id, user_id: str, calendar_id='primary'):
        """Xóa sự kiện với xác thực theo user"""
        try:
            service = await self.get_service(user_id)
            if not service:
                raise Exception("Chưa xác thực Google Calendar")

            await asyncio.get_event_loop().run_in_executor(
                None, service.events().delete(calendarId=calendar_id, eventId=event_id).execute
            )
            return True
        except Exception as e:
            print(f"Error deleting event: {e}")
            return False

    async def list_events(self, user_id: str, calendar_id='primary'):
        """Liệt kê sự kiện với xác thực theo user"""
        try:
            service = await self.get_service(user_id)
            if not service:
                raise Exception("Chưa xác thực Google Calendar")

            now = datetime.utcnow().isoformat() + 'Z'
            events_result = await asyncio.get_event_loop().run_in_executor(
                None, service.events().list(
                    calendarId=calendar_id,
                    timeMin=now,
                    maxResults=10,
                    singleEvents=True,
                    orderBy='startTime'
                ).execute
            )
            return events_result.get('items', [])
        except Exception as e:
            print(f"Error listing events: {e}")
            return []
