import time
import asyncio
import threading
import discord
import json
from discord.ext import commands
from flask import Flask, request, render_template, redirect, url_for
from service_functions import add_new_order, add_order_reference_sql, update_order_status_sql, delete_order_sql, update_user_last_payment_date_sql
from wayforpay import WayForPay
from config import *
from schedure import *

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

@app.route("/payment_year", methods=["GET", "POST"])
def payment_yearly():
    if request.method == "GET":
        return redirect(url_for("index"))

    email = request.form.get("email")
    amount_value = COST_VALUE_YEARLY
    sub_time = request.form.get('sub_time') or 365
    currency = "USD"
    sub_period = int(int(sub_time) / 30)

    if not email:
        response = redirect(url_for("index"))
        response.status_code = 400
        return response

    try:
        invite_url = generate_invite()

        order_id = add_new_order(email, invite_url, amount_value, sub_time)

        merchant_domain = "upworkrevolution.com"
        wfp = WayForPay(MERCHANT_SECRET, merchant_domain)

        invoice_result = wfp.create_yearly_invoice(
            merchantAccount=MERCHANT_ID,
            merchantAuthType="SimpleSignature",
            amount=amount_value,
            currency=currency,
            productNames=["Оплата доступу до закритого Discord-каналу Community Upwork Revolution"],
            productPrices=[amount_value],
            productCounts=[1],
            recurring="true",
            subscriptionPeriod=f"{sub_period}"
        )

        order_reference = invoice_result.orderReference
        add_order_reference_sql(order_id, order_reference)

        if not invoice_result:
            raise Exception("Failed to create transaction via WayForPay")

        return redirect(invoice_result.invoiceUrl)

    except Exception as e:
        print(f"Error creating order: {e}")
        response = redirect(url_for("index"))
        response.status_code = 501
        return response
    
@app.route("/payment", methods=["GET", "POST"])
def payment():
    if request.method == "GET":
        return redirect(url_for("index"))

    email = request.form.get("email")
    amount_value = COST_VALUE
    sub_time = request.form.get('sub_time') or 365
    currency = "USD"
    sub_period = int(int(sub_time) / 30)

    if not email:
        response = redirect(url_for("index"))
        response.status_code = 400
        return response

    try:
        invite_url = generate_invite()

        order_id = add_new_order(email, invite_url, amount_value, sub_time)

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
            subscriptionPeriod=f"{sub_period}"
        )

        order_reference = invoice_result.orderReference
        add_order_reference_sql(order_id, order_reference)

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

# http://upworkrevolution.com/callback_success
@app.route("/callback_success", methods=["POST"])
def callback_success():
    form_data = request.form
    
    keys = list(form_data.keys())
    json_str = ''
    if keys:
        json_str = keys[0]
    if not keys:
        json_str = request.data
    else:
        print(f"Unable to parce data: {form_data}")
        return "No data", 400
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
        user_email = parsed_data.get("email")
        new_date = parsed_data.get("processingDate")
        asyncio.run(update_user_last_payment_date_sql(user_email, new_date))
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

def run_scheduler():
    import schedure
    schedure.run_scheduler()

def run_flask():
    app.run(host='0.0.0.0', port=5000)


if __name__ == '__main__':
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    run_bot() 

