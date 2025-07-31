#!/usr/bin/env python3
"""
Database migration script to add new columns and update existing data
Run this script once before starting the updated application
"""

import asyncio
import time
from sqlalchemy import text
from models import engine, async_session, Users
from sqlalchemy import select

async def migrate_database():
    """Run all database migrations"""
    print("Starting database migration...")
    
    try:
        async with engine.begin() as conn:
            print("1. Adding last_date_of_payment column...")
            try:
                await conn.execute(text(
                    "ALTER TABLE users ADD COLUMN last_date_of_payment INTEGER"
                ))
                print("   ✓ Added last_date_of_payment column")
            except Exception as e:
                if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
                    print("   ✓ last_date_of_payment column already exists")
                else:
                    print(f"   ⚠ Error adding last_date_of_payment: {e}")
            
            print("2. Adding warned_30_days column...")
            try:
                await conn.execute(text(
                    "ALTER TABLE users ADD COLUMN warned_30_days BOOLEAN DEFAULT FALSE"
                ))
                print("   ✓ Added warned_30_days column")
            except Exception as e:
                if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
                    print("   ✓ warned_30_days column already exists")
                else:
                    print(f"   ⚠ Error adding warned_30_days: {e}")
    
    except Exception as e:
        print(f"Error during column addition: {e}")
        return False

    # Update existing data
    print("3. Updating existing user data...")
    try:
        async with async_session() as session:
            # Update users who don't have last_date_of_payment set
            result = await session.execute(
                text("UPDATE users SET last_date_of_payment = date_of_payment WHERE last_date_of_payment IS NULL")
            )
            updated_count = result.rowcount
            print(f"   ✓ Updated {updated_count} users with last_date_of_payment")
            
            # Set default values for warned_30_days
            result = await session.execute(
                text("UPDATE users SET warned_30_days = FALSE WHERE warned_30_days IS NULL")
            )
            updated_count = result.rowcount
            print(f"   ✓ Updated {updated_count} users with warned_30_days default")
            
            await session.commit()
            
    except Exception as e:
        print(f"Error updating existing data: {e}")
        return False

    print("4. Verifying migration...")
    try:
        async with async_session() as session:
            # Count users
            result = await session.execute(select(Users))
            users = result.scalars().all()
            
            users_with_payment_date = 0
            users_with_warning_flag = 0
            
            for user in users:
                if hasattr(user, 'last_date_of_payment') and user.last_date_of_payment is not None:
                    users_with_payment_date += 1
                if hasattr(user, 'warned_30_days'):
                    users_with_warning_flag += 1
            
            print(f"   ✓ Total users: {len(users)}")
            print(f"   ✓ Users with last_date_of_payment: {users_with_payment_date}")
            print(f"   ✓ Users with warned_30_days field: {users_with_warning_flag}")
            
            if len(users) > 0:
                print("   ✓ Sample user data:")
                sample_user = users[0]
                print(f"     - Discord ID: {sample_user.discord_id}")
                print(f"     - Email: {sample_user.email}")
                print(f"     - Date of payment: {sample_user.date_of_payment}")
                print(f"     - Last date of payment: {getattr(sample_user, 'last_date_of_payment', 'NOT SET')}")
                print(f"     - Warned 30 days: {getattr(sample_user, 'warned_30_days', 'NOT SET')}")
                
    except Exception as e:
        print(f"Error during verification: {e}")
        return False
    
    print("\n✅ Database migration completed successfully!")
    print("\nYou can now start your application with the updated features:")
    print("- 30-day payment warnings")
    print("- 40-day subscription expiry with kick")
    print("- Grace period for new users")
    print("- Fixed instant deletion bug")
    
    return True


async def check_database_status():
    """Check current database status"""
    print("Checking current database status...")
    
    try:
        async with async_session() as session:
            result = await session.execute(select(Users))
            users = result.scalars().all()
            
            print(f"Total users in database: {len(users)}")
            
            if len(users) > 0:
                current_time = int(time.time())
                
                # Analyze user statuses
                active_users = 0
                warning_users = 0
                expired_users = 0
                
                for user in users:
                    if hasattr(user, 'last_date_of_payment') and user.last_date_of_payment:
                        days_since_payment = (current_time - user.last_date_of_payment) / 86400
                    elif user.date_of_payment:
                        days_since_payment = (current_time - user.date_of_payment) / 86400
                    else:
                        days_since_payment = 999  # Very old
                    
                    if days_since_payment < 30:
                        active_users += 1
                    elif days_since_payment < 40:
                        warning_users += 1
                    else:
                        expired_users += 1
                
                print(f"Active users (< 30 days): {active_users}")
                print(f"Warning period users (30-40 days): {warning_users}")
                print(f"Expired users (> 40 days): {expired_users}")
                
    except Exception as e:
        print(f"Error checking database status: {e}")


if __name__ == "__main__":
    print("=== Discord Bot Database Migration ===")
    print("This script will update your database to support:")
    print("- 30-day payment warnings")
    print("- 40-day expiry with user kick")
    print("- Fixed instant deletion bug")
    print()
    
    # Check current status
    asyncio.run(check_database_status())
    print()
    
    # Ask for confirmation
    response = input("Do you want to proceed with the migration? (y/N): ")
    if response.lower() != 'y':
        print("Migration cancelled.")
        exit(0)
    
    # Run migration
    success = asyncio.run(migrate_database())
    
    if success:
        print("\n🎉 Migration completed! You can now start your updated application.")
    else:
        print("\n❌ Migration failed. Please check the errors above and try again.")
        exit(1)