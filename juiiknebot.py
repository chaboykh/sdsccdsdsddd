import discord
from discord.ext import commands
import json
import random
import os
import asyncio
from datetime import datetime, timezone
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import requests

# ===== CONFIGURATION =====
TOKEN = "MTM3NjU2NTE4MzUwOTY5NjUzNA.GgnBb9.QvOfECMjYnn0dTCzT5oVRte3E8ArUGHhDgrX6E"  # Replace with your bot token
PREFIX = "#"
XP_MIN = 5
XP_MAX = 15
COOLDOWN = 60  # seconds cooldown for text XP gain

LOG_CHANNEL_ID = 1360495203106160700  # Your level-up log channel ID

VOICE_XP_GAIN = 10          # XP granted every VOICE_CHECK_INTERVAL while in voice
VOICE_CHECK_INTERVAL = 60   # seconds between XP grants for voice activity

# ===== DISCORD INTENTS & BOT SETUP =====
intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
intents.guilds = True
intents.members = True
intents.voice_states = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# ===== DATA STORAGE =====
DATA_FILE = "levels.json"
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump({}, f)

with open(DATA_FILE, "r") as f:
    levels = json.load(f)

cooldowns = {}

def save_levels():
    with open(DATA_FILE, "w") as f:
        json.dump(levels, f, indent=4)

def xp_needed_for_next(level: int) -> int:
    # XP curve similar to ProBot
    return 5 * (level ** 2) + 50 * level + 100

