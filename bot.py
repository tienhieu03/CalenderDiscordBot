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
                await self.db_manager.delete_event(event_id)
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
        super().__init__(timeout=120)  # Tăng timeout lên vì người dùng cần chọn 2 lần
        self.bot = bot
        self.event_id = event_id
        self.title = title
        self.datetime_str = datetime_str
        self.first_reminder = None  # Lưu thời gian nhắc nhở đầu tiên
        
        # Tạo dropdown cho các lựa chọn thời gian
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
        
        # Tạo dropdown đầu tiên
        self.create_first_dropdown()

    def create_first_dropdown(self):
        self.clear_items()  # Xóa tất cả items hiện tại
        
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
        self.select.callback = self.first_reminder_callback
        self.add_item(self.select)

    def create_second_dropdown(self):
        self.clear_items()  # Xóa dropdown đầu tiên
        
        # Lọc bỏ option đã chọn ở lần 1
        remaining_options = [
            (label, minutes, emoji) 
            for label, minutes, emoji in self.remind_options
            if minutes != self.first_reminder
        ]
        
        select_options = [
            discord.SelectOption(
                label=label,
                value=str(minutes),
                emoji=emoji
            ) for label, minutes, emoji in remaining_options
        ]
        
        self.select = Select(
            placeholder="Chọn thời gian nhắc nhở lần 2 (hoặc bỏ qua)...",
            options=select_options,
            min_values=1,
            max_values=1
        )
        self.select.callback = self.second_reminder_callback
        self.add_item(self.select)
        
        # Thêm nút bỏ qua
        skip_button = Button(
            label="Chỉ nhắc 1 lần",
            style=discord.ButtonStyle.secondary,
            emoji="⏭️"
        )
        skip_button.callback = self.skip_callback
        self.add_item(skip_button)

    async def first_reminder_callback(self, interaction: discord.Interaction):
        try:
            self.first_reminder = int(self.select.values[0])
            
            # Cập nhật embed để hiển thị lựa chọn thứ hai
            embed = discord.Embed(
                title="⏰ Đặt thời gian nhắc nhở",
                description="Bạn muốn được nhắc thêm lần nữa không?",
                color=discord.Color.blue()
            )
            
            # Tạo dropdown cho lần chọn thứ hai
            self.create_second_dropdown()
            await interaction.response.edit_message(embed=embed, view=self)
            
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Lỗi: {str(e)}",
                ephemeral=True
            )

    async def second_reminder_callback(self, interaction: discord.Interaction):
        try:
            second_reminder = int(self.select.values[0])
            await self.set_reminders(interaction, [self.first_reminder, second_reminder])
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Lỗi: {str(e)}",
                ephemeral=True
            )

    async def skip_callback(self, interaction: discord.Interaction):
        await self.set_reminders(interaction, [self.first_reminder])

    async def set_reminders(self, interaction, times):
        try:
            # Sắp xếp thời gian để hiển thị theo thứ tự
            times.sort(reverse=True)
            
            # Đặt tất cả các nhắc nhở
            for minutes in times:
                await self.bot.scheduler.schedule_reminder(
                    self.event_id,
                    self.title,
                    self.datetime_str,
                    minutes
                )
            
            # Tạo mô tả về các thời điểm nhắc
            reminders_text = []
            for minutes in times:
                if minutes == 0:
                    reminders_text.append("ngay lúc diễn ra")
                else:
                    reminders_text.append(f"{minutes} phút trước khi diễn ra")
            
            reminder_desc = " và ".join(reminders_text)
            
            # Hiển thị thông báo thành công
            embed = discord.Embed(
                title="⏰ Đã đặt nhắc nhở",
                description=f"Sự kiện **{self.title}** sẽ được nhắc {reminder_desc}",
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
        super().__init__(command_prefix=COMMAND_PREFIX, intents=intents)
        
        self.calendar_manager = CalendarManager()
        self.db_manager = DatabaseManager()
        self.scheduler = SchedulerManager(self)
        
    async def setup_hook(self):
        await self.add_commands()
        
    async def add_commands(self):
        @self.command(name='add')
        @commands.has_permissions(administrator=True)
        async def add_event(ctx, *, content=""):
            if not content:
                await ctx.send("❌ Vui lòng nhập theo định dạng:\n"
                             "`b!add <tiêu đề> <dd/mm/yyyy HH:MM> <mô tả>`\n"
                             "Ví dụ: `b!add Họp nhóm 25/02/2024 15:30 Họp về dự án mới`")
                return
                
            try:
                # Tách nội dung thành các phần
                parts = content.split(' ')
                if len(parts) < 4:  # Ít nhất phải có: tiêu đề, ngày, giờ, mô tả
                    await ctx.send("❌ Thiếu thông tin! Vui lòng nhập đầy đủ tiêu đề, thời gian và mô tả")
                    return

                # Lấy ngày và giờ (2 phần tử)
                date_idx = next(i for i, part in enumerate(parts) if '/' in part)
                title = ' '.join(parts[:date_idx])  # Tất cả phần tử trước ngày là tiêu đề
                date = parts[date_idx]
                time = parts[date_idx + 1]
                description = ' '.join(parts[date_idx + 2:])  # Tất cả phần tử sau giờ là mô tả
                
                # Chuyển đổi định dạng ngày giờ
                try:
                    # Chuyển từ dd/mm/yyyy sang yyyy-mm-dd
                    day, month, year = date.split('/')
                    formatted_date = f"{year}-{month}-{day}"
                    datetime_str = f"{formatted_date} {time}"
                    
                    event_id = await self.calendar_manager.add_event(title, datetime_str, description)
                    
                    if event_id:
                        await self.db_manager.save_event(event_id, title, datetime_str, description, str(ctx.author.id))  # Thêm ID người tạo
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
                    await self.db_manager.save_event(
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

        @self.command(name='helps')
        async def show_help(ctx):
            embed = discord.Embed(
                title="📝 Hướng dẫn sử dụng Bot",
                description="Danh sách các lệnh có sẵn:",
                color=discord.Color.blue()
            )
            
            commands_help = {
                "b!add": {
                    "format": "b!add <tiêu đề> <dd/mm/yyyy HH:MM> <mô tả>",
                    "example": "b!add Họp nhóm 25/02/2024 15:30 Họp về dự án mới",
                    "desc": "Thêm sự kiện mới vào lịch"
                },
                "b!list": {  # Đổi tên trong help
                    "format": "b!list",
                    "example": "b!list",
                    "desc": "Xem danh sách các sự kiện sắp tới dưới dạng bảng"
                },
                "b!del": {  # Cập nhật tên lệnh trong help
                    "format": "b!del",
                    "example": "b!del",
                    "desc": "Hiện danh sách và xóa sự kiện theo lựa chọn"
                },
                "b!test": {
                    "format": "b!test",
                    "example": "b!test",
                    "desc": "Tạo sự kiện test (15 phút sau thời điểm hiện tại)"
                }
            }
            
            for cmd, info in commands_help.items():
                embed.add_field(
                    name=f"🔹 {cmd}",
                    value=f"Mô tả: {info['desc']}\n"
                          f"Định dạng: `{info['format']}`\n"
                          f"Ví dụ: `{info['example']}`",
                    inline=False
                )
            
            embed.set_footer(text="💡 Các lệnh add và del yêu cầu quyền Administrator")
            await ctx.send(embed=embed)

    async def on_ready(self):
        print(f'{self.user} đã sẵn sàng!')
        await self.scheduler.start()

def run_bot():
    bot = CalendarBot()
    bot.run(DISCORD_TOKEN)

if __name__ == "__main__":
    run_bot()
