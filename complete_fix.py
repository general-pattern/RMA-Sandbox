
import re
import os
import shutil
from datetime import datetime

def backup_file(filepath):
    """Create a backup of the file"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{filepath}.backup_{timestamp}"
    shutil.copy2(filepath, backup_path)
    print(f"✅ Backup: {backup_path}")
    return backup_path

def fix_app_py():
    """Apply all fixes to app.py"""
    
    app_path = "app.py"
    
    if not os.path.exists(app_path):
        print(f"❌ Error: {app_path} not found!")
        return False
    
    backup_file(app_path)
    
    with open(app_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print("\n🔄 Applying fixes to app.py...")
    
    # ============================================
    # FIX 1: Add session['full_name'] to login
    # ============================================
    print("\n1️⃣ Fixing session full_name...")
    if "session[\"full_name\"] = user[\"FullName\"]" not in content:
        content = re.sub(
            r'(session\["user_id"\] = user\["UserID"\]\s*session\["username"\] = user\["Username"\]\s*session\["role"\] = user\["Role"\])',
            r'\1\n        session["full_name"] = user["FullName"]',
            content
        )
        print("   ✓ Added session['full_name'] to login")
    else:
        print("   ✓ Already fixed")
    
    # ============================================
    # FIX 2: Call init_db_if_needed() for gunicorn
    # ============================================
    print("\n2️⃣ Fixing database initialization for gunicorn...")
    if 'init_db_if_needed()\n\nif __name__ == "__main__"' not in content:
        content = re.sub(
            r'(# ============ CONTEXT PROCESSOR ============.*?def inject_user\(\):.*?return dict\(current_user=get_current_user\(\)\))\s*if __name__',
            r'\1\n\n\n# Initialize database on startup (needed for gunicorn)\ninit_db_if_needed()\n\nif __name__',
            content,
            flags=re.DOTALL
        )
        print("   ✓ Added init_db_if_needed() call for gunicorn")
    else:
        print("   ✓ Already fixed")
    
    # ============================================
    # FIX 3: Consolidate owners into users
    # ============================================
    print("\n3️⃣ Consolidating owners into users...")
    
    # Table references
    content = re.sub(r'FROM internal_owners\b(?! WHERE)', 'FROM users WHERE IsOwner = 1', content)
    content = re.sub(r'JOIN internal_owners o ON', 'JOIN users o ON', content)
    
    # Column names
    content = re.sub(r'o\.OwnerName\b', 'o.FullName', content)
    content = re.sub(r'o\.OwnerEmail\b', 'o.Email', content)
    content = re.sub(r"'OwnerName'", "'FullName'", content)
    content = re.sub(r"'OwnerEmail'", "'Email'", content)
    
    # Foreign keys
    content = re.sub(r'\bInternalOwnerID\b', 'AssignedToUserID', content)
    
    # WHERE clauses
    content = re.sub(
        r'o\.OwnerID = r\.InternalOwnerID',
        'o.UserID = r.AssignedToUserID AND o.IsOwner = 1',
        content
    )
    content = re.sub(r'GROUP BY o\.OwnerID', 'GROUP BY o.UserID', content)
    
    # Owner check in index/dashboard
    content = re.sub(
        r'cur\.execute\("""\s*SELECT OwnerID FROM internal_owners\s*WHERE OwnerEmail = \?\s*""", \(user\[\'Email\'\],\)\)\s*owner_row = cur\.fetchone\(\)\s*if owner_row:\s*is_owner = True\s*owner_id = owner_row\[\'OwnerID\'\]',
        "is_owner = user.get('IsOwner', 0) == 1\n        \n        if is_owner:\n            owner_id = user['UserID']",
        content,
        flags=re.DOTALL
    )
    
    # Notification preferences
    content = re.sub(
        r'SELECT OwnerID FROM internal_owners\s*WHERE OwnerEmail = \?',
        "SELECT UserID FROM users WHERE Email = ? AND IsOwner = 1",
        content
    )
    
    # Routes
    content = re.sub(r"url_for\('list_owners'\)", "url_for('admin_users')", content)
    content = re.sub(r"url_for\('new_owner'\)", "url_for('register')", content)
    
    print("   ✓ Updated all owner references")
    
    # ============================================
    # FIX 4: Add IsOwner to register function
    # ============================================
    print("\n4️⃣ Adding IsOwner to register...")
    if 'is_owner = 1 if request.form.get("is_owner")' not in content:
        content = re.sub(
            r'(role = request\.form\.get\("role", "user"\))',
            r'\1\n        is_owner = 1 if request.form.get("is_owner") else 0',
            content
        )
        
        content = re.sub(
            r'INSERT INTO users \(Username, PasswordHash, FullName, Email, Role, CreatedOn\)\s*VALUES \(\?, \?, \?, \?, \?, \?\)',
            'INSERT INTO users (Username, PasswordHash, FullName, Email, Role, IsOwner, CreatedOn)\n            VALUES (?, ?, ?, ?, ?, ?, ?)',
            content
        )
        
        content = re.sub(
            r'\(username, password_hash, full_name, email, role, now\)',
            '(username, password_hash, full_name, email, role, is_owner, now)',
            content
        )
        print("   ✓ Added IsOwner handling")
    else:
        print("   ✓ Already has IsOwner")
    
    # ============================================
    # FIX 5: Remove owner management routes
    # ============================================
    print("\n5️⃣ Removing old owner management routes...")
    
    routes_to_remove = [
        r'@app\.route\("/owners"\)[^@]*?(?=@app\.route|# ===|if __name__|$)',
        r'@app\.route\("/owners/new"[^@]*?(?=@app\.route|# ===|if __name__|$)',
        r'@app\.route\("/owners/<int:owner_id>/edit"[^@]*?(?=@app\.route|# ===|if __name__|$)',
        r'@app\.route\("/owners/<int:owner_id>/delete"[^@]*?(?=@app\.route|# ===|if __name__|$)',
    ]
    
    for pattern in routes_to_remove:
        content = re.sub(pattern, '', content, flags=re.DOTALL)
    
    print("   ✓ Removed owner routes")
    
    # Clean up extra whitespace
    content = re.sub(r'\n{4,}', '\n\n\n', content)
    
    # Write back
    with open(app_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("\n✅ app.py fixed!")
    return True

def fix_base_html():
    """Fix base.html navigation"""
    
    base_path = "templates/base.html"
    
    if not os.path.exists(base_path):
        print(f"\n⚠️ {base_path} not found, skipping...")
        return False
    
    backup_file(base_path)
    
    with open(base_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print("\n🔄 Fixing base.html...")
    
    # Replace Admin dropdown section
    admin_section = '''        <!-- Admin Dropdown - Only for admins -->
        {% if current_user and current_user['Role'] == 'admin' %}
        <div class="nav-dropdown">
          <button class="nav-dropdown-btn">Admin <span class="dropdown-arrow">▼</span></button>
          <div class="nav-dropdown-content">
            <a href="{{ url_for('admin_users') }}">👥 Manage Users</a>
            <a href="{{ url_for('register') }}">➕ Add User</a>
            <div style="border-top: 1px solid var(--gray-200); margin: 5px 0;"></div>
            <a href="{{ url_for('list_customers') }}">🏢 Customers</a>
          </div>
        </div>
        {% else %}
        <!-- Regular users see direct links -->
        <a href="{{ url_for('list_customers') }}" class="nav-link">🏢 Customers</a>
        {% endif %}'''
    
    # Find and replace the admin section
    content = re.sub(
        r'<!-- Admin Dropdown -->.*?</div>\s*</div>',
        admin_section,
        content,
        flags=re.DOTALL
    )
    
    # Remove any reference to list_owners
    content = content.replace("{{ url_for('list_owners') }}", "{{ url_for('admin_users') }}")
    content = content.replace("Internal Owners", "Users")
    content = content.replace("👤 Owners", "👥 Users")
    
    with open(base_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ base.html fixed!")
    return True

def fix_register_html():
    """Add IsOwner checkbox to register.html"""
    
    register_path = "templates/register.html"
    
    if not os.path.exists(register_path):
        print(f"\n⚠️ {register_path} not found, skipping...")
        return False
    
    backup_file(register_path)
    
    with open(register_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print("\n🔄 Fixing register.html...")
    
    if 'is_owner' not in content:
        # Add IsOwner checkbox after role selector
        checkbox_html = '''    
    <div class="form-group">
      <label style="display: flex; align-items: center; cursor: pointer;">
        <input type="checkbox" name="is_owner" style="width: auto; margin-right: 10px;">
        <span>Can be assigned RMAs (Owner)</span>
      </label>
      <small>Check this if the user should be able to own/handle RMAs</small>
    </div>'''
        
        content = re.sub(
            r'(<small>Admins can manage users and have full system access</small>\s*</div>)',
            r'\1\n' + checkbox_html,
            content
        )
        
        with open(register_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("✅ register.html fixed!")
    else:
        print("✅ register.html already has IsOwner")
    
    return True

def main():
    print("="*70)
    print("RMA App - Complete Fix Script")
    print("="*70)
    print("\nThis will fix:")
    print("  ✓ Session full_name issue")
    print("  ✓ Database initialization for gunicorn")
    print("  ✓ Consolidate owners into users")
    print("  ✓ Navigation menu")
    print("  ✓ Registration form")
    print("\nBackups will be created for all modified files.")
    print()
    
    response = input("Continue? (yes/no): ").strip().lower()
    
    if response != 'yes':
        print("\n❌ Aborted")
        return
    
    print("\n" + "="*70)
    
    # Fix all files
    fix_app_py()
    fix_base_html()
    fix_register_html()
    
    print("\n" + "="*70)
    print("✅ All Fixes Applied!")
    print("="*70)
    print("\nNext steps:")
    print("  1. Run: python migrate_consolidate_users.py")
    print("  2. Test locally: python app.py")
    print("  3. If it works: git add . && git commit -m 'Apply all fixes' && git push")
    print("\n💡 All original files have been backed up!")
    print()

if __name__ == "__main__":
    main()