# ===== RANK CARD GENERATOR WITH CAMBODIA THEME =====
def generate_rank_card(user: discord.Member, level: int, xp: int, needed: int):
    width, height = 900, 250
    bar_width = 580
    bar_height = 40
    bg_color = (30, 15, 5)  # Dark brown, like Angkor sandstone
    accent_color = (201, 110, 43)  # Warm orange, inspired by Angkor carvings
    text_color = (255, 236, 179)  # Soft cream

    # Create base image
    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    # Load fonts
    # You can download a Khmer font and specify the path here, or fallback to default Arial
    try:
        font_big = ImageFont.truetype("Battambang-Regular.ttf", 40)  # Khmer font if you have it
        font_small = ImageFont.truetype("Battambang-Regular.ttf", 24)
    except:
        font_big = ImageFont.truetype("arial.ttf", 40)
        font_small = ImageFont.truetype("arial.ttf", 24)

    # Draw progress bar background
    bar_x, bar_y = 250, 170
    draw.rectangle([bar_x, bar_y, bar_x + bar_width, bar_y + bar_height], fill=(90, 70, 40))  # darker brown bar bg

    # Draw progress bar fill
    progress = int((xp / needed) * bar_width)
    draw.rectangle([bar_x, bar_y, bar_x + progress, bar_y + bar_height], fill=accent_color)

    # User avatar circle mask
    avatar_asset = user.display_avatar.with_size(128)
    avatar_bytes = requests.get(avatar_asset.url).content
    avatar_img = Image.open(BytesIO(avatar_bytes)).convert("RGB").resize((180, 180))

    mask = Image.new("L", (180, 180), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.ellipse((0, 0, 180, 180), fill=255)
    img.paste(avatar_img, (40, 40), mask)

    # Draw user name and level in Khmer-inspired color
    draw.text((250, 60), f"{user.name}", font=font_big, fill=text_color)
    draw.text((250, 110), f"Level: {level}", font=font_small, fill=text_color)
    draw.text((400, 110), f"XP: {xp}/{needed}", font=font_small, fill=text_color)

    # Optionally, add a subtle Khmer Angkor motif border (skipped for brevity)

    # Save image to BytesIO buffer
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

# ===== EVENTS =====
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    if not hasattr(bot, "voice_xp_task"):
        bot.voice_xp_task = bot.loop.create_task(voice_xp_task())

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        await bot.process_commands(message)
        return

    user_id = str(message.author.id)
    now = asyncio.get_event_loop().time()

    # Text XP cooldown
    if user_id in cooldowns and now - cooldowns[user_id] < COOLDOWN:
        await bot.process_commands(message)
        return

    cooldowns[user_id] = now
    xp_gain = random.randint(XP_MIN, XP_MAX)

    if user_id not in levels:
        levels[user_id] = {"xp": 0, "level": 0}

    levels[user_id]["xp"] += xp_gain
    current_level = levels[user_id]["level"]
    needed = xp_needed_for_next(current_level)

    leveled = False
    while levels[user_id]["xp"] >= needed:
        levels[user_id]["xp"] -= needed
        levels[user_id]["level"] += 1
        current_level = levels[user_id]["level"]
        needed = xp_needed_for_next(current_level)
        leveled = True

    save_levels()

    if leveled:
        # Celebrate in chat
        await message.channel.send(f"🎉 {message.author.mention} just leveled up to **Level {levels[user_id]['level']}**!")

        # Send rank card + log embed
        log_channel = bot.get_channel(LOG_CHANNEL_ID) or await bot.fetch_channel(LOG_CHANNEL_ID)
        xp_now = levels[user_id]["xp"]
        needed_now = xp_needed_for_next(levels[user_id]["level"])
        card = generate_rank_card(message.author, levels[user_id]["level"], xp_now, needed_now)
        file = discord.File(card, filename="rank.png")

        embed = discord.Embed(
            title="📜 Angkor Level Up Log",
            description=f"{message.author.mention} បានកើនកំរិតទៅ **Level {levels[user_id]['level']}**!",
            color=discord.Color.orange(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="កំរិត (Level)", value=str(levels[user_id]["level"]))
        embed.add_field(name="ពិន្ទុ (XP)", value=f"{xp_now}/{needed_now}")
        embed.set_thumbnail(url=message.author.display_avatar.url)
        await log_channel.send(embed=embed, file=file)

    await bot.process_commands(message)

# ===== VOICE XP BACKGROUND TASK =====
async def voice_xp_task():
    await bot.wait_until_ready()
    while not bot.is_closed():
        for guild in bot.guilds:
            for vc in guild.voice_channels:
                for member in vc.members:
                    if member.bot:
                        continue
                    user_id = str(member.id)
                    if user_id not in levels:
                        levels[user_id] = {"xp": 0, "level": 0}
                    levels[user_id]["xp"] += VOICE_XP_GAIN

                    current_level = levels[user_id]["level"]
                    needed = xp_needed_for_next(current_level)

                    leveled = False
                    while levels[user_id]["xp"] >= needed:
                        levels[user_id]["xp"] -= needed
                        levels[user_id]["level"] += 1
                        current_level = levels[user_id]["level"]
                        needed = xp_needed_for_next(current_level)
                        leveled = True

                    if leveled:
                        log_channel = bot.get_channel(LOG_CHANNEL_ID) or await bot.fetch_channel(LOG_CHANNEL_ID)
                        if log_channel: 
                            embed = discord.Embed( 
                                title="🎧 Angkor Voice Level Up!",
                                description=f"{member.mention} បានកើនកំរិតដោយការនិយាយក្នុង Voice Channel! **Level {levels[user_id]['level']}**",
                                color=discord.Color.gold(),
                                timestamp=datetime.now(timezone.utc)
                            )
                            embed.set_thumbnail(url=member.display_avatar.url)
                            card = generate_rank_card(member, levels[user_id]["level"], levels[user_id]["xp"], xp_needed_for_next(levels[user_id]["level"]))
                            file = discord.File(card, filename="rank.png")
                            try:
                                await log_channel.send(embed=embed, file=file)
                            except Exception as e:
                                print(f"Failed to send voice level-up log: {e}")

        save_levels()
        await asyncio.sleep(VOICE_CHECK_INTERVAL)

# ===== COMMANDS =====
@bot.command()
async def id(ctx, member: discord.Member = None):
    member = member or ctx.author
    user_id = str(member.id)

    if user_id not in levels:
        await ctx.send(f"{member.mention} មិនទាន់មានពិន្ទុទេ។")
        return

    xp = levels[user_id]["xp"]
    level = levels[user_id]["level"]
    needed = xp_needed_for_next(level)
    card = generate_rank_card(member, level, xp, needed)
    await ctx.send(file=discord.File(card, filename="rank.png"))

@bot.command()
@commands.has_permissions(administrator=True)
async def setlevel(ctx, member: discord.Member, level: int):
    user_id = str(member.id)
    if user_id not in levels:
        levels[user_id] = {"xp": 0, "level": level}
    else:
        levels[user_id]["level"] = level
        levels[user_id]["xp"] = 0
    save_levels()
    await ctx.send(f"✅ បានកំណត់កំរិត {member.display_name} ទៅ {level}។")

# ===== RUN BOT =====
bot.run(TOKEN)
