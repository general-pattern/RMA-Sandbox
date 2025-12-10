#!/usr/bin/env python3
"""
Fix all remaining OwnerID references in app.py
"""

import re
import shutil
from datetime import datetime

def fix_owner_references():
    # Backup first
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    shutil.copy2("app.py", f"app.py.backup_{timestamp}")
    print(f"✅ Backup created: app.py.backup_{timestamp}")
    
    with open('app.py', 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    print("\n🔄 Fixing OwnerID references...")
    
    # List of all replacements needed
    replacements = [
        # SQL column references
        (r"SELECT OwnerID FROM users WHERE IsOwner = 1", "SELECT UserID FROM users WHERE IsOwner = 1"),
        (r"owner_row\['OwnerID'\]", "owner_row['UserID']"),
        (r"ro\.OwnerID", "ro.UserID"),
        (r"o\.OwnerID", "o.UserID"),
        
        # AS clauses - keep these as OwnerID for backwards compatibility in templates
        # (r"UserID\s+AS OwnerID", "UserID AS OwnerID"),  # Keep these
        
        # JOIN clauses
        (r"JOIN users o ON ro\.OwnerID = o\.OwnerID", "JOIN users o ON ro.UserID = o.UserID"),
        
        # WHERE clauses
        (r"WHERE ro\.OwnerID = \?", "WHERE ro.UserID = ?"),
        (r"WHERE OwnerID = \?", "WHERE UserID = ?"),
        (r"AND OwnerID = \?", "AND UserID = ?"),
        (r"WHERE RMAID = \? AND OwnerID = \?", "WHERE RMAID = ? AND UserID = ?"),
        
        # INSERT/UPDATE statements
        (r"INSERT INTO rma_owners \(RMAID, OwnerID,", "INSERT INTO rma_owners (RMAID, UserID,"),
        (r"\(OwnerID, EmailEnabled", "(UserID, EmailEnabled"),
        
        # Old internal_owners table references (delete these entire functions)
        (r'cur\.execute\("SELECT OwnerName, OwnerEmail FROM internal_owners WHERE OwnerID = \?",', 
         'cur.execute("SELECT FullName as OwnerName, Email as OwnerEmail FROM users WHERE UserID = ? AND IsOwner = 1",'),
        
        (r'cur\.execute\("UPDATE internal_owners SET OwnerName = \?, OwnerEmail = \? WHERE OwnerID = \?",',
         'cur.execute("UPDATE users SET FullName = ?, Email = ? WHERE UserID = ? AND IsOwner = 1",'),
        
        (r'cur\.execute\("SELECT \* FROM internal_owners WHERE OwnerID = \?",',
         'cur.execute("SELECT * FROM users WHERE UserID = ? AND IsOwner = 1",'),
        
        (r'cur\.execute\("DELETE FROM internal_owners WHERE OwnerID = \?",',
         'cur.execute("DELETE FROM users WHERE UserID = ? AND IsOwner = 1",'),
    ]
    
    fixed_count = 0
    for pattern, replacement in replacements:
        matches = len(re.findall(pattern, content))
        if matches > 0:
            content = re.sub(pattern, replacement, content)
            print(f"   ✓ Fixed {matches} occurrence(s) of: {pattern[:60]}...")
            fixed_count += matches
    
    # Write back
    with open('app.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"\n✅ Fixed {fixed_count} references!")
    print("\n💡 Note: 'UserID AS OwnerID' is kept for template compatibility")
    
    return True

if __name__ == "__main__":
    print("="*70)
    print("Fix All OwnerID References")
    print("="*70)
    
    fix_owner_references()
    
    print("\n" + "="*70)
    print("✅ Done!")
    print("="*70)
    print("\nNext step: python app.py")