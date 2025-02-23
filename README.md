# Discord Calendar Bot

Bot Discord hỗ trợ quản lý sự kiện thông qua Google Calendar với các tính năng nhắc nhở tự động.

## 🌟 Tính năng chính

- Thêm/Xóa/Xem sự kiện trong Google Calendar
- Nhắc nhở tự động qua Discord (DM hoặc channel)
- Hỗ trợ nhiều lần nhắc cho mỗi sự kiện
- Mã hóa thông tin calendar của người dùng
- Prefix linh hoạt (B! hoặc b!)
- Tự động dọn dẹp sự kiện đã kết thúc

## 📋 Yêu cầu

- Python 3.8 trở lên
- MongoDB
- Google Calendar API credentials
- Discord Bot Token

## 🚀 Cài đặt

1. Clone repository và cài đặt dependencies:

```bash
git clone <repository-url>
cd CalenderDiscordBot
pip install -r requirements.txt
```

2. Tạo file `.env` với nội dung:

```
DISCORD_TOKEN=your_discord_bot_token
MONGODB_URI=your_mongodb_uri
CALENDAR_ID=your_default_calendar_id
```

3. Cấu hình Google Calendar API:

- Tạo project trên Google Cloud Console
- Bật Google Calendar API
- Tải credentials.json và đặt vào thư mục gốc của bot
- Chạy bot lần đầu và xác thực qua trình duyệt

4. Khởi động bot:

```bash
python bot.py
```

## 📝 Lệnh cơ bản

Bot hỗ trợ prefix B! hoặc b!

- `B!add <tiêu đề> <dd/mm/yyyy HH:MM> [mô tả]` - Thêm sự kiện mới
- `B!list` - Xem danh sách sự kiện
- `B!del` - Xóa sự kiện (có menu chọn)
- `B!test` - Tạo sự kiện test
- `B!setcalendar <calendar_id>` - Cài đặt Calendar ID
- `B!mycalendar` - Xem Calendar ID hiện tại
- `B!helps` - Xem hướng dẫn đầy đủ

## ⚙️ Cấu hình nâng cao

### Thay đổi múi giờ

Trong file `scheduler.py`, tìm và sửa:

```python
timezone=timezone('Asia/Ho_Chi_Minh')
```

### Tùy chỉnh thời gian nhắc nhở

Trong file `bot.py`, tìm class `ReminderSelectView` và sửa:

```python
self.remind_options = [
    ("Vào lúc diễn ra", 0, "⏰"),
    // Thêm các tùy chọn khác
]
```

## 🔒 Bảo mật

- Calendar ID được mã hóa trước khi lưu vào database
- Chỉ admin có quyền thêm/xóa sự kiện
- Token và credentials được lưu riêng trong file .env

## 🤝 Đóng góp

Mọi đóng góp và báo lỗi đều được chào đón! Vui lòng tạo issue hoặc pull request.

## 📜 Giấy phép

MIT License - Xem file [LICENSE](LICENSE) để biết thêm chi tiết.
