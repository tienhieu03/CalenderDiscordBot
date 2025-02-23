import discord
from discord.ext import commands
import asyncio
from datetime import datetime, timedelta
import importlib.util
import sys
import os
from pathlib import Path
from calendar_manager import CalendarManager
from config import DISCORD_TOKEN, COMMAND_PREFIX
from database import DatabaseManager
from scheduler import SchedulerManager
from discord.ui import Select, View, Button

class ContinueDeleteView(View):
    def __init__(self, bot, ctx):
        super().__init__(timeout=30)
        self.bot = bot
        self.ctx = ctx
        
        # Thêm nút Có
        self.yes_button = Button(
            label="Có",
            style=discord.ButtonStyle.green,
            emoji="✅"
        )
        self.yes_button.callback = self.yes_callback
        self.add_item(self.yes_button)
        
        # Thêm nút Không
        self.no_button = Button(
            label="Không",
            style=discord.ButtonStyle.red,
            emoji="❌"
        )
        self.no_button.callback = self.no_callback
        self.add_item(self.no_button)
    
    async def yes_callback(self, interaction: discord.Interaction):
        await interaction.message.delete()  # Xóa message hỏi
        # Tạo lại menu xóa sự kiện mới
        await self.bot.get_command('del').callback(self.ctx)
    
    async def no_callback(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="✅ Hoàn tất xóa sự kiện",
            color=discord.Color.green()
        )
        await interaction.response.edit_message(embed=embed, view=None)

class DeleteView(View):
    def __init__(self, events, calendar_manager, db_manager, scheduler, bot, ctx):
        super().__init__(timeout=60)
        self.events = events
        self.calendar_manager = calendar_manager
        self.db_manager = db_manager
        self.scheduler = scheduler
        self.bot = bot
        self.ctx = ctx
        
        # Tạo dropdown menu
        select_options = []
        for idx, event in enumerate(events, 1):
            title = event['summary']
            start_time = event['start'].get('dateTime', event['start'].get('date'))
            if 'T' in start_time:
                dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                time_str = dt.strftime('%d/%m/%Y %H:%M')
            else:
                dt = datetime.strptime(start_time, '%Y-%m-%d')
                time_str = dt.strftime('%d/%m/%Y')
                
            label = f"{title} - {time_str}"
            if len(label) > 100:  # Discord có giới hạn độ dài label
                label = label[:97] + "..."
                
            select_options.append(
                discord.SelectOption(
                    label=label,
                    value=str(idx-1),
                    emoji="📅"
                )
            )
        
        # Thêm dropdown vào view
        self.select = Select(
            placeholder="Chọn sự kiện cần xóa...",
            options=select_options,
            min_values=1,
            max_values=1
        )
        self.select.callback = self.select_callback
        self.add_item(self.select)
        
        # Thêm nút hủy
        self.cancel_button = Button(
            label="Hủy",
            style=discord.ButtonStyle.secondary,
            emoji="❌"
        )
        self.cancel_button.callback = self.cancel_callback
        self.add_item(self.cancel_button)
        
    async def select_callback(self, interaction: discord.Interaction):
        try:
            idx = int(self.select.values[0])
            event = self.events[idx]
            event_id = event['id']
            
            if await self.calendar_manager.delete_event(event_id):
                self.db_manager.delete_event(event_id)
                await self.scheduler.remove_reminder(event_id)
                
                # Hiện thông báo xóa thành công
                embed = discord.Embed(
                    title="✅ Đã xóa sự kiện",
                    description=f"**{event['summary']}**",
                    color=discord.Color.green()
                )
                
                # Tạo view mới để hỏi người dùng
                continue_view = ContinueDeleteView(self.bot, self.ctx)
                await interaction.response.edit_message(
                    embed=embed,
                    view=continue_view,
                    content="Bạn có muốn xóa thêm sự kiện không?"
                )
            else:
                await interaction.response.send_message(
                    "❌ Không thể xóa sự kiện. Vui lòng thử lại.",
                    ephemeral=True
                )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Lỗi: {str(e)}",
                ephemeral=True
            )
    
    async def cancel_callback(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="❌ Đã hủy xóa sự kiện",
            color=discord.Color.red()
        )
        await interaction.response.edit_message(embed=embed, view=None)

