import schedule
import time
import asyncio
from discord.ext import commands, tasks
from sql_scripts import select_all_users_with_expired_subs
import discord
from config import server_id, bot_token

intents = discord.Intents.default()
intents.members = True
intents.guilds = True
bot = commands.Bot(command_prefix='!', intents=intents)


GUILD_ID = int(server_id)

async def kick_expired_users():
    users = await select_all_users_with_expired_subs()

    guild = bot.get_guild(GUILD_ID)
    if not guild:
        print("Guild not found")
        return

    for user in users:
        discord_id = user.discord_id
        member = guild.get_member(discord_id)
        if member:
            try:
                await member.kick(reason="Subscription expired.")
                print(f"Kicked user {discord_id}")
            except Exception as e:
                print(f"Failed to kick {discord_id}: {e}")
        else:
            print(f"Member {discord_id} not found in guild")

# TODO check days
@tasks.loop(hours=24)
async def check_subscription_task():
    await kick_expired_users()

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    check_subscription_task.start()

def run_bot():
    bot.run(bot_token)
