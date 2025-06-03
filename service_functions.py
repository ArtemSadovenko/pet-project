import asyncio
import random
from sql_scripts import *


async def generate_unique_order_id(all_orders_id, length=10) -> str:
    existing_ids = set(all_orders_id)
    while True:
        order_id = ''.join(random.choices('0123456789', k=length))
        if order_id not in existing_ids:
            return order_id


async def add_new_order(email, join_link, amount, sub_time):
    try:

        all_orders_id = []
        all_orders_list = await select_orders()

        for order in all_orders_list:
            all_orders_id.append(order['order_id'])

        new_order_id = await generate_unique_order_id(all_orders_id)

        await add_order(int(new_order_id), email, join_link, amount=amount, sub_time=int(sub_time), order_status=0)

        return int(new_order_id)
    except Exception as error:
        print(f"Error in service_functions > add_new_order: {error}")


async def add_order_reference_sql(order_id, order_reference):
    try:
        await update_user_order_reference(order_id, order_reference)
    except Exception as e:
        print(f"Error in service_functions > add_order_reference_sql: {e}")


async def update_order_status_sql(order_reference, new_status):
    try:
        await update_order_status_by_order_reference(order_reference, new_status)
    except Exception as e:
        print(f"Error in service_functions > update_order_status_sql: {e}")


async def delete_order_sql(order_reference):
    try:
        await delete_order_by_order_reference(order_reference)
    except Exception as e:
        print(f"Error in service_functions > delete_order_sql: {e}")
