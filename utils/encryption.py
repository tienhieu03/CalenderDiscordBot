from cryptography.fernet import Fernet
import base64
import os
from pathlib import Path

class EncryptionManager:
    def __init__(self):
        self.key_file = Path(__file__).parent.parent / '.encryption_key'
        self.key = self._load_or_create_key()
        self.fernet = Fernet(self.key)

    def _load_or_create_key(self):
        if self.key_file.exists():
            return self.key_file.read_bytes()
        else:
            key = Fernet.generate_key()
            self.key_file.write_bytes(key)
            return key

    def encrypt(self, text: str) -> str:
        """Mã hóa chuỗi văn bản"""
        if not text:
            return text
        encrypted = self.fernet.encrypt(text.encode())
        return base64.urlsafe_b64encode(encrypted).decode()

    def decrypt(self, encrypted_text: str) -> str:
        """Giải mã chuỗi đã mã hóa"""
        if not encrypted_text:
            return encrypted_text
        try:
            decoded = base64.urlsafe_b64decode(encrypted_text.encode())
            decrypted = self.fernet.decrypt(decoded)
            return decrypted.decode()
        except Exception as e:
            print(f"Lỗi giải mã: {e}")
            return None
