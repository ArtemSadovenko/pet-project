import schedule
import time
import asyncio
import threading
from discord.ext import commands, tasks
from sql_scripts import select_all_users_with_expired_subs, select_users_for_30day_warning, get_user_by_discord_id
import discord
from config import server_id, bot_token

# Create a separate bot instance for the scheduler
intents = discord.Intents.default()
intents.members = True
intents.guilds = True
scheduler_bot = commands.Bot(command_prefix='!scheduler_', intents=intents)

GUILD_ID = int(server_id)
GRACE_PERIOD_SECONDS = 3600  # 1 hour grace period for new users

# Track warned users to avoid spam
warned_users = set()

async def send_warning_message(user_discord_id: int, days_remaining: int):
    """Send a warning message to user about subscription expiry"""
    try:
        user = await scheduler_bot.fetch_user(user_discord_id)
        if user:
            warning_message = (
                f"⚠️ **Увага!** ⚠️\n\n"
                f"Ваша підписка на Upwork Revolution закінчується через {days_remaining} днів.\n"
                f"Будь ласка, поновіть підписку, щоб продовжити доступ до community.\n\n"
                f"Якщо ви не поновите підписку, ви будете виключені з сервера через {days_remaining} днів.\n\n"
                f"Для поновлення підписки зверніться до адміністрації або скористайтеся нашим сайтом."
            )
            
            await user.send(warning_message)
            print(f"Warning sent to user {user_discord_id}")
            return True
    except discord.NotFound:
        print(f"User {user_discord_id} not found")
    except discord.Forbidden:
        print(f"Cannot send DM to user {user_discord_id}")
    except Exception as e:
        print(f"Error sending warning to {user_discord_id}: {e}")
    return False


async def send_30day_warnings():
    """Send 30-day warnings to users whose subscriptions are expiring"""
    try:
        users = await select_users_for_30day_warning()
        current_time = int(time.time())
        
        print(f"Checking {len(users)} users for 30-day warnings")
        
        for user in users:
            discord_id = user.discord_id if hasattr(user, 'discord_id') else user['discord_id']
            last_payment = user.last_date_of_payment if hasattr(user, 'last_date_of_payment') else user['last_date_of_payment']
            
            # Skip if already warned recently
            if discord_id in warned_users:
                continue
                
            # Calculate days since last payment
            days_since_payment = (current_time - last_payment) / 86400
            
            # Send warning if payment was 10 days ago (30 days left)
            if 9 <= days_since_payment <= 11:  # 2-day window to catch the notification
                success = await send_warning_message(discord_id, 30)
                if success:
                    warned_users.add(discord_id)
                    
    except Exception as e:
        print(f"Error in send_30day_warnings: {e}")


async def kick_expired_users():
    """Kick users with expired subscriptions (40 days after last payment)"""
    try:
        users = await select_all_users_with_expired_subs()
        current_time = int(time.time())

        guild = scheduler_bot.get_guild(GUILD_ID)
        if not guild:
            print("Guild not found")
            return

        print(f"Found {len(users)} users with expired subscriptions (40+ days)")

        for user in users:
            discord_id = user.discord_id if hasattr(user, 'discord_id') else user['discord_id']
            last_payment = user.last_date_of_payment if hasattr(user, 'last_date_of_payment') else user['last_date_of_payment']
            
            # Additional safety check: only kick if really expired (40+ days)
            days_since_payment = (current_time - last_payment) / 86400
            if days_since_payment < 40:
                continue
                
            # Skip if within grace period from join (for new users)
            join_ts = getattr(user, "date_of_payment", None) or user.get("date_of_payment")
            if join_ts and (current_time - join_ts) < GRACE_PERIOD_SECONDS:
                print(f"Skipping kick for {discord_id} (joined recently)")
                continue

            member = guild.get_member(int(discord_id))
            if member:
                try:
                    # Send final notification before kick
                    try:
                        await member.send(
                            "❌ **Вашу підписку було скасовано**\n\n"
                            "Ваша підписка на Upwork Revolution закінчилася, і ви були виключені з сервера.\n"
                            "Для повторного доступу, будь ласка, поновіть підписку через наш сайт.\n\n"
                            "Дякуємо за те, що були частиною нашої спільноти!"
                        )
                    except:
                        pass  # Ignore if can't send DM
                        
                    await member.kick(reason=f"Subscription expired {int(days_since_payment)} days ago")
                    print(f"Kicked user {discord_id} (expired {int(days_since_payment)} days ago)")
                    
                    # Remove from warned users set
                    warned_users.discard(discord_id)
                    
                except Exception as e:
                    print(f"Failed to kick {discord_id}: {e}")
            else:
                print(f"Member {discord_id} not found in guild")
                # Remove from warned users set if they're not in guild
                warned_users.discard(discord_id)
                
    except Exception as e:
        print(f"Error in kick_expired_users: {e}")


@tasks.loop(hours=6)  # Check every 6 hours
async def check_warnings_task():
    """Check for users who need 30-day warnings"""
    print("Running 30-day warning check...")
    await send_30day_warnings()


@tasks.loop(hours=24)  # Check daily
async def check_subscription_task():
    """Daily task to check and kick expired users"""
    print("Running subscription expiry check...")
    await kick_expired_users()


@tasks.loop(hours=24)  # Clean up warned users daily
async def cleanup_warned_users():
    """Clean up the warned users set to prevent memory issues"""
    global warned_users
    # Clear warnings older than 7 days to allow re-warning if needed
    warned_users.clear()
    print("Cleaned up warned users set")


@scheduler_bot.event
async def on_ready():
    print(f'Scheduler bot logged in as {scheduler_bot.user}')
    
    if not check_warnings_task.is_running():
        check_warnings_task.start()
        print("Started warning check task")
        
    if not check_subscription_task.is_running():
        check_subscription_task.start()
        print("Started subscription check task")
        
    if not cleanup_warned_users.is_running():
        cleanup_warned_users.start()
        print("Started cleanup task")


# Manual commands for testing (admin only)
@scheduler_bot.command()
@commands.has_permissions(administrator=True)
async def check_warnings_now(ctx):
    """Manually trigger warning check"""
    await ctx.send("Checking for users who need warnings...")
    await send_30day_warnings()
    await ctx.send("Warning check completed!")


@scheduler_bot.command()
@commands.has_permissions(administrator=True)
async def check_expired_now(ctx):
    """Manually trigger expired user check"""
    await ctx.send("Checking for expired users...")
    await kick_expired_users()
    await ctx.send("Expired user check completed!")


@scheduler_bot.command()
@commands.has_permissions(administrator=True)
async def user_status(ctx, discord_id: int):
    """Check a specific user's subscription status"""
    try:
        user = await get_user_by_discord_id(discord_id)
        if user:
            current_time = int(time.time())
            days_since_payment = (current_time - user.last_date_of_payment) / 86400
            
            status_msg = (
                f"**User Status for {discord_id}:**\n"
                f"Email: {user.email or 'N/A'}\n"
                f"Days since last payment: {int(days_since_payment)}\n"
                f"Last payment: <t:{user.last_date_of_payment}:F>\n"
                f"Subscription expires: <t:{user.last_date_of_payment + (40 * 86400)}:F>\n"
                f"Status: {'⚠️ Warning sent' if discord_id in warned_users else '✅ Active' if days_since_payment < 30 else '❌ Expiring soon'}"
            )
            await ctx.send(status_msg)
        else:
            await ctx.send(f"User {discord_id} not found in database")
    except Exception as e:
        await ctx.send(f"Error checking user status: {e}")


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