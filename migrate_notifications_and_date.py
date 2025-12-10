"""
Migration script to:
1. Add customer_date_opened field to RMAs table
2. Update notification_preferences table to support weekly schedule and time selection
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import os

DATABASE_URL = os.environ.get("DATABASE_URL")

def migrate():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        print("Starting migration...")
        
        # 1. Add customer_date_opened to RMAs table
        print("Adding customer_date_opened column to rmas table...")
        cur.execute("""
            ALTER TABLE rmas 
            ADD COLUMN IF NOT EXISTS customer_date_opened DATE;
        """)
        
        # 2. Drop old notification_preferences columns and add new ones
        print("Updating notification_preferences table structure...")
        
        # Add new columns for weekly schedule
        cur.execute("""
            ALTER TABLE notification_preferences 
            ADD COLUMN IF NOT EXISTS notify_sunday BOOLEAN DEFAULT FALSE;
        """)
        
        cur.execute("""
            ALTER TABLE notification_preferences 
            ADD COLUMN IF NOT EXISTS notify_monday BOOLEAN DEFAULT FALSE;
        """)
        
        cur.execute("""
            ALTER TABLE notification_preferences 
            ADD COLUMN IF NOT EXISTS notify_tuesday BOOLEAN DEFAULT FALSE;
        """)
        
        cur.execute("""
            ALTER TABLE notification_preferences 
            ADD COLUMN IF NOT EXISTS notify_wednesday BOOLEAN DEFAULT FALSE;
        """)
        
        cur.execute("""
            ALTER TABLE notification_preferences 
            ADD COLUMN IF NOT EXISTS notify_thursday BOOLEAN DEFAULT FALSE;
        """)
        
        cur.execute("""
            ALTER TABLE notification_preferences 
            ADD COLUMN IF NOT EXISTS notify_friday BOOLEAN DEFAULT FALSE;
        """)
        
        cur.execute("""
            ALTER TABLE notification_preferences 
            ADD COLUMN IF NOT EXISTS notify_saturday BOOLEAN DEFAULT FALSE;
        """)
        
        # Add notification time column (stored as TIME type, e.g., '09:00:00')
        cur.execute("""
            ALTER TABLE notification_preferences 
            ADD COLUMN IF NOT EXISTS notification_time TIME DEFAULT '09:00:00';
        """)
        
        # Set default values for existing users (Monday as default day)
        print("Setting default notification preferences for existing users...")
        cur.execute("""
            UPDATE notification_preferences 
            SET notify_monday = TRUE
            WHERE notify_monday IS NULL OR notify_monday = FALSE;
        """)
        
        conn.commit()
        print("Migration completed successfully!")
        
    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    migrate()
