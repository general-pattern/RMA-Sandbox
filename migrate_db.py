import sqlite3

DB_PATH = "rma.db"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Add CreditMemoNumber to rmas table
try:
    cur.execute("ALTER TABLE rmas ADD COLUMN CreditMemoNumber TEXT")
    print("✓ Added CreditMemoNumber column")
except sqlite3.OperationalError as e:
    print(f"CreditMemoNumber column already exists or error: {e}")

# Add CreditApproved and CreditApprovedOn to rmas table
try:
    cur.execute("ALTER TABLE rmas ADD COLUMN CreditApproved INTEGER DEFAULT 0")
    print("✓ Added CreditApproved column")
except sqlite3.OperationalError as e:
    print(f"CreditApproved column already exists or error: {e}")

try:
    cur.execute("ALTER TABLE rmas ADD COLUMN CreditApprovedOn TEXT")
    print("✓ Added CreditApprovedOn column")
except sqlite3.OperationalError as e:
    print(f"CreditApprovedOn column already exists or error: {e}")

try:
    cur.execute("ALTER TABLE rmas ADD COLUMN CreditApprovedBy TEXT")
    print("✓ Added CreditApprovedBy column")
except sqlite3.OperationalError as e:
    print(f"CreditApprovedBy column already exists or error: {e}")

conn.commit()
conn.close()

print("\n✓ Database migration completed!")
