import smtplib
import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from sql_scripts import *
from config import *


async def extract_name_from_email(email: str) -> str:
    local_part = email.split('@')[0]
    parts = local_part.split('.')
    name = ' '.join(part.capitalize() for part in parts)
    return name


async def send_mail(receiver_email: str, discord_link: str, order_reference: str) -> None:
    smtp_server = "localhost"
    smtp_port = 25
    # если необходимо, задайте username и password для smtp (здесь они не используются)
    sender_email = "info@mail.upworkrevolution.com"
    subject = "Доступ до Discord каналу"

    receiver_name = await extract_name_from_email(receiver_email)

    body = (
        f"Привіт, {receiver_name}!\n\n"
        "Дякуємо за покупку доступу до community Upwork Revolution!\n"
        "Ти щойно зробив(ла) крок, який може змінити твою фриланс-кар’єру та допоможе вийти на стабільний дохід на західному ринку.\n\n"
        "📩 Ось запрошення на сервер:\n"
        f"🔗 Перейти в Discord: {discord_link}\n\n"
        "Побачимось всередині Upwork Revolution!\n\n"
        "З повагою,\n"
        "Upwork Revolution"
    )

    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = receiver_email
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain"))

    server = None
    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.sendmail(sender_email, receiver_email, message.as_string())
        print(f"The letter was successfully sent according to the order {order_reference}!")
    except Exception as e:
        print(f"Error sending email to the order {order_reference}:", e)
    finally:
        if server is not None:
            server.quit()


async def main():
    print("WORKING")
    while True:
        try:
            orders = await select_orders_with_paid_status()
            print(orders)
            if orders:
                for order in orders:
                    order_reference = order['order_reference']
                    receiver_email = order['email']
                    discord_link = order['link']

                    updated = await update_order_status_by_order_reference_v2(order_reference, finished_order_status)
                    if updated:
                        await send_mail(receiver_email, discord_link, order_reference)
                        print(f"Order {order_reference} updated and mail sent.")
                    else:
                        print(f"Order {order_reference} was not updated (possibly already processed) - skipping.")
        except Exception as e:
            print(f"Error in main: {e}")
        await asyncio.sleep(5)



if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Mailing bot is off.")