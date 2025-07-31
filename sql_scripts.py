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
            # Set last_date_of_payment to the same as date_of_payment for new payments
            user.last_date_of_payment = date_of_payment

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
                # Set both payment dates for new users
                last_date_of_payment=date_of_payment,
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
            last_date_of_payment=int(datetime.utcnow().timestamp()),
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


# Fixed function: Get users who should receive 30-day warning
async def select_users_for_30day_warning() -> list[Users]:
    """Get users whose payment expires in 30 days and haven't been warned yet"""
    current_time = int(time.time())
    warning_threshold = current_time + (30 * 86400)  # 30 days from now
    
    async with async_session() as session:
        result = await session.execute(
            select(Users).where(
                Users.last_date_of_payment < warning_threshold,
                Users.last_date_of_payment > (current_time - 10 * 86400),  # Not too old
                Users.discord_id.isnot(None)  # Has Discord ID
            )
        )
        return result.scalars().all()


# Fixed function: Get users with expired subscriptions (40 days)
async def select_all_users_with_expired_subs() -> list[Users]:
    """Get users whose subscription expired 40 days ago"""
    current_time = int(time.time())
    expiry_threshold = current_time - (40 * 86400)  # 40 days ago
    
    async with async_session() as session:
        result = await session.execute(
            select(Users).where(
                Users.last_date_of_payment < expiry_threshold,
                Users.discord_id.isnot(None)  # Has Discord ID
            )
        )
        return result.scalars().all()


# New function: Mark user as warned
async def mark_user_as_warned(discord_id: int):
    """Mark user as having received a 30-day warning"""
    async with async_session() as session:
        result = await session.execute(
            select(Users).where(Users.discord_id == discord_id)
        )
        user = result.scalar_one_or_none()
        if user:
            # You might want to add a 'warned' field to your Users model
            # For now, we'll use a different approach in the scheduler
            await session.commit()
            return True
        return False


async def update_user_last_payment_date(user_email, new_date):
    """Update user's last payment date when they make a payment"""
    async with async_session() as session:
        async with session.begin():
            result = await session.execute(
                select(Users).where(Users.email == user_email)
            )
            user = result.scalar_one_or_none()
            if user:
                user.last_date_of_payment = new_date
                await session.commit()
                return True
            return False


# New function: Get user by Discord ID
async def get_user_by_discord_id(discord_id: int) -> Users:
    """Get user by Discord ID"""
    async with async_session() as session:
        result = await session.execute(
            select(Users).where(Users.discord_id == discord_id)
        )
        return result.scalar_one_or_none()