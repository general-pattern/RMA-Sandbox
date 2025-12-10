
#!/usr/bin/env python3
"""
Consolidate internal_owners into users table - SAFE VERSION
Works whether tables exist or not
"""

import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash

DB_PATH = "rma.db"

def migrate():
    print("="*70)
    print("🔄 Consolidating internal_owners into users...")
    print("="*70)
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    try:
        # 1. Add IsOwner column to users
        print("\n1️⃣ Adding IsOwner column to users...")
        try:
            cur.execute("ALTER TABLE users ADD COLUMN IsOwner INTEGER DEFAULT 0")
            print("   ✓ IsOwner column added")
        except sqlite3.OperationalError:
            print("   ✓ IsOwner already exists")
        
        # 2. Add AssignedToUserID column to rmas
        print("\n2️⃣ Adding AssignedToUserID column to rmas...")
        try:
            cur.execute("ALTER TABLE rmas ADD COLUMN AssignedToUserID INTEGER")
            print("   ✓ AssignedToUserID column added")
        except sqlite3.OperationalError:
            print("   ✓ AssignedToUserID already exists")
        
        # 3. Create rma_owners table if it doesn't exist
        print("\n3️⃣ Creating rma_owners table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS rma_owners (
                RMAOwnerID      INTEGER PRIMARY KEY AUTOINCREMENT,
                RMAID           INTEGER NOT NULL,
                UserID          INTEGER NOT NULL,
                IsPrimary       INTEGER DEFAULT 0,
                AssignedOn      TEXT NOT NULL,
                AssignedBy      INTEGER,
                FOREIGN KEY (RMAID) REFERENCES rmas(RMAID) ON DELETE CASCADE,
                FOREIGN KEY (UserID) REFERENCES users(UserID) ON DELETE CASCADE,
                FOREIGN KEY (AssignedBy) REFERENCES users(UserID),
                UNIQUE(RMAID, UserID)
            )
        """)
        print("   ✓ rma_owners table ready")
        
        # 4. Create notification preferences table
        print("\n4️⃣ Creating owner_notification_preferences table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS owner_notification_preferences (
                PrefID          INTEGER PRIMARY KEY AUTOINCREMENT,
                UserID          INTEGER NOT NULL UNIQUE,
                EmailEnabled    INTEGER DEFAULT 1,
                Frequency       TEXT DEFAULT 'daily',
                RMAAge          INTEGER DEFAULT 3,
                LastSent        TEXT,
                FOREIGN KEY (UserID) REFERENCES users(UserID) ON DELETE CASCADE
            )
        """)
        print("   ✓ owner_notification_preferences table ready")
        
        # 5. Migrate internal_owners if table exists
        print("\n5️⃣ Migrating internal owners (if any)...")
        try:
            cur.execute("SELECT * FROM internal_owners")
            owners = cur.fetchall()
            print(f"   Found {len(owners)} owners to migrate")
            
            migrated = 0
            created = 0
            
            for owner in owners:
                owner_email = owner['OwnerEmail']
                owner_name = owner['OwnerName']
                owner_id = owner['OwnerID']
                
                # Check if user exists
                cur.execute("SELECT UserID FROM users WHERE Email = ?", (owner_email,))
                existing_user = cur.fetchone()
                
                if existing_user:
                    cur.execute("UPDATE users SET IsOwner = 1 WHERE Email = ?", (owner_email,))
                    user_id = existing_user['UserID']
                    print(f"   ✓ Marked existing user as owner: {owner_name}")
                    migrated += 1
                else:
                    username = owner_email.split('@')[0]
                    cur.execute("SELECT UserID FROM users WHERE Username = ?", (username,))
                    if cur.fetchone():
                        username = f"{username}_{owner_id}"
                    
                    password_hash = generate_password_hash("ChangeMe123!")
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    cur.execute("""
                        INSERT INTO users (Username, PasswordHash, FullName, Email, Role, IsOwner, CreatedOn)
                        VALUES (?, ?, ?, ?, 'user', 1, ?)
                    """, (username, password_hash, owner_name, owner_email, now))
                    
                    user_id = cur.lastrowid
                    print(f"   ✓ Created user: {owner_name} (password: ChangeMe123!)")
                    created += 1
                
                # Update AssignedToUserID
                cur.execute("""
                    UPDATE rmas SET AssignedToUserID = ? WHERE InternalOwnerID = ?
                """, (user_id, owner_id))
            
            print(f"   Summary: {migrated} marked as owners, {created} created")
            
            # Drop internal_owners
            cur.execute("DROP TABLE IF EXISTS internal_owners")
            print("   ✓ Dropped internal_owners table")
            
        except sqlite3.OperationalError:
            print("   ✓ No internal_owners table found (already migrated)")
        
        # 6. Create indexes
        print("\n6️⃣ Creating indexes...")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_users_isowner ON users(IsOwner)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_rmas_assigned ON rmas(AssignedToUserID)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_rma_owners_rmaid ON rma_owners(RMAID)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_rma_owners_userid ON rma_owners(UserID)")
        print("   ✓ Indexes created")
        
        conn.commit()
        
        print("\n" + "="*70)
        print("✅ Migration completed successfully!")
        print("="*70)
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()