class ReminderSelectView(View):
    def __init__(self, bot, event_id, title, datetime_str):
        super().__init__(timeout=120)
        self.bot = bot
        self.event_id = event_id
        self.title = title
        self.datetime_str = datetime_str
        self.first_reminder = None
        self.repeat_times = 1  # Mặc định nhắc 1 lần
        
        # Định nghĩa cả remind_options và repeat_options
        self.remind_options = [
            ("Vào lúc diễn ra", 0, "⏰"),
            ("5 phút trước", 5, "5️⃣"),
            ("10 phút trước", 10, "🔟"),
            ("15 phút trước", 15, "🕒"),
            ("30 phút trước", 30, "🕧"),
            ("1 tiếng trước", 60, "1️⃣"),
            ("2 tiếng trước", 120, "2️⃣"),
            ("5 tiếng trước", 300, "5️⃣"),
            ("1 ngày trước", 1440, "📅"),
            ("2 ngày trước", 2880, "📆")
        ]
        
        self.repeat_options = [
            ("Nhắc 1 lần", 1, "1️⃣"),
            ("Nhắc 2 lần", 2, "2️⃣"),
            ("Nhắc 3 lần", 3, "3️⃣"),
            ("Nhắc 5 lần", 5, "5️⃣")
        ]
        
        # Tạo dropdown đầu tiên cho thời gian
        self.create_time_dropdown()

    def create_time_dropdown(self):
        self.clear_items()
        
        select_options = [
            discord.SelectOption(
                label=label,
                value=str(minutes),
                emoji=emoji
            ) for label, minutes, emoji in self.remind_options
        ]
        
        self.select = Select(
            placeholder="Chọn thời gian nhắc nhở lần 1...",
            options=select_options,
            min_values=1,
            max_values=1
        )
        self.select.callback = self.time_callback
        self.add_item(self.select)

    async def time_callback(self, interaction: discord.Interaction):
        try:
            self.first_reminder = int(self.select.values[0])
            
            # Sau khi chọn thời gian, hiển thị lựa chọn số lần nhắc
            embed = discord.Embed(
                title="🔄 Số lần nhắc nhở",
                description="Bạn muốn nhắc nhở mấy lần?\n(Mỗi lần cách nhau 15 giây)",  # Cập nhật mô tả
                color=discord.Color.blue()
            )
            
            # Tạo dropdown cho số lần nhắc
            self.create_repeat_dropdown()
            await interaction.response.edit_message(embed=embed, view=self)
            
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Lỗi: {str(e)}",
                ephemeral=True
            )

    def create_repeat_dropdown(self):
        self.clear_items()
        
        select_options = [
            discord.SelectOption(
                label=label,
                value=str(times),
                emoji=emoji
            ) for label, times, emoji in self.repeat_options
        ]
        
        self.select = Select(
            placeholder="Chọn số lần nhắc...",
            options=select_options,
            min_values=1,
            max_values=1
        )
        self.select.callback = self.repeat_callback
        self.add_item(self.select)

    async def repeat_callback(self, interaction: discord.Interaction):
        try:
            self.repeat_times = int(self.select.values[0])
            await self.schedule_reminder(interaction)
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Lỗi: {str(e)}",
                ephemeral=True
            )

    async def schedule_reminder(self, interaction):
        try:
            await self.bot.scheduler.schedule_reminder(
                self.event_id,
                self.title,
                self.datetime_str,
                self.first_reminder,
                self.repeat_times
            )
            
            # Hiển thị thông báo thành công
            reminder_text = "ngay lúc diễn ra" if self.first_reminder == 0 else f"{self.first_reminder} phút trước khi diễn ra"
            embed = discord.Embed(
                title="⏰ Đã đặt nhắc nhở",
                description=f"Sự kiện **{self.title}** sẽ được nhắc {reminder_text}\n"
                           f"Số lần nhắc: **{self.repeat_times}** lần",
                color=discord.Color.green()
            )
            await interaction.response.edit_message(embed=embed, view=None)
            
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Lỗi khi đặt nhắc nhở: {str(e)}",
                ephemeral=True
            )

