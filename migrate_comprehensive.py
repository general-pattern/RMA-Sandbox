"""
Database Migration Script - Comprehensive Update
Safely adds missing columns and updates schema
"""
import sqlite3
import sys

def safe_add_column(conn, table, column, definition):
    """Safely add a column if it doesn't exist"""
    cur = conn.cursor()
    try:
        # Check if column exists
        cur.execute(f"PRAGMA table_info({table})")
        columns = [col[1] for col in cur.fetchall()]
        
        if column not in columns:
            print(f"  Adding {table}.{column}...")
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            conn.commit()
            print(f"  ✅ Added {table}.{column}")
            return True
        else:
            print(f"  ⏭️  {table}.{column} already exists")
            return False
    except Exception as e:
        print(f"  ❌ Error adding {table}.{column}: {e}")
        return False

def migrate_database(db_path='rma.db'):
    """Run all migrations"""
    print(f"Starting migration of {db_path}...")
    
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()
    
    try:
        # 1. Add IsAdmin to users table
        print("\n1. Updating users table...")
        safe_add_column(conn, 'users', 'IsAdmin', 'INTEGER DEFAULT 0')
        
        # 2. Add credit tracking fields to rmas
        print("\n2. Adding credit tracking fields to rmas...")
        safe_add_column(conn, 'rmas', 'CreditAmount', 'REAL DEFAULT 0')
        safe_add_column(conn, 'rmas', 'CreditRejected', 'INTEGER DEFAULT 0')
        safe_add_column(conn, 'rmas', 'CreditRejectedOn', 'TEXT')
        safe_add_column(conn, 'rmas', 'CreditRejectedBy', 'INTEGER')
        safe_add_column(conn, 'rmas', 'CreditRejectionReason', 'TEXT')
        safe_add_column(conn, 'rmas', 'CreditIssuedOn', 'TEXT')
        safe_add_column(conn, 'rmas', 'AcknowledgedBy', 'INTEGER')
        
        # 3. Rename columns that need updating (from old schema)
        print("\n3. Checking for old column names...")
        cur.execute("PRAGMA table_info(rmas)")
        rma_columns = {col[1]: col for col in cur.fetchall()}
        
        if 'InternalOwnerID' in rma_columns and 'AssignedToUserID' not in rma_columns:
            print("  Found InternalOwnerID, needs migration...")
            # Need to recreate table to rename column
            print("  ⚠️  Manual intervention required - see migration notes")
        
        # 4. Create credit_history table
        print("\n4. Creating credit_history table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS credit_history (
                CreditHistID    INTEGER PRIMARY KEY AUTOINCREMENT,
                RMAID           INTEGER NOT NULL,
                Action          TEXT NOT NULL,
                Amount          REAL,
                MemoNumber      TEXT,
                ActionBy        INTEGER,
                ActionOn        TEXT NOT NULL,
                Comment         TEXT,
                FOREIGN KEY (RMAID) REFERENCES rmas(RMAID) ON DELETE CASCADE,
                FOREIGN KEY (ActionBy) REFERENCES users(UserID)
            )
        """)
        conn.commit()
        print("  ✅ credit_history table ready")
        
        # 5. Update any existing admin users
        print("\n5. Checking for existing admin users...")
        cur.execute("SELECT UserID, Role FROM users WHERE Role = 'admin'")
        admins = cur.fetchall()
        if admins:
            for admin in admins:
                cur.execute("UPDATE users SET IsAdmin = 1 WHERE UserID = ?", (admin[0],))
            conn.commit()
            print(f"  ✅ Updated {len(admins)} admin users")
        
        print("\n✅ Migration completed successfully!")
        conn.close()
        return True
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        conn.rollback()
        conn.close()
        return False

if __name__ == "__main__":
    db_file = sys.argv[1] if len(sys.argv) > 1 else 'rma.db'
    success = migrate_database(db_file)
    sys.exit(0 if success else 1)
