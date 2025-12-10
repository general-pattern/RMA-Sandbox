import sqlite3

# This script adds columns to your existing database so it matches what app.py expects

conn = sqlite3.connect('rma.db')
cur = conn.cursor()

print("Adding missing columns to match app.py...")

# Add Complaint column (copy from CustomerComplaintDesc)
try:
    cur.execute("ALTER TABLE rmas ADD COLUMN Complaint TEXT")
    cur.execute("UPDATE rmas SET Complaint = CustomerComplaintDesc")
    print("✅ Added Complaint column")
except sqlite3.OperationalError as e:
    print(f"⚠️ Complaint column: {e}")

# Add RootCause column
try:
    cur.execute("ALTER TABLE rmas ADD COLUMN RootCause TEXT")
    print("✅ Added RootCause column")
except sqlite3.OperationalError as e:
    print(f"⚠️ RootCause column: {e}")

# Add CorrectiveAction column
try:
    cur.execute("ALTER TABLE rmas ADD COLUMN CorrectiveAction TEXT")
    print("✅ Added CorrectiveAction column")
except sqlite3.OperationalError as e:
    print(f"⚠️ CorrectiveAction column: {e}")

# Add DispositionStatus column
try:
    cur.execute("ALTER TABLE rmas ADD COLUMN DispositionStatus TEXT")
    print("✅ Added DispositionStatus column")
except sqlite3.OperationalError as e:
    print(f"⚠️ DispositionStatus column: {e}")

# Create line_items table (app.py expects this instead of rma_lines)
try:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS line_items (
            LineItemID INTEGER PRIMARY KEY AUTOINCREMENT,
            RMAID INTEGER NOT NULL,
            PartNumber TEXT,
            ToolNumber TEXT,
            ItemDescription TEXT,
            QtyAffected INTEGER,
            POLotNumber TEXT,
            TotalCost REAL,
            FOREIGN KEY (RMAID) REFERENCES rmas(RMAID) ON DELETE CASCADE
        )
    """)
    
    # Copy existing data from rma_lines if it exists
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='rma_lines'")
    if cur.fetchone():
        cur.execute("""
            INSERT INTO line_items (RMAID, PartNumber, ToolNumber, ItemDescription, QtyAffected, POLotNumber, TotalCost)
            SELECT RMAID, PartNumber, ToolNumber, ItemDescription, QtyAffected, POLotNumber, TotalCost
            FROM rma_lines
        """)
        print("✅ Created line_items table and copied data from rma_lines")
    else:
        print("✅ Created line_items table")
except sqlite3.OperationalError as e:
    print(f"⚠️ line_items table: {e}")

# Update notes_history table structure
try:
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='notes_history'")
    if cur.fetchone():
        # Check if old structure exists
        cur.execute("PRAGMA table_info(notes_history)")
        columns = [col[1] for col in cur.fetchall()]
        
        if 'NotesContent' in columns and 'OldNotes' not in columns:
            # Rename table and recreate
            cur.execute("ALTER TABLE notes_history RENAME TO notes_history_old")
            
            cur.execute("""
                CREATE TABLE notes_history (
                    NoteHistID INTEGER PRIMARY KEY AUTOINCREMENT,
                    RMAID INTEGER NOT NULL,
                    OldNotes TEXT,
                    NewNotes TEXT,
                    ModifiedBy TEXT,
                    ModifiedOn TEXT NOT NULL,
                    FOREIGN KEY (RMAID) REFERENCES rmas(RMAID) ON DELETE CASCADE
                )
            """)
            
            cur.execute("""
                INSERT INTO notes_history (RMAID, NewNotes, ModifiedBy, ModifiedOn)
                SELECT RMAID, NotesContent, ModifiedBy, ModifiedOn
                FROM notes_history_old
            """)
            
            cur.execute("DROP TABLE notes_history_old")
            print("✅ Updated notes_history table structure")
except sqlite3.OperationalError as e:
    print(f"⚠️ notes_history table: {e}")

# Update attachments table
try:
    cur.execute("PRAGMA table_info(attachments)")
    columns = [col[1] for col in cur.fetchall()]
    
    if 'Filename' in columns and 'FileName' not in columns:
        cur.execute("ALTER TABLE attachments ADD COLUMN FileName TEXT")
        cur.execute("UPDATE attachments SET FileName = Filename")
        print("✅ Added FileName column to attachments")
except sqlite3.OperationalError as e:
    print(f"⚠️ attachments FileName: {e}")

# Create owner_notification_preferences table
try:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS owner_notification_preferences (
            PreferenceID INTEGER PRIMARY KEY AUTOINCREMENT,
            UserID INTEGER NOT NULL,
            EmailEnabled INTEGER DEFAULT 1,
            Frequency TEXT DEFAULT 'daily',
            RMAAge INTEGER DEFAULT 3,
            FOREIGN KEY (UserID) REFERENCES users(UserID) ON DELETE CASCADE
        )
    """)
    
    # Create default preferences for all existing users
    cur.execute("""
        INSERT INTO owner_notification_preferences (UserID, EmailEnabled, Frequency, RMAAge)
        SELECT UserID, 1, 'daily', 3
        FROM users
        WHERE UserID NOT IN (SELECT UserID FROM owner_notification_preferences)
    """)
    print("✅ Created owner_notification_preferences table")
except sqlite3.OperationalError as e:
    print(f"⚠️ owner_notification_preferences: {e}")

conn.commit()
conn.close()

print("\n✅ Database migration complete!")
print("Your database should now work with app.py")
