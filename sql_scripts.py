import asyncio
import time
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import class_mapper
from models import Orders, Users, async_session
from config import *


async def add_order(order_id: int, email: str, join_link: str, amount: str, sub_time, order_status: int = 0) -> Orders:
    current_unix_time = int(time.time())
    async with async_session() as session:
        new_order = Orders(
            order_id=order_id,
            email=email,
            link=join_link,
            amount_to_pay=amount,
            sub_time=int(sub_time),
            order_date=current_unix_time,
            order_status=order_status
        )
        session.add(new_order)
        await session.commit()
        return new_order


async def add_or_update_user(email, link, discord_name, discord_server_name, discord_id, date_of_payment, sub_time):

    current_time = int(time.time())
    subscription_duration_sec = int(sub_time) * 86400

    async with async_session() as session:
        result = await session.execute(select(Users).filter(Users.discord_id == discord_id))
        user = result.scalar_one_or_none()

        if user:
            user.email = email
            user.link = link
            user.date_of_payment = date_of_payment

            if user.sub_time and user.sub_time > current_time:
                new_subscription_expiry = user.sub_time + subscription_duration_sec
            else:
                new_subscription_expiry = current_time + subscription_duration_sec
            user.sub_time = new_subscription_expiry

            session.add(user)
        else:
            new_subscription_expiry = current_time + subscription_duration_sec
            new_user = Users(
                email=email,
                link=link,
                discord_name=discord_name,
                discord_server_name=discord_server_name,
                discord_id=discord_id,
                date_of_payment=date_of_payment,
                sub_time=new_subscription_expiry
            )
            session.add(new_user)

        await session.commit()


async def wait_for_payment(order_id: int, timeout: int = 300, interval: int = 5) -> Orders:
    start_time = datetime.utcnow()
    while (datetime.utcnow() - start_time).total_seconds() < timeout:
        async with async_session() as session:
            result = await session.execute(select(Orders).where(Orders.order_id == order_id))
            order = result.scalars().first()
            if order and order.order_status == 3:
                return order
        await asyncio.sleep(interval)
    return None


async def select_orders() -> Orders:
    async with async_session() as session:
        result = await session.execute(select(Orders))
        order = result.fetchall()
        if order:
            return [{column.key: getattr(row.Orders, column.key) for column in class_mapper(Orders).columns} for row in order]
        return order


async def select_orders_with_paid_status() -> Orders:
    async with async_session() as session:
        result = await session.execute(select(Orders).where(Orders.order_status == paid_order_status))
        order = result.fetchall()
        if order:
            return [{column.key: getattr(row.Orders, column.key) for column in class_mapper(Orders).columns} for row in order]
        return order


async def select_order_by_order_reference(order_reference) -> dict:
    async with async_session() as session:
        result = await session.execute(select(Orders).where(Orders.order_reference == order_reference))
        order = result.scalar_one_or_none()
        if order:
            return {column.key: getattr(order, column.key) for column in class_mapper(Orders).columns}
        return None


async def select_order_by_discord_link(discord_link) -> dict:
    async with async_session() as session:
        result = await session.execute(select(Orders).where(Orders.link == discord_link))
        order = result.scalar_one_or_none()
        if order:
            return {column.key: getattr(order, column.key) for column in class_mapper(Orders).columns}
        return None

async def add_user_from_order(order: Orders) -> Users:
    async with async_session() as session:
        new_user = Users(
            email=order.email,
            link=order.link,
            date_of_payment=int(datetime.utcnow().timestamp()),
            sub_time=30  # время подписки в днях (по умолчанию 30)
        )
        session.add(new_user)
        await session.commit()
        return new_user


async def update_user_with_discord_id(join_link: str, discord_id: int) -> Users:
    async with async_session() as session:
        result = await session.execute(select(Users).where(Users.link == join_link))
        user = result.scalars().first()
        if user:
            user.discord_id = discord_id
            user.link = None  # удаляем ссылку, чтобы нельзя было повторно вступить по ней
            await session.commit()
            return user
        return None


async def update_user_order_reference(order_id, order_reference):
    async with async_session() as session:
        result = await session.execute(select(Orders).where(Orders.order_id == order_id))
        order = result.scalars().first()
        if order:
            order.order_reference = order_reference
            await session.commit()


async def update_order_status_by_order_reference(order_reference, new_status):
    async with async_session() as session:
        result = await session.execute(
            select(Orders).where(
                Orders.order_reference == order_reference,
                Orders.order_status == 0
            )
        )
        order = result.scalars().first()
        if order:
            order.order_status = new_status
            await session.commit()


async def update_order_status_by_order_reference_v2(order_reference: str, new_status: int) -> bool:
    async with async_session() as session:
        stmt = select(Orders).where(
            Orders.order_reference == order_reference,
            Orders.order_status == paid_order_status
        )
        result = await session.execute(stmt)
        order = result.scalars().first()
        if order:
            order.order_status = new_status
            await session.commit()
            return True
        return False


async def delete_order_by_order_reference(order_reference):
    async with async_session() as session:
        result = await session.execute(select(Orders).where(Orders.order_reference == order_reference))
        order = result.scalars().first()
        if order:
            await session.delete(order)
            await session.commit()



# Пример использования:
# Предположим, что где-то в вашем коде (например, в обработчике команды Discord бота)
# вы генерируете order_id и join_link (с помощью discord.py) и получаете email и сумму.

#
# @bot.event
# async def on_member_join(member):
#     # Получаем join_link, по которому пришёл пользователь (см. пример отслеживания invite'ов)
#     used_link = ...  # Здесь ваша логика определения ссылки
#     updated_user = await update_user_with_discord_id(used_link, discord_id=member.id)
#     if updated_user:
#         print(f"Обновлён пользователь {updated_user.email} с Discord ID {member.id}")
#
# Не забудьте адаптировать этот пример под свою архитектуру и требования.
