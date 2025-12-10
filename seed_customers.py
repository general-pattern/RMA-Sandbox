import sqlite3

conn = sqlite3.connect("rma.db")
cur = conn.cursor()

customers = [
]

cur.executemany("""
    INSERT INTO customers
    (CustomerName, ContactName, ContactEmail)
    VALUES (?, ?, ?)
""", customers)

conn.commit()
conn.close()
print("Seeded customers.")
