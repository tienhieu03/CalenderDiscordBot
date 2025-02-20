from pymongo import MongoClient
from config import MONGODB_URI

class DatabaseManager:
    def __init__(self):
        self.client = MongoClient(MONGODB_URI)
        self.db = self.client.calendar_bot
        self.events = self.db.events

    async def save_event(self, event_id, title, datetime_str, description, user_id=None):
        """Lưu sự kiện với thông tin người tạo"""
        return self.events.update_one(
            {'event_id': event_id},
            {
                '$set': {
                    'title': title,
                    'datetime': datetime_str,
                    'description': description,
                    'created_by': user_id  # Thêm user_id vào database
                }
            },
            upsert=True
        )

    async def delete_event(self, event_id):
        return self.events.delete_one({'event_id': event_id})

    async def get_event(self, event_id):
        return self.events.find_one({'event_id': event_id})

    async def get_event_creator(self, event_id):
        """Lấy ID người tạo sự kiện"""
        event = await self.get_event(event_id)
        return event.get('created_by') if event else None
