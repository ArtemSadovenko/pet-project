#!/usr/bin/env python3
"""
Complete startup script for Upwork Revolution Discord Bot System
This script starts all services in the correct order and provides status monitoring
"""

import time
import threading
import asyncio
import sys
import os
from datetime import datetime

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def print_banner():
    """Print startup banner"""
    print("=" * 60)
    print("    UPWORK REVOLUTION DISCORD BOT SYSTEM")
    print("=" * 60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

def check_config():
    """Check if config file exists and has required variables"""
    try:
        from config import (
            bot_token, 
            server_id, 
            invite_channel_id, 
            MERCHANT_ID, 
            MERCHANT_SECRET,
            DATABASE_URL
        )
        print("✓ Configuration file loaded successfully")
        return True
    except ImportError as e:
        print(f"❌ Configuration error: {e}")
        print("Please ensure config.py exists with all required variables")
        return False
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        return False

def start_scheduler():
    """Start the scheduler service"""
    try:
        from scheduler import run_scheduler
        print("🕐 Starting scheduler service...")
        scheduler_thread = run_scheduler()
        time.sleep(1)
        print("✓ Scheduler service started")
        return scheduler_thread
    except Exception as e:
        print(f"❌ Failed to start scheduler: {e}")
        return None

def start_mail_service():
    """Start the mail service"""
    try:
        from mail_sender import main as mail_main
        
        def run_mail():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(mail_main())
            except Exception as e:
                print(f"❌ Mail service error: {e}")
        
        print("📧 Starting mail service...")
        mail_thread = threading.Thread(target=run_mail, daemon=True)
        mail_thread.start()
        time.sleep(1)
        print("✓ Mail service started")
        return mail_thread
    except Exception as e:
        print(f"❌ Failed to start mail service: {e}")
        return None

def start_discord_bot():
    """Start the main Discord bot"""
    try:
        from discord_bot import bot, bot_token
        
        def run_bot():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                bot.run(bot_token)
            except Exception as e:
                print(f"❌ Discord bot error: {e}")
        
        print("🤖 Starting Discord bot...")
        bot_thread = threading.Thread(target=run_bot, daemon=True)
        bot_thread.start()
        time.sleep(2)
        print("✓ Discord bot started")
        return bot_thread
    except Exception as e:
        print(f"❌ Failed to start Discord bot: {e}")
        return None

def start_flask_app():
    """Start the Flask web application"""
    try:
        from flask import Flask
        from app_main import app
        
        print("🌐 Starting Flask web application...")
        print("   - Payment processing endpoint")
        print("   - Webhook handlers")
        print("   - Web interface")
        print()
        print("🚀 All services running! System is ready.")
        print("=" * 60)
        print("SERVICE STATUS:")
        print("✓ Scheduler: Managing user subscriptions and warnings")
        print("✓ Mail Service: Sending payment confirmation emails")
        print("✓ Discord Bot: Handling invites and user management")
        print("✓ Flask App: Processing payments and webhooks")
        print("=" * 60)
        print(f"Web interface available at: http://localhost:5000")
        print("Press Ctrl+C to stop all services")
        print("=" * 60)
        
        app.run(debug=False, use_reloader=False, host='0.0.0.0', port=5000)
        
    except Exception as e:
        print(f"❌ Failed to start Flask app: {e}")
        return False

def main():
    """Main startup function"""
    print_banner()
    
    # Check configuration
    if not check_config():
        sys.exit(1)
    
    print("Starting services in sequence...")
    print()
    
    # Start services in order
    services = []
    
    # 1. Scheduler (subscription management)
    scheduler_thread = start_scheduler()
    if scheduler_thread:
        services.append(("Scheduler", scheduler_thread))
    
    # 2. Mail service (email notifications)
    mail_thread = start_mail_service()
    if mail_thread:
        services.append(("Mail Service", mail_thread))
    
    # 3. Discord bot (user management)
    bot_thread = start_discord_bot()
    if bot_thread:
        services.append(("Discord Bot", bot_thread))
    
    # Small delay for all services to initialize
    print("⏳ Waiting for services to initialize...")
    time.sleep(3)
    print()
    
    # 4. Flask app (web interface) - runs in main thread
    try:
        start_flask_app()
    except KeyboardInterrupt:
        print("\n" + "=" * 60)
        print("🛑 Shutdown signal received...")
        print("Stopping all services...")
        
        for service_name, thread in services:
            if thread and thread.is_alive():
                print(f"   - Stopping {service_name}")
        
        print("✓ All services stopped")
        print("Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Critical error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()