class CalendarBot(commands.Bot):
    def __init__(self):
        # Cập nhật intents để có thể đọc member data
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True  # Thêm quyền đọc members
        intents.guilds = True   # Thêm quyền đọc guild data
        
        # Sử dụng case_insensitive=True để bỏ qua hoa thường trong prefix
        super().__init__(
            command_prefix=COMMAND_PREFIX, 
            intents=intents,
            case_insensitive=True
        )
        
        self.calendar_manager = CalendarManager()
        self.db_manager = DatabaseManager()
        self.scheduler = SchedulerManager(self)
        
    async def setup_hook(self):
        await self.add_commands()
        
    async def add_commands(self):
        @self.command(name='add')
        @commands.has_permissions(administrator=True)
        async def add_event(ctx, *, content=""):
            # Kiểm tra calendar id của user
            calendar_id = self.db_manager.get_user_calendar(str(ctx.author.id))
            if not calendar_id:
                embed = discord.Embed(
                    title="❌ Chưa cài đặt Calendar",
                    description="Bạn cần cài đặt Calendar ID trước khi thêm sự kiện. Sử dụng lệnh:\n`b!setcalendar your.email@gmail.com`",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return

            if not content:
                await ctx.send("❌ Vui lòng nhập theo định dạng:\n"
                             "`b!add <tiêu đề> <dd/mm/yyyy HH:MM> [mô tả]`\n"
                             "Ví dụ: `b!add Họp nhóm 25/02/2024 15:30 Họp về dự án mới`")
                return
                
            try:
                # Tách nội dung thành các phần
                parts = content.split(' ')
                if len(parts) < 3:  # Chỉ yêu cầu tiêu đề, ngày và giờ
                    await ctx.send("❌ Thiếu thông tin! Vui lòng nhập đầy đủ tiêu đề và thời gian")
                    return

                # Lấy ngày và giờ (2 phần tử)
                date_idx = next(i for i, part in enumerate(parts) if '/' in part)
                title = ' '.join(parts[:date_idx])  # Tất cả phần tử trước ngày là tiêu đề
                date = parts[date_idx]
                time = parts[date_idx + 1]
                description = ' '.join(parts[date_idx + 2:]) if len(parts) > date_idx + 2 else "Không có mô tả"
                
                # Chuyển đổi định dạng ngày giờ
                try:
                    # Chuyển từ dd/mm/yyyy sang yyyy-mm-dd
                    day, month, year = date.split('/')
                    formatted_date = f"{year}-{month}-{day}"
                    datetime_str = f"{formatted_date} {time}"
                    
                    event_id = await self.calendar_manager.add_event(title, datetime_str, description)
                    
                    if event_id:
                        self.db_manager.save_event(event_id, title, datetime_str, description, str(ctx.author.id))  # Thêm ID người tạo
                        event_embed = discord.Embed(
                            title="✅ Sự kiện đã được tạo",
                            description=(
                                f"ID: {event_id}\n"
                                f"Tiêu đề: {title}\n"
                                f"Thời gian: {date} {time}\n"
                                f"Mô tả: {description}"
                            ),
                            color=discord.Color.green()
                        )
                        await ctx.send(embed=event_embed)
                        
                        # Hiển thị lựa chọn thời gian nhắc nhở
                        remind_embed = discord.Embed(
                            title="⏰ Đặt thời gian nhắc nhở",
                            description="Bạn muốn được nhắc nhở trước bao lâu?",
                            color=discord.Color.blue()
                        )
                        view = ReminderSelectView(self, event_id, title, datetime_str)
                        await ctx.send(embed=remind_embed, view=view)
                    else:
                        await ctx.send("❌ Không thể tạo sự kiện. Vui lòng thử lại.")
                except ValueError:
                    await ctx.send("❌ Định dạng ngày giờ không hợp lệ!\n"
                                 "Vui lòng sử dụng định dạng: `dd/mm/yyyy HH:MM`")
                    return
                    
            except Exception as e:
                await ctx.send(f"❌ Lỗi: {str(e)}")

        @self.command(name='list')  # Đổi tên từ events thành list
        async def list_events(ctx):
            events = await self.calendar_manager.list_events()
            if not events:
                await ctx.send("Không có sự kiện nào sắp tới.")
                return

            # Lọc bỏ các sự kiện sinh nhật
            filtered_events = [
                event for event in events 
                if not "birthday" in event.get('summary', '').lower() 
                and not "sinh nhật" in event.get('summary', '').lower()
            ]

            if not filtered_events:
                await ctx.send("Không có sự kiện nào sắp tới.")
                return

            # Tạo bảng sự kiện
            embed = discord.Embed(
                title="📅 Danh sách sự kiện sắp tới",
                color=discord.Color.blue()
            )

            # Tạo danh sách theo dạng list
            description = ""
            for idx, event in enumerate(filtered_events, 1):
                title = event['summary']
                
                # Chuyển đổi thời gian
                start_time = event['start'].get('dateTime', event['start'].get('date'))
                if 'T' in start_time:
                    dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                    time_str = dt.strftime('%d/%m/%Y %H:%M')
                else:
                    dt = datetime.strptime(start_time, '%Y-%m-%d')
                    time_str = dt.strftime('%d/%m/%Y')
                
                desc = event.get('description', 'Không có mô tả')
                if len(desc) > 50:
                    desc = desc[:47] + "..."
                
                description += f"**{idx}. {title}**\n"
                description += f"⏰ {time_str}\n"
                description += f"📝 {desc}\n\n"

            embed.description = description
            embed.set_footer(text="💡 Sử dụng b!add để thêm sự kiện mới")
            
            await ctx.send(embed=embed)

        @self.command(name='del')
        @commands.has_permissions(administrator=True)
        async def delete_event(ctx):
            """Xóa sự kiện bằng dropdown menu"""
            events = await self.calendar_manager.list_events()
            
            # Lọc bỏ các sự kiện sinh nhật
            filtered_events = [
                event for event in events 
                if not "birthday" in event.get('summary', '').lower() 
                and not "sinh nhật" in event.get('summary', '').lower()
            ]

            if not filtered_events:
                await ctx.send("❌ Không có sự kiện nào để xóa.")
                return

            embed = discord.Embed(
                title="🗑️ Xóa sự kiện",
                description="Chọn sự kiện bạn muốn xóa từ danh sách bên dưới:",
                color=discord.Color.blue()
            )
            
            # Tạo view với dropdown và button, truyền thêm bot và ctx
            view = DeleteView(
                filtered_events,
                self.calendar_manager,
                self.db_manager,
                self.scheduler,
                self,
                ctx
            )
            
            await ctx.send(embed=embed, view=view)

        @self.command(name='test')
        @commands.has_permissions(administrator=True)
        async def add_test_event(ctx):
            # Kiểm tra calendar id của user
            calendar_id = self.db_manager.get_user_calendar(str(ctx.author.id))
            if not calendar_id:
                embed = discord.Embed(
                    title="❌ Chưa cài đặt Calendar",
                    description="Bạn cần cài đặt Calendar ID trước khi thêm sự kiện. Sử dụng lệnh:\n`b!setcalendar your.email@gmail.com`",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return

            try:
                # Tạo sự kiện test cho 15 phút sau
                now = datetime.now()
                test_time = now + timedelta(minutes=15)
                time_str = test_time.strftime('%Y-%m-%d %H:%M')
                
                test_data = {
                    'title': 'Sự kiện Test',
                    'datetime': time_str,
                    'description': 'Đây là sự kiện test tự động'
                }
                
                event_id = await self.calendar_manager.add_event(
                    test_data['title'],
                    test_data['datetime'],
                    test_data['description']
                )
                
                if event_id:
                    self.db_manager.save_event(
                        event_id,
                        test_data['title'],
                        test_data['datetime'],
                        test_data['description'],
                        str(ctx.author.id)  # Thêm ID người tạo
                    )
                    
                    embed = discord.Embed(
                        title="Sự kiện Test đã được tạo",
                        description=(
                            f"ID: {event_id}\n"
                            f"Tiêu đề: {test_data['title']}\n"
                            f"Thời gian: {test_data['datetime']}\n"
                            f"Mô tả: {test_data['description']}"
                        ),
                        color=discord.Color.green()
                    )
                    await ctx.send(embed=embed)
                    await self.scheduler.schedule_reminder(
                        event_id,
                        test_data['title'],
                        test_data['datetime']
                    )
                else:
                    await ctx.send("Không thể tạo sự kiện test. Vui lòng thử lại.")
            except Exception as e:
                await ctx.send(f"Lỗi khi tạo sự kiện test: {str(e)}")

        @self.command(name='setcalendar')
        async def set_calendar(ctx, calendar_id=None):
            """Cài đặt Calendar ID cho người dùng"""
            if not calendar_id:
                await ctx.send("❌ Vui lòng nhập Calendar ID! Ví dụ:\n`b!setcalendar your.email@gmail.com`")
                return

            try:
                # Lưu calendar ID (không cần await)
                self.db_manager.save_user_calendar(str(ctx.author.id), calendar_id)
                
                embed = discord.Embed(
                    title="✅ Đã cài đặt Calendar",
                    description=f"Calendar ID của bạn đã được cài đặt thành:\n`{calendar_id}`",
                    color=discord.Color.green()
                )
                embed.set_footer(text="💡 Bot sẽ sử dụng calendar này cho các sự kiện của bạn")
                await ctx.send(embed=embed)
                
            except Exception as e:
                await ctx.send(f"❌ Lỗi khi cài đặt calendar: {str(e)}")

        @self.command(name='mycalendar')
        async def show_calendar(ctx):
            """Hiển thị Calendar ID hiện tại của người dùng"""
            try:
                calendar_id = self.db_manager.get_user_calendar(str(ctx.author.id))
                if (calendar_id):
                    embed = discord.Embed(
                        title="📅 Calendar của bạn",
                        description=f"Calendar ID hiện tại: `{calendar_id}`",
                        color=discord.Color.blue()
                    )
                else:
                    embed = discord.Embed(
                        title="❌ Chưa cài đặt Calendar",
                        description="Bạn chưa cài đặt Calendar ID. Sử dụng lệnh:\n`b!setcalendar your.email@gmail.com`",
                        color=discord.Color.red()
                    )
                await ctx.send(embed=embed)
                
            except Exception as e:
                await ctx.send(f"❌ Lỗi khi kiểm tra calendar: {str(e)}")

        @self.command(name='helps')
        async def show_help(ctx):
            embed = discord.Embed(
                title="📝 Hướng dẫn sử dụng Bot",
                description="Bot hỗ trợ cả prefix chữ hoa (B!) và chữ thường (b!)\nDanh sách các lệnh có sẵn:",
                color=discord.Color.blue()
            )
            
            commands_help = {
                "add": {
                    "format": "<B! hoặc b!>add <tiêu đề> <dd/mm/yyyy HH:MM> [mô tả]",
                    "example": "B!add Họp nhóm 25/02/2024 15:30 Họp về dự án mới",
                    "desc": "Thêm sự kiện mới vào lịch (mô tả là tùy chọn)"
                },
                "list": {
                    "format": "<B! hoặc b!>list",
                    "example": "B!list",
                    "desc": "Xem danh sách các sự kiện sắp tới"
                },
                "del": {
                    "format": "<B! hoặc b!>del",
                    "example": "B!del",
                    "desc": "Hiện danh sách và xóa sự kiện theo lựa chọn"
                },
                "test": {
                    "format": "<B! hoặc b!>test",
                    "example": "B!test",
                    "desc": "Tạo sự kiện test (15 phút sau thời điểm hiện tại)"
                },
                "setcalendar": {
                    "format": "<B! hoặc b!>setcalendar <calendar_id>",
                    "example": "B!setcalendar your.email@gmail.com",
                    "desc": "Cài đặt Calendar ID của bạn"
                },
                "mycalendar": {
                    "format": "<B! hoặc b!>mycalendar",
                    "example": "B!mycalendar",
                    "desc": "Xem Calendar ID hiện tại của bạn"
                }
            }
            
            for cmd, info in commands_help.items():
                embed.add_field(
                    name=f"🔹 Lệnh: {cmd}",
                    value=f"Mô tả: {info['desc']}\n"
                          f"Định dạng: `{info['format']}`\n"
                          f"Ví dụ: `{info['example']}`",
                    inline=False
                )
            
            embed.set_footer(text="💡 Các lệnh add và del yêu cầu quyền Administrator\n"
                                "📝 Bot hỗ trợ cả prefix B! và b!")
            await ctx.send(embed=embed)

    async def on_ready(self):
        print(f'{self.user} đã sẵn sàng!')
        await self.scheduler.start()

def run_bot():
    bot = CalendarBot()
    bot.run(DISCORD_TOKEN)

if __name__ == "__main__":
    run_bot()