import schedule
import time
import asyncio
import threading
from discord.ext import commands, tasks
from sql_scripts import select_all_users_with_expired_subs
import discord
from config import server_id, bot_token

# Create a separate bot instance for the scheduler
intents = discord.Intents.default()
intents.members = True
intents.guilds = True
scheduler_bot = commands.Bot(command_prefix='!scheduler_', intents=intents)

GUILD_ID = int(server_id)

# async def kick_expired_users():
#     """Kick users with expired subscriptions"""
#     try:
#         users = await select_all_users_with_expired_subs()
#         print(f"Found {len(users)} users with expired subscriptions")

#         guild = scheduler_bot.get_guild(GUILD_ID)
#         if not guild:
#             print("Guild not found")
#             return

#         for user in users:
#             discord_id = user.discord_id if hasattr(user, 'discord_id') else user['discord_id']
#             member = guild.get_member(int(discord_id))
#             if member:
#                 try:
#                     await member.kick(reason="Subscription expired.")
#                     print(f"Kicked user {discord_id}")
#                 except Exception as e:
#                     print(f"Failed to kick {discord_id}: {e}")
#             else:
#                 print(f"Member {discord_id} not found in guild")
#     except Exception as e:
#         print(f"Error in kick_expired_users: {e}")

import time

GRACE_PERIOD_SECONDS = 3600  # 1 hour

async def kick_expired_users():
    """Kick users with expired subscriptions, but not immediately after join"""
    try:
        users = await select_all_users_with_expired_subs()

        guild = scheduler_bot.get_guild(GUILD_ID)
        if not guild:
            print("Guild not found")
            return

        now = time.time()

        for user in users:
            join_ts = getattr(user, "join_timestamp", None) or user.get("join_timestamp")
            
            # Skip if within grace period
            if join_ts and (now - join_ts) < GRACE_PERIOD_SECONDS:
                print(f"Skipping kick for {user.discord_id} (joined recently)")
                continue

            discord_id = user.discord_id if hasattr(user, 'discord_id') else user['discord_id']
            member = guild.get_member(int(discord_id))
            if member:
                try:
                    await member.kick(reason="Subscription expired.")
                    print(f"Kicked user {discord_id}")
                except Exception as e:
                    print(f"Failed to kick {discord_id}: {e}")
            else:
                print(f"Member {discord_id} not found in guild")
    except Exception as e:
        print(f"Error in kick_expired_users: {e}")


@tasks.loop(hours=24)
async def check_subscription_task():
    """Daily task to check and kick expired users"""
    print("Running subscription check...")
    # await kick_expired_users()

@scheduler_bot.event
async def on_ready():
    print(f'Scheduler bot logged in as {scheduler_bot.user}')
    if not check_subscription_task.is_running():
        check_subscription_task.start()
        print("Started subscription check task")

def run_scheduler_bot():
    """Run the scheduler bot in its own event loop"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        scheduler_bot.run(bot_token)
    except Exception as e:
        print(f"Error running scheduler bot: {e}")

def run_scheduler():
    """Start the scheduler in a separate thread"""
    scheduler_thread = threading.Thread(target=run_scheduler_bot, daemon=True)
    scheduler_thread.start()
    print("Scheduler thread started")
    return scheduler_thread

if __name__ == '__main__':
    # Run scheduler independently
    run_scheduler_bot()



