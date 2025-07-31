import logging
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker, class_mapper
from sqlalchemy import Column, Integer, String, BigInteger, Float, insert, update, delete, Float, Boolean
from sqlalchemy import select
from datetime import datetime, timedelta
from config import *


Base = declarative_base()


engine = create_async_engine(DATABASE_URL, echo=False)
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Orders(Base):
    __tablename__ = 'orders'
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer)
    email = Column(String)
    link = Column(String)
    amount_to_pay = Column(String)
    order_reference = Column(String)
    sub_time = Column(Integer)
    order_date = Column(Integer)
    order_status = Column(Integer)


class Users(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    email = Column(String)
    link = Column(String)
    discord_name = Column(String)
    discord_server_name = Column(String)
    discord_id = Column(Integer, unique=True)
    date_of_payment = Column(Integer)  # Initial join/payment date
    last_date_of_payment = Column(Integer)  # Last payment date (for renewals)
    sub_time = Column(Integer)  # Subscription expiry timestamp
    warned_30_days = Column(Boolean, default=False)  # Whether user received 30-day warning


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# Migration script to add new columns to existing database
async def migrate_add_new_columns():
    """Add new columns to existing Users table"""
    try:
        async with engine.begin() as conn:
            # Add last_date_of_payment column if it doesn't exist
            try:
                await conn.execute(
                    "ALTER TABLE users ADD COLUMN last_date_of_payment INTEGER"
                )
                print("Added last_date_of_payment column")
            except Exception as e:
                print(f"last_date_of_payment column might already exist: {e}")
            
            # Add warned_30_days column if it doesn't exist
            try:
                await conn.execute(
                    "ALTER TABLE users ADD COLUMN warned_30_days BOOLEAN DEFAULT FALSE"
                )
                print("Added warned_30_days column")
            except Exception as e:
                print(f"warned_30_days column might already exist: {e}")
                
            # Update existing users to have last_date_of_payment = date_of_payment
            try:
                await conn.execute(
                    "UPDATE users SET last_date_of_payment = date_of_payment WHERE last_date_of_payment IS NULL"
                )
                print("Updated existing users with last_date_of_payment")
            except Exception as e:
                print(f"Error updating existing users: {e}")
                
    except Exception as e:
        print(f"Migration error: {e}")


##Delete Table
# async def drop_users_table():
#     async with engine.begin() as conn:
#         await conn.run_sync(Users.__table__.drop)
# asyncio.run(drop_users_table())

# Run migration and init
# asyncio.run(migrate_add_new_columns())
# asyncio.run(init_db()