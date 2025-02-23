from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta
import discord
from pytz import timezone

class SchedulerManager:
    def __init__(self, bot):
        self.bot = bot
        self.scheduler = AsyncIOScheduler(
            timezone=timezone('Asia/Ho_Chi_Minh'),
            job_defaults={
                'misfire_grace_time': 60,  # Cho phép job chạy trễ tối đa 60s
                'coalesce': True  # Gộp các jobs bị miss
            }
        )
        self.reminders = {}

    async def start(self):
        self.scheduler.start()

    async def schedule_reminder(self, event_id, title, datetime_str, minutes_before=0, repeat_times=1):
        """Lập lịch nhắc nhở sự kiện"""
        try:
            # Chuyển datetime string sang datetime object với múi giờ VN
            tz = timezone('Asia/Ho_Chi_Minh')
            event_time = tz.localize(datetime.strptime(datetime_str, '%Y-%m-%d %H:%M'))
            
            print(f"🕒 Lập lịch nhắc nhở cho sự kiện: {title}")
            print(f"⏰ Thời gian diễn ra: {event_time}")
            
            # Tính thời gian bắt đầu nhắc
            if minutes_before > 0:
                reminder_time = event_time - timedelta(minutes=minutes_before)
            else:
                reminder_time = event_time  # Nhắc ngay lúc diễn ra
                
            print(f"⏰ Sẽ bắt đầu nhắc từ: {reminder_time}")
            
            # Tạo nhiều jobs cho mỗi lần nhắc
            for i in range(repeat_times):
                # Thay đổi từ minutes thành seconds
                job_time = reminder_time + timedelta(seconds=i*15)  # Mỗi 15 giây một lần
                print(f"📅 Đặt nhắc lần {i+1} lúc: {job_time}")
                
                reminder_job = self.scheduler.add_job(
                    self.send_reminder,
                    'date',
                    run_date=job_time,
                    args=[event_id, title, minutes_before],
                    id=f"{event_id}_remind_{i}",
                    misfire_grace_time=15  # Giảm misfire_grace_time xuống 15s
                )
                self.reminders[f"{event_id}_remind_{i}"] = reminder_job

            # Thêm job tự động xóa sau 1 phút
            cleanup_time = event_time + timedelta(minutes=1)
            print(f"🧹 Sẽ dọn dẹp lúc: {cleanup_time}")
            
            cleanup_job = self.scheduler.add_job(
                self.cleanup_event,
                'date',
                run_date=cleanup_time,
                args=[event_id, title],
                id=f"{event_id}_cleanup",
                misfire_grace_time=60
            )
            self.reminders[f"{event_id}_cleanup"] = cleanup_job
            
        except Exception as e:
            print(f"❌ Lỗi khi lập lịch nhắc nhở: {str(e)}")
            import traceback
            print(traceback.format_exc())

    async def remove_reminder(self, event_id):
        """Xóa tất cả jobs liên quan đến một sự kiện"""
        try:
            # Lấy danh sách các keys cần xóa
            keys_to_remove = [
                key for key in self.reminders.keys() 
                if key.startswith(f"{event_id}_")
            ]
            
            # Xóa từng job an toàn
            for key in keys_to_remove:
                try:
                    if key in self.reminders:
                        try:
                            self.reminders[key].remove()
                        except Exception as e:
                            print(f"Không thể xóa job {key}: {str(e)}")
                        finally:
                            del self.reminders[key]
                except Exception as e:
                    print(f"Lỗi khi xử lý job {key}: {str(e)}")
                    
            print(f"✓ Đã xóa {len(keys_to_remove)} jobs cho sự kiện {event_id}")
            
        except Exception as e:
            print(f"❌ Lỗi khi xóa reminders: {str(e)}")

    async def send_reminder(self, event_id, title, minutes_before=0):
        """Gửi thông báo nhắc nhở"""
        try:
            # Bỏ await vì get_event_creator không phải async
            creator_id = self.bot.db_manager.get_event_creator(event_id)
            
            if not creator_id:
                print(f"❌ Không tìm thấy người tạo sự kiện ID: {event_id}")
                return
                
            print(f"🔍 Tìm user ID: {creator_id} cho sự kiện: {title}")
            found_user = False
            
            # Tìm user trong tất cả các server
            for guild in self.bot.guilds:
                member = guild.get_member(int(creator_id))
                if member:
                    found_user = True
                    print(f"✓ Đã tìm thấy user {member.name}#{member.discriminator} trong server {guild.name}")
                    
                    # Tạo tin nhắn
                    if minutes_before > 0:
                        message = f"⚠️ Sự kiện **{title}** của bạn sẽ diễn ra sau {minutes_before} phút!"
                    else:
                        message = f"🔔 Sự kiện **{title}** của bạn đang diễn ra!"
                        
                    embed = discord.Embed(
                        title="Nhắc nhở sự kiện!",
                        description=message,
                        color=discord.Color.orange()
                    )
                    
                    try:
                        # Thử gửi DM
                        print(f"📨 Đang gửi DM cho {member.name}...")
                        await member.send(embed=embed)
                        print(f"✓ Đã gửi DM thành công")
                        
                    except discord.Forbidden as e:
                        print(f"❌ Không thể gửi DM: {str(e)}")
                        print("↪️ Thử gửi vào kênh general...")
                        
                        # Thử gửi vào kênh general
                        channel = discord.utils.get(guild.text_channels, name='general')
                        if channel:
                            await channel.send(f"{member.mention}", embed=embed)
                            print(f"✓ Đã gửi thông báo vào kênh {channel.name}")
                        else:
                            print("❌ Không tìm thấy kênh general")
                            
                    except Exception as e:
                        print(f"❌ Lỗi không xác định khi gửi tin nhắn: {str(e)}")
                    
                    break
            
            if not found_user:
                print(f"❌ Không tìm thấy user ID {creator_id} trong bất kỳ server nào")
                        
        except Exception as e:
            print(f"❌ Lỗi khi gửi nhắc nhở: {str(e)}")
            import traceback
            print(traceback.format_exc())

    async def cleanup_event(self, event_id, title):
        """Xóa sự kiện khỏi database và Google Calendar sau khi kết thúc"""
        try:
            print(f"🧹 Đang dọn dẹp sự kiện: {title}")
            
            # Xóa khỏi Google Calendar
            calendar_success = await self.bot.calendar_manager.delete_event(event_id)
            if calendar_success:
                print(f"✓ Đã xóa sự kiện khỏi Google Calendar")
            else:
                print(f"❌ Không thể xóa sự kiện khỏi Google Calendar")
                
            # Xóa khỏi MongoDB
            self.bot.db_manager.delete_event(event_id)
            print(f"✓ Đã xóa sự kiện khỏi database")
            
            # Xóa jobs khỏi scheduler
            await self.remove_reminder(event_id)
            print(f"✓ Đã xóa các nhắc nhở còn lại")
            
        except Exception as e:
            print(f"❌ Lỗi khi dọn dẹp sự kiện: {str(e)}")
            import traceback
            print(traceback.format_exc())
