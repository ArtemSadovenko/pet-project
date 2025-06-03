import time
import asyncio
import threading
import discord
import json
from discord.ext import commands
from flask import Flask, request, render_template, redirect, url_for
from service_functions import add_new_order, add_order_reference_sql, update_order_status_sql, delete_order_sql
from wayforpay import WayForPay
from config import *


app = Flask(__name__)


intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
guild_invites = {}


async def generate_invite() -> str:
    await bot.wait_until_ready()
    channel = bot.get_channel(invite_channel_id)
    if channel is None:
        raise Exception("Channel for generating invite not found. Check invite_channel_id in config.")
    try:
        invite = await channel.create_invite(max_uses=1, unique=True)
        guild = channel.guild
        if guild.id in guild_invites:
            guild_invites[guild.id][invite.code] = invite.uses
        else:
            guild_invites[guild.id] = {invite.code: invite.uses}
        return invite.url
    except Exception as e:
        raise Exception(f"Error creating invite: {e}")


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/payment", methods=["GET", "POST"])
def payment():
    if request.method == "GET":
        return redirect(url_for("index"))

    email = request.form.get("email")
    amount_value = request.form.get('sub_price')
    sub_time = request.form.get('sub_time')
    # amount_value = '0.15'
    # sub_time = 365

    currency = "USD"

    sub_period = int(int(sub_time) / 30)

    if not email:
        response = redirect(url_for("index"))
        response.status_code = 400
        return response

    try:
        future = asyncio.run_coroutine_threadsafe(generate_invite(), bot.loop)
        invite_url = future.result(timeout=10)

        order_id = asyncio.run(add_new_order(email, invite_url, amount_value, sub_time))

        merchant_domain = "upworkrevolution.com"
        wfp = WayForPay(MERCHANT_SECRET, merchant_domain)

        invoice_result = wfp.create_invoice(
            merchantAccount=MERCHANT_ID,
            merchantAuthType="SimpleSignature",
            amount=amount_value,
            currency=currency,
            productNames=["Оплата доступу до закритого Discord-каналу Community Upwork Revolution"],
            productPrices=[amount_value],
            productCounts=[1],
            recurring="true",
            subscriptionPeriod=f"{sub_period}"  # in month, 1 month, 12 month on sub period
        )

        order_reference = invoice_result.orderReference

        asyncio.run(add_order_reference_sql(order_id, order_reference))

        if not invoice_result:
            raise Exception("Failed to create transaction via WayForPay")

        return redirect(invoice_result.invoiceUrl)

    except Exception as e:
        print(f"Error creating order: {e}")
        response = redirect(url_for("index"))
        response.status_code = 501
        return response


@app.route("/response", methods=["GET", "POST"])
def response():
    return "Payment completed. Thank you!"


@app.route("/callback_success", methods=["POST"])
def callback_success():
    form_data = request.form

    keys = list(form_data.keys())
    if not keys:
        return "No data", 400

    json_str = keys[0]

    try:
        parsed_data = json.loads(json_str)
    except Exception as e:
        print(f"Ошибка парсинга JSON из form: {e}")
        return "Invalid JSON", 400

    print("parsed_data:", parsed_data)
    tx_status = parsed_data.get('transactionStatus')
    if tx_status == "Declined":
        return "OK", 200
    else:
        order_reference = parsed_data.get("orderReference")
        print("order_reference:", order_reference)

        if not order_reference:
            return "orderReference not found", 400

        asyncio.run(update_order_status_sql(order_reference, paid_order_status))

    return "OK", 200


@app.route("/callback_failure", methods=["POST"])
def callback_failure():
    data = request.form or request.get_json()
    if not data:
        return "No data", 400

    order_reference = data.get("orderReference")
    if not order_reference:
        return "orderReference not found", 400

    asyncio.run(delete_order_sql(order_reference))

    return "OK", 200


def run_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    bot.run(bot_token)

def run_scheduler():
    import schedure
    schedure.run_scheduler()


if __name__ == '__main__':
    threading.Thread(target=run_bot).start()
    threading.Thread(target=run_scheduler).start()
    app.run(debug=True)

