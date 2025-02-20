from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta
import discord

class SchedulerManager:
    def __init__(self, bot):
        self.bot = bot
        self.scheduler = AsyncIOScheduler()
        self.reminders = {}

    async def start(self):
        self.scheduler.start()

    async def schedule_reminder(self, event_id, title, datetime_str, minutes_before=0):
        """Lập lịch nhắc nhở sự kiện
        
        Args:
            event_id: ID của sự kiện
            title: Tiêu đề sự kiện
            datetime_str: Thời gian diễn ra (định dạng: YYYY-MM-DD HH:MM)
            minutes_before: Số phút nhắc trước khi diễn ra (mặc định: 0)
        """
        event_time = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M')
        
        # Tính thời gian nhắc nhở
        if minutes_before > 0:
            reminder_time = event_time - timedelta(minutes=minutes_before)
        else:
            reminder_time = event_time
        
        job = self.scheduler.add_job(
            self.send_reminder,
            'date',
            run_date=reminder_time,
            args=[event_id, title, minutes_before]
        )
        
        self.reminders[event_id] = job

    async def remove_reminder(self, event_id):
        if event_id in self.reminders:
            self.reminders[event_id].remove()
            del self.reminders[event_id]

    async def send_reminder(self, event_id, title, minutes_before=0):
        """Gửi thông báo nhắc nhở"""
        try:
            # Lấy ID người tạo sự kiện
            creator_id = await self.bot.db_manager.get_event_creator(event_id)
            
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
            print(traceback.format_exc())  # In ra stack trace đầy đủ
