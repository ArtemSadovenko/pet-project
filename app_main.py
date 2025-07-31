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
from scheduler import run_scheduler  # Import the scheduler

app = Flask(__name__)

# Main bot for invites and general functionality
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
        future = asyncio.run_coroutine_threadsafe(generate_invite(), bot.loop)
        invite_url = future.result(timeout=10)

        future = asyncio.run_coroutine_threadsafe(
            add_new_order(email, invite_url, amount_value, sub_time), 
            bot.loop
        )
        order_id = future.result(timeout=10)

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
        
        future = asyncio.run_coroutine_threadsafe(
            add_order_reference_sql(order_id, order_reference), 
            bot.loop
        )
        future.result(timeout=10)

        if not invoice_result:
            raise Exception("Failed to create transaction via WayForPay")

        return redirect(invoice_result.invoiceUrl)

    except Exception as e:
        print(f"Error creating yearly order: {e}")
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
        future = asyncio.run_coroutine_threadsafe(generate_invite(), bot.loop)
        invite_url = future.result(timeout=10)

        future = asyncio.run_coroutine_threadsafe(
            add_new_order(email, invite_url, amount_value, sub_time), 
            bot.loop
        )
        order_id = future.result(timeout=10)

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
        
        future = asyncio.run_coroutine_threadsafe(
            add_order_reference_sql(order_id, order_reference), 
            bot.loop
        )
        future.result(timeout=10)

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
    
    json_str = ''
    keys = list(form_data.keys())
    
    if keys:
        json_str = keys[0]
    else:
        # Try to get raw data
        json_str = request.get_data(as_text=True)
        if not json_str:
            return "No data", 400

    try:
        parsed_data = json.loads(json_str)
    except Exception as e:
        print(f"Error parsing JSON from callback: {e}")
        print(f"Raw data received: {json_str}")
        return "Invalid JSON", 400

    print("Callback success - parsed_data:", parsed_data)
    
    tx_status = parsed_data.get('transactionStatus')
    if tx_status == "Declined":
        print("Transaction declined")
        return "OK", 200
    
    order_reference = parsed_data.get("orderReference")
    print("order_reference:", order_reference)

    if not order_reference:
        return "orderReference not found", 400
        
    user_email = parsed_data.get("email")
    new_date = parsed_data.get("processingDate")
    
    try:
        # Update user payment date if available
        if user_email and new_date:
            # Convert processing date to timestamp if needed
            if isinstance(new_date, str):
                try:
                    # Assume format is Unix timestamp or convert if needed
                    payment_timestamp = int(new_date) if new_date.isdigit() else int(time.time())
                except:
                    payment_timestamp = int(time.time())
            else:
                payment_timestamp = int(new_date)
                
            future = asyncio.run_coroutine_threadsafe(
                update_user_last_payment_date_sql(user_email, payment_timestamp), 
                bot.loop
            )
            result = future.result(timeout=10)
            print(f"Updated payment date for {user_email}: {payment_timestamp}")
        
        # Update order status
        future = asyncio.run_coroutine_threadsafe(
            update_order_status_sql(order_reference, paid_order_status), 
            bot.loop
        )
        result = future.result(timeout=10)
        print(f"Updated order status for {order_reference}")
        
    except Exception as e:
        print(f"Error updating database in callback_success: {e}")
        return "Database error", 500

    return "OK", 200

@app.route("/callback_failure", methods=["POST"])
def callback_failure():
    data = request.form if request.form else request.get_json()
    if not data:
        return "No data", 400

    order_reference = data.get("orderReference")
    if not order_reference:
        return "orderReference not found", 400

    try:
        future = asyncio.run_coroutine_threadsafe(
            delete_order_sql(order_reference), 
            bot.loop
        )
        future.result(timeout=10)
        print(f"Deleted failed order: {order_reference}")
    except Exception as e:
        print(f"Error deleting order in callback_failure: {e}")
        return "Database error", 500

    return "OK", 200

def run_bot():
    """Run the main Discord bot"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        bot.run(bot_token)
    except Exception as e:
        print(f"Error running main bot: {e}")

def run_flask():
    """Run Flask application"""
    app.run(debug=True, use_reloader=False, host='0.0.0.0', port=5000)

if __name__ == '__main__':
    # Start the scheduler first
    print("Starting scheduler...")
    scheduler_thread = run_scheduler()
    
    # Start the main bot in a separate thread
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    print("Main bot thread started")
    
    # Small delay to ensure bots are starting up
    time.sleep(2)
    
    # Run Flask in the main thread
    print("Starting Flask application...")
    run_flask()