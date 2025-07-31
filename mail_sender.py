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
        "Ти щойно зробив(ла) крок, який може змінити твою фриланс-кар'єру та допоможе вийти на стабільний дохід на західному ринку.\n\n"
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
        print(f"✓ Email sent successfully for order {order_reference} to {receiver_email}")
    except Exception as e:
        print(f"❌ Error sending email for order {order_reference}: {e}")
    finally:
        if server is not None:
            server.quit()


async def main():
    """Main mail service loop"""
    print("📧 Mail service started - monitoring for paid orders...")
    
    consecutive_errors = 0
    max_consecutive_errors = 5
    
    while True:
        try:
            orders = await select_orders_with_paid_status()
            
            if orders:
                print(f"📬 Found {len(orders)} paid orders to process")
                
                for order in orders:
                    order_reference = order['order_reference']
                    receiver_email = order['email']
                    discord_link = order['link']

                    # Try to update order status first (prevents duplicate emails)
                    updated = await update_order_status_by_order_reference_v2(order_reference, finished_order_status)
                    
                    if updated:
                        await send_mail(receiver_email, discord_link, order_reference)
                        print(f"✓ Order {order_reference} processed and email sent")
                    else:
                        print(f"⚠ Order {order_reference} was not updated (possibly already processed)")
                        
                # Reset error counter on successful processing
                consecutive_errors = 0
                
            else:
                # No orders to process - this is normal
                pass
                
        except Exception as e:
            consecutive_errors += 1
            print(f"❌ Error in mail service (attempt {consecutive_errors}/{max_consecutive_errors}): {e}")
            
            if consecutive_errors >= max_consecutive_errors:
                print(f"💀 Mail service failed {max_consecutive_errors} times consecutively. Stopping.")
                break
                
            # Wait longer after errors
            await asyncio.sleep(10)
            continue
        
        # Normal processing interval
        await asyncio.sleep(5)


def run_mail_service():
    """Run mail service in a thread-safe way"""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("📧 Mail service stopped by user")
    except Exception as e:
        print(f"💀 Mail service crashed: {e}")


if __name__ == "__main__":
    print("Starting mail service independently...")
    try:
        run_mail_service()
    except KeyboardInterrupt:
        print("Mail service stopped.")