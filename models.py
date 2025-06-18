import logging
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker, class_mapper
from sqlalchemy import Column, Integer, String, BigInteger, Float, insert, update, delete, Float
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
    date_of_payment = Column(Integer)
    last_date_of_payment = Column(Integer)
    sub_time = Column(Integer)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


##Delete Table
# async def drop_users_table():
#     async with engine.begin() as conn:
#         await conn.run_sync(Users.__table__.drop)
# asyncio.run(drop_users_table())

# asyncio.run(init_db())