#!/usr/bin/env python3
"""
Migration script to add:
1. Multiple owners per RMA
2. Notification preferences for owners
3. Migrate existing single owner data
"""

import sqlite3
from datetime import datetime

DB_PATH = "rma.db"

def migrate_database():
    print("Starting database migration for multiple owners and notifications...")
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    try:
        # ===== CREATE RMA_OWNERS TABLE =====
        print("\n1. Creating rma_owners table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS rma_owners (
                RMAOwnerID      INTEGER PRIMARY KEY AUTOINCREMENT,
                RMAID           INTEGER NOT NULL,
                OwnerID         INTEGER NOT NULL,
                IsPrimary       INTEGER DEFAULT 0,
                AssignedOn      TEXT NOT NULL,
                AssignedBy      INTEGER,
                FOREIGN KEY (RMAID) REFERENCES rmas(RMAID) ON DELETE CASCADE,
                FOREIGN KEY (OwnerID) REFERENCES internal_owners(OwnerID) ON DELETE CASCADE,
                FOREIGN KEY (AssignedBy) REFERENCES users(UserID),
                UNIQUE(RMAID, OwnerID)
            )
        """)
        print("   ✓ rma_owners table created")
        
        # ===== CREATE OWNER_NOTIFICATION_PREFERENCES TABLE =====
        print("\n2. Creating owner_notification_preferences table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS owner_notification_preferences (
                PrefID          INTEGER PRIMARY KEY AUTOINCREMENT,
                OwnerID         INTEGER NOT NULL UNIQUE,
                EmailEnabled    INTEGER DEFAULT 1,
                Frequency       TEXT DEFAULT 'daily',
                RMAAge          INTEGER DEFAULT 3,
                LastSent        TEXT,
                FOREIGN KEY (OwnerID) REFERENCES internal_owners(OwnerID) ON DELETE CASCADE
            )
        """)
        print("   ✓ owner_notification_preferences table created")
        
        # ===== MIGRATE EXISTING OWNER DATA =====
        print("\n3. Migrating existing owner assignments...")
        
        # Get all RMAs that have an owner
        cur.execute("""
            SELECT RMAID, InternalOwnerID, DateOpened 
            FROM rmas 
            WHERE InternalOwnerID IS NOT NULL
        """)
        existing_rmas = cur.fetchall()
        
        migrated_count = 0
        for rma in existing_rmas:
            try:
                cur.execute("""
                    INSERT OR IGNORE INTO rma_owners (RMAID, OwnerID, IsPrimary, AssignedOn)
                    VALUES (?, ?, 1, ?)
                """, (rma['RMAID'], rma['InternalOwnerID'], rma['DateOpened']))
                if cur.rowcount > 0:
                    migrated_count += 1
            except sqlite3.IntegrityError:
                # Already exists, skip
                pass
        
        print(f"   ✓ Migrated {migrated_count} existing owner assignments")
        
        # ===== CREATE DEFAULT NOTIFICATION PREFERENCES =====
        print("\n4. Creating default notification preferences for all owners...")
        
        # Get all owners
        cur.execute("SELECT OwnerID FROM internal_owners")
        owners = cur.fetchall()
        
        prefs_created = 0
        for owner in owners:
            try:
                cur.execute("""
                    INSERT OR IGNORE INTO owner_notification_preferences 
                    (OwnerID, EmailEnabled, Frequency, RMAAge)
                    VALUES (?, 1, 'daily', 3)
                """, (owner['OwnerID'],))
                if cur.rowcount > 0:
                    prefs_created += 1
            except sqlite3.IntegrityError:
                pass
        
        print(f"   ✓ Created notification preferences for {prefs_created} owners")
        
        # ===== CREATE INDEXES =====
        print("\n5. Creating indexes for better performance...")
        
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_rma_owners_rmaid 
            ON rma_owners(RMAID)
        """)
        
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_rma_owners_ownerid 
            ON rma_owners(OwnerID)
        """)
        
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_rma_owners_primary 
            ON rma_owners(IsPrimary)
        """)
        
        print("   ✓ Indexes created")
        
        # ===== COMMIT CHANGES =====
        conn.commit()
        print("\n" + "="*60)
        print("✓ Database migration completed successfully!")
        print("="*60)
        print("\nSummary:")
        print(f"  • rma_owners table created with {migrated_count} existing assignments")
        print(f"  • owner_notification_preferences created for {prefs_created} owners")
        print(f"  • All indexes created")
        print("\nNext steps:")
        print("  1. Update app.py with new routes")
        print("  2. Restart Flask application")
        print("  3. Owners can customize notification preferences in their profile")
        
    except Exception as e:
        conn.rollback()
        print(f"\n✗ Error during migration: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_database()
