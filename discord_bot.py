import time
import discord
from discord.ext import commands
import asyncio
from config import *
from sql_scripts import update_user_with_discord_id, select_order_by_discord_link, add_or_update_user


intents = discord.Intents.default()
intents.members = True
intents.message_content = True


bot = commands.Bot(command_prefix="!", intents=intents)


guild_invites = {}


@bot.event
async def on_ready():
    print(f"Бот {bot.user} запущен.")
    for guild in bot.guilds:
        try:
            invites = await guild.invites()
            guild_invites[guild.id] = {invite.code: invite.uses for invite in invites}
            print(f"Инвайты для {guild.name} сохранены.")
        except Exception as e:
            print(f"Ошибка получения инвайтов для {guild.name}: {e}")


async def generate_invite() -> str:
    await bot.wait_until_ready()

    channel = bot.get_channel(invite_channel_id)
    print(f"ID канала: {invite_channel_id}")
    print(f"Канал: {channel}")

    if channel is None:
        raise Exception("Канал для генерации инвайта не найден. Проверьте invite_channel_id в конфиге.")

    try:
        # Создаем инвайт
        invite = await channel.create_invite(max_uses=1, unique=True)
        guild = channel.guild

        # Обновляем локальное состояние инвайтов
        if guild.id in guild_invites:
            guild_invites[guild.id][invite.code] = invite.uses
        else:
            guild_invites[guild.id] = {invite.code: invite.uses}

        return invite.url
    except Exception as e:
        raise Exception(f"Ошибка при создании инвайта: {e}")

@bot.event
async def on_member_join(member):
    guild = member.guild
    try:
        current_invites = await guild.invites()
    except Exception as e:
        print(f"Ошибка получения инвайтов для {guild.name}: {e}")
        return

    used_invite = None
    previous_invites = guild_invites.get(guild.id, {})
    for invite in current_invites:
        prev_uses = previous_invites.get(invite.code, 0)
        if invite.uses > prev_uses:
            used_invite = invite
            break

    guild_invites[guild.id] = {invite.code: invite.uses for invite in current_invites}

    discord_id = member.id
    discord_name = member.name
    discord_server_name = member.display_name
    current_time = int(time.time())

    if used_invite:
        print(f"Пользователь {member} ({member.id}) присоединился по ссылке {used_invite.url}")
        discord_link = used_invite.url

        try:
            order = await select_order_by_discord_link(discord_link)
            
            if order:
                email = order['email']
                link = order['link']
                sub_time = order['sub_time']
                date_of_payment = order['order_date']

                # Add user with proper payment dates
                await add_or_update_user(email, link, discord_name, discord_server_name, discord_id, date_of_payment, sub_time)
                print(f"Обновлена запись пользователя {email} с Discord ID {member.id}")
            else:
                print(f"Заказ не найден для ссылки {discord_link}")
                # Add user without payment (will be kicked later)
                await add_or_update_user('', '', discord_name, discord_server_name, discord_id, current_time, 1)
        except Exception as e:
            print(f"Ошибка при обработке пользователя с инвайтом: {e}")
            # Add user without payment as fallback
            await add_or_update_user('', '', discord_name, discord_server_name, discord_id, current_time, 1)
    else:
        print(f"Не удалось определить, по какой ссылке присоединился {member.id}")
        # Add user without payment (will be kicked after grace period)
        await add_or_update_user('', '', discord_name, discord_server_name, discord_id, current_time, 1)

@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason=None):
    try:
        await member.kick(reason=reason)
        await ctx.send(f"{member.mention} был кикнут. Причина: {reason}")
    except Exception as e:
        await ctx.send(f"Не удалось кикнуть пользователя: {e}")

if __name__ == "__main__":
    bot.run(bot_token)