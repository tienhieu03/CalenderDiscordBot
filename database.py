from pymongo import MongoClient
from config import MONGODB_URI
from utils.encryption import EncryptionManager

class DatabaseManager:
    def __init__(self):
        self.client = MongoClient(MONGODB_URI)
        self.db = self.client.calendar_bot
        self.events = self.db.events
        self.user_settings = self.db.user_settings
        self.encryption = EncryptionManager()

    def save_event(self, event_id, title, datetime_str, description, user_id=None):
        """Lưu sự kiện với thông tin người tạo"""
        return self.events.update_one(
            {'event_id': event_id},
            {
                '$set': {
                    'title': title,
                    'datetime': datetime_str,
                    'description': description,
                    'created_by': user_id
                }
            },
            upsert=True
        )

    def delete_event(self, event_id):
        return self.events.delete_one({'event_id': event_id})

    def get_event(self, event_id):
        return self.events.find_one({'event_id': event_id})

    def get_event_creator(self, event_id):
        """Lấy ID người tạo sự kiện"""
        event = self.events.find_one({'event_id': event_id})
        return event.get('created_by') if event else None

    def save_user_calendar(self, user_id: str, calendar_id: str):
        """Lưu Calendar ID đã mã hóa cho user"""
        encrypted_id = self.encryption.encrypt(calendar_id)
        return self.user_settings.update_one(
            {'user_id': user_id},
            {'$set': {'calendar_id': encrypted_id}},
            upsert=True
        )

    def get_user_calendar(self, user_id: str) -> str:
        """Lấy và giải mã Calendar ID của user"""
        setting = self.user_settings.find_one({'user_id': user_id})
        if setting and setting.get('calendar_id'):
            return self.encryption.decrypt(setting['calendar_id'])
        return None

    def delete_user_calendar(self, user_id: str):
        """Xóa Calendar ID của user"""
        return self.user_settings.delete_one({'user_id': user_id})
