import os
import sys
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, session, flash
from datetime import datetime
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import shutil

# Postgres imports
import psycopg2
from psycopg2.extras import RealDictCursor

# --- Paths / base dirs ---
if getattr(sys, "frozen", False):
    # Running as a frozen EXE
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # Running as normal Python script
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Postgres connection string from Render environment variable
DATABASE_URL = os.environ.get("DATABASE_URL")


app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static")
)

# Use env var in production, fallback for dev
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")


# Network location for RMA attachments
NETWORK_UPLOAD_PATH = r"\\server2\users\shared_files\QC\Inspection\Megan\RMA Attachments"

# Local fallback if network is unavailable
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["NETWORK_UPLOAD_PATH"] = NETWORK_UPLOAD_PATH
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024  # 20 MB

EMAIL_CONFIG = {
    "enabled": False,
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "sender_email": "your-email@gmail.com",
    "sender_password": "your-app-password",
    "base_url": "http://127.0.0.1:5000",
}

# status flow options
# Canonical statuses for the whole app
STATUS_OPTIONS = ['Draft', 'Acknowledged', 'In Progress', 'Disposition', 'Closed', 'Rejected']

def ensure_admin_user():
    """
    Ensure there is at least one user in the users table.
    If empty, create a default admin user.
    """
    conn = get_db()
    cur = conn.cursor()

    # Count how many users exist
    cur.execute("SELECT COUNT(*) AS count FROM users")
    row = cur.fetchone()
    user_count = row["count"] if row else 0

    if user_count == 0:
        username = "admin"
        raw_password = "Admin123!"  # change after first login
        password_hash = generate_password_hash(raw_password)

        full_name = "Admin User"
        email = "admin@example.com"
        role = "admin"
        is_owner = 1
        is_admin = 1
        created_on = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        last_login = None

        cur.execute(
            """
            INSERT INTO users
                (username, password_hash, full_name, email, role,
                 is_owner, is_admin, created_on, last_login)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                username,
                password_hash,
                full_name,
                email,
                role,
                is_owner,
                is_admin,
                created_on,
                last_login,
            ),
        )
        conn.commit()
        print("✅ Seeded default admin user: admin / Admin123!")

    conn.close()


def to_datetime(value):
    """Normalize DB value (string or datetime) to a datetime object."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    # Fallback for any old string data
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(value), fmt)
        except (ValueError, TypeError):
            continue
    return None


@app.template_filter("dt_display")
def dt_display(value):
    dt = to_datetime(value)
    if not dt:
        return ""

    date_part = dt.strftime("%m/%d/%Y")
    time_part = dt.strftime("%I:%M %p").lstrip("0")

    return f"<strong>{date_part}</strong> {time_part}"



# ============ TEMPLATE FILTERS ============

@app.template_filter("rma_code")
def rma_code_filter(value):
    try:
        return f"RMA{int(value):04d}"
    except:
        return value


@app.template_filter("currency")
def currency_filter(value):
    try:
        return f"${float(value):,.2f}"
    except:
        return value or '-'


@app.template_filter("short_date")
def short_date_filter(value):
    try:
        dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%b %d, %Y")
    except:
        return value or '-'


from datetime import datetime

from datetime import datetime, timedelta

@app.template_filter("time_active")
def time_active(opened, closed=None, status=None):
    """
    Return a nicely formatted 'X days, Y hours' string.
    Works with both datetime objects and strings.
    """

    if not opened:
        return "-"

    # --- Normalize OPENED ---
    if isinstance(opened, datetime):
        opened_dt = opened
    else:
        opened_dt = None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
            try:
                opened_dt = datetime.strptime(opened, fmt)
                break
            except ValueError:
                pass
        if opened_dt is None:
            return "-"

    # --- Normalize CLOSED ---
    closed_dt = None
    if closed:
        if isinstance(closed, datetime):
            closed_dt = closed
        else:
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
                try:
                    closed_dt = datetime.strptime(closed, fmt)
                    break
                except ValueError:
                    pass

    # If not closed → active RMA
    end_time = closed_dt if closed_dt else datetime.now()

    delta = end_time - opened_dt

    # Calculate days & hours
    total_seconds = int(delta.total_seconds())
    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600

    # Build output
    parts = []

    if days > 0:
        parts.append(f"{days} day{'s' if days != 1 else ''}")

    parts.append(f"{hours} hour{'s' if hours != 1 else ''}")

    result = ", ".join(parts)

    # Add closed tag if applicable
    if status in ("Closed", "Rejected") and closed_dt:
        result += " (closed)"

    return result


# ============ HELPERS ============


# Allow ANY file type – we just make sure it has some non-empty name
def allowed_file(filename: str) -> bool:
    return bool(filename and filename.strip())


def get_db():
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn
    except Exception as e:
        print("Database connection error:", e)
        raise


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access this page.", "error")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Decorator to require admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        
        user = get_current_user()
        if not user or user['role'] != 'admin':
            flash('You do not have permission to access this page.', 'error')
            return redirect(url_for('index'))
        
        return f(*args, **kwargs)
    return decorated_function


def get_current_user():
    if "user_id" not in session:
        return None

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM users WHERE user_id = %s",
        (session["user_id"],)
    )
    user = cur.fetchone()
    conn.close()
    return user



def send_rma_notification(owner_email, owner_name, rma_id, rma_code, customer_name, return_type, complaint, created_by):
    if not EMAIL_CONFIG['enabled']:
        print(f"[EMAIL DISABLED] Would send to {owner_email}: New RMA {rma_code}")
        return False
    
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"New RMA Assigned: {rma_code} - {customer_name}"
        msg['From'] = EMAIL_CONFIG['sender_email']
        msg['To'] = owner_email
        
        rma_url = f"{EMAIL_CONFIG['base_url']}/rmas/{rma_id}"
        
        html_content = f"""
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #1d4ed8;">New RMA Assigned: {rma_code}</h2>
        <p>Hello {owner_name},</p>
        <p>A new RMA has been assigned to you by <strong>{created_by}</strong>.</p>
        <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
            <tr><td style="padding: 8px; border: 1px solid #ddd; background: #f9f9f9;"><strong>RMA Number</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{rma_code}</td></tr>
            <tr><td style="padding: 8px; border: 1px solid #ddd; background: #f9f9f9;"><strong>Customer</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{customer_name}</td></tr>
            <tr><td style="padding: 8px; border: 1px solid #ddd; background: #f9f9f9;"><strong>Return Type</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{return_type}</td></tr>
            <tr><td style="padding: 8px; border: 1px solid #ddd; background: #f9f9f9;"><strong>Complaint</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{complaint[:100]}...</td></tr>
        </table>
        <p>
            <a href="{rma_url}" style="display: inline-block; padding: 12px 24px; background: #1d4ed8; color: white; text-decoration: none; border-radius: 4px; font-weight: bold;">View RMA Details</a>
        </p>
        <p style="color: #666; font-size: 14px; margin-top: 20px;">
            This is an automated notification from the RMA System. Please do not reply to this email.
        </p>
    </div>
</body>
</html>
"""
        
        part = MIMEText(html_content, 'html')
        msg.attach(part)
        
        with smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port']) as server:
            server.starttls()
            server.login(EMAIL_CONFIG['sender_email'], EMAIL_CONFIG['sender_password'])
            server.send_message(msg)
        
        print(f"✅ email sent to {owner_email}: {rma_code}")
        return True
        
    except Exception as e:
        print(f"❌ email error: {e}")
        return False


# ============ AUTH ROUTES ============

@app.route("/register", methods=["GET", "POST"])
@admin_required
def register():
    """
    Admin-only: create a new user account.
    Also seeds default notification preferences for that user.
    """
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm = (
            request.form.get("confirm")
            or request.form.get("confirm_password")
            or request.form.get("password2")
            or ""
        )
        role = request.form.get("role", "user").strip().lower()

        # Basic validation
        if not username or not full_name or not email or not password:
            flash("Username, full name, email, and password are required.", "error")
            return redirect(url_for("register"))

        if confirm and password != confirm:
            flash("Passwords do not match.", "error")
            return redirect(url_for("register"))

        conn = get_db()
        cur = conn.cursor()

        # Check duplicates
        cur.execute("SELECT 1 FROM users WHERE username = %s", (username,))
        if cur.fetchone():
            conn.close()
            flash("Username already exists.", "error")
            return redirect(url_for("register"))

        cur.execute("SELECT 1 FROM users WHERE email = %s", (email,))
        if cur.fetchone():
            conn.close()
            flash("Email already in use.", "error")
            return redirect(url_for("register"))

        password_hash = generate_password_hash(password)
        created_on = datetime.now().isoformat(timespec="seconds")

        # Set flags based on role
        is_admin = 1 if role == "admin" else 0
        is_owner = 1  # if you want everyone to be an owner by default
        # or do: is_owner = 1 if role in ("admin", "owner") else 0

        # Insert user and get their new user_id
        cur.execute(
            """
            INSERT INTO users (username, password_hash, full_name, email, role, created_on, is_owner, is_admin)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING user_id
            """,
            (username, password_hash, full_name, email, role, created_on, is_owner, is_admin),
        )
        new_user = cur.fetchone()
        new_user_id = new_user["user_id"]

        # Insert default notification preferences for this new user
        cur.execute(
            """
            INSERT INTO notification_preferences (user_id, days_threshold, notification_frequency)
            VALUES (%s, %s, %s)
            """,
            (new_user_id, 3, "weekly"),
        )

        conn.commit()
        conn.close()

        flash(f"User '{username}' created successfully.", "success")
        return redirect(url_for("admin_users"))

    # GET: show registration form
    return render_template("register.html")



@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        conn = get_db()
        cur = conn.cursor()

        # Postgres uses %s for placeholders, not %s
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cur.fetchone()

        # NOTE: these keys assume your Postgres columns are:
        # password_hash, user_id, username, full_name, last_login
        if user and check_password_hash(user["password_hash"], password):
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cur.execute(
                "UPDATE users SET last_login = %s WHERE user_id = %s",
                (now, user["user_id"])
            )
            conn.commit()
            conn.close()

            session["user_id"] = user["user_id"]
            session["username"] = user["username"]
            session["full_name"] = user["full_name"]

            flash(f"Welcome back, {user['full_name']}!", "success")
            return redirect(url_for("index"))
        else:
            conn.close()
            flash("Invalid username or password.", "error")

    return render_template("login.html")



@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user = get_current_user()
    
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip()
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        
        if not all([full_name, email]):
            flash("Full name and email are required.", "error")
            return render_template("profile.html", user=user)
        
        conn = get_db()
        cur = conn.cursor()
        
        # Check if email is taken by another user
        cur.execute("SELECT user_id FROM users WHERE email = %s AND user_id != %s", (email, user['user_id']))
        if cur.fetchone():
            conn.close()
            flash("email already in use by another user.", "error")
            return render_template("profile.html", user=user)
        
        # If changing password, verify current password
        if new_password:
            if not check_password_hash(user['password_hash'], current_password):
                conn.close()
                flash("Current password is incorrect.", "error")
                return render_template("profile.html", user=user)
            
            if len(new_password) < 6:
                conn.close()
                flash("New password must be at least 6 characters.", "error")
                return render_template("profile.html", user=user)
            
            password_hash = generate_password_hash(new_password)
            cur.execute("""
                UPDATE users 
                SET full_name = %s, email = %s, password_hash = %s
                WHERE user_id = %s
            """, (full_name, email, password_hash, user['user_id']))
            flash("Profile and password updated successfully.", "success")
        else:
            cur.execute("""
                UPDATE users 
                SET full_name = %s, email = %s
                WHERE user_id = %s
            """, (full_name, email, user['user_id']))
            flash("Profile updated successfully.", "success")
        
        conn.commit()
        conn.close()
        
        # Update session
        session['full_name'] = full_name
        
        return redirect(url_for("profile"))
    
    return render_template("profile.html", user=user)


# ============ DASHBOARD ============

@app.route("/")
@login_required
def index():
    conn = get_db()
    cur = conn.cursor()
    
    user = get_current_user()

# If session has a stale user_id or lookup failed, force relogin
    if not user:
        session.clear()
        return redirect(url_for("login"))
    
    # Get RMAs assigned to current user
    cur.execute("""
        SELECT 
            r.rma_id,
            r.status,
            r.date_opened,
            r.customer_date_opened,
            r.date_closed,
            r.customer_complaint_desc,
            r.return_type,
            c.customer_name,
            ro.is_primary
        FROM rmas r
        LEFT JOIN customers c ON r.customer_id = c.customer_id
        LEFT JOIN rma_owners ro ON r.rma_id = ro.rma_id
        WHERE ro.user_id = %s 
          AND r.status NOT IN ('Closed', 'Rejected')
        ORDER BY r.date_opened ASC
    """, (user['user_id'],))
    
    my_rmas = cur.fetchall()
    
    # Calculate stats
    total = len(my_rmas)
    urgent = 0
    warning = 0
    normal = 0

    for rma in my_rmas:
        opened = to_datetime(rma['date_opened'])

        if not opened:
            # skip if somehow no date
            continue

        days_open = (datetime.now() - opened).days

        if days_open >= 14:
            urgent += 1
        elif days_open >= 7:
            warning += 1
        else:
            normal += 1

    
    stats = {
        'total': total,
        'urgent': urgent,
        'warning': warning,
        'normal': normal
    }
    
    conn.close()
    
    return render_template(
        "dashboard.html",
        is_owner=True,
        my_rmas=my_rmas,
        stats=stats
    )

# ============ RMA ROUTES ============

@app.route("/rmas/new", methods=["GET", "POST"])
@login_required
def new_rma():
    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":
        customer_id = request.form.get("customer_id")
        return_type = request.form.get("return_type")
        complaint = request.form.get("complaint", "").strip()
        internal_notes = request.form.get("internal_notes", "").strip()
        customer_date_opened = request.form.get("customer_date_opened", "").strip()
        
        # Multi-select owners
        owner_ids = request.form.getlist("owner_ids")
        
        if not all([customer_id, return_type]):
            flash("Customer and Return Type are required.", "error")
            cur.execute("SELECT * FROM customers ORDER BY customer_name")
            customers = cur.fetchall()
            cur.execute("SELECT user_id, full_name FROM users WHERE is_owner = 1 ORDER BY full_name")
            owners = cur.fetchall()
            conn.close()
            return render_template("rma_new.html", customers=customers, owners=owners)

        now = datetime.now()
        created_by_user_id = session.get("user_id")

        # 🔹 INSERT into rmas with customer_date_opened
        cur.execute(
            """
            INSERT INTO rmas (
                customer_id,
                status,
                date_opened,
                customer_date_opened,
                return_type,
                customer_complaint_desc,
                internal_notes,
                created_by_user_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING rma_id
            """,
            (
                customer_id,
                "Draft",
                now,
                customer_date_opened or None,
                return_type,
                complaint or None,
                internal_notes or None,
                created_by_user_id,
            ),
        )
        rma_row = cur.fetchone()
        rma_id = rma_row["rma_id"]

        # 🔹 Initial status history row
        cur.execute(
            """
            INSERT INTO status_history (rma_id, status, changed_by, changed_on, comment)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (rma_id, "Draft", created_by_user_id, now, "RMA created"),
        )

        # 🔹 Assign owners (if any selected)
        if owner_ids:
            for owner_id in owner_ids:
                cur.execute(
                    """
                    INSERT INTO rma_owners (rma_id, user_id, is_primary, assigned_on, assigned_by)
                    VALUES (%s, %s, 0, %s, %s)
                    """,
                    (rma_id, owner_id, now, created_by_user_id),
                )

            # 🔹 Send email notifications to each owner
            for owner_id in owner_ids:
                cur.execute(
                    "SELECT full_name, email FROM users WHERE user_id = %s",
                    (owner_id,),
                )
                owner = cur.fetchone()

                if owner:
                    cur.execute(
                        "SELECT customer_name FROM customers WHERE customer_id = %s",
                        (customer_id,),
                    )
                    customer = cur.fetchone()

                    send_rma_notification(
                        owner_email=owner["email"],
                        owner_name=owner["full_name"],
                        rma_id=rma_id,
                        rma_code=f"RMA{rma_id:04d}",
                        customer_name=customer["customer_name"] if customer else "Unknown",
                        return_type=return_type,
                        complaint=complaint,
                        created_by=session.get("full_name", "System"),
                    )

        conn.commit()
        conn.close()

        flash(f"RMA{rma_id:04d} created successfully.", "success")
        return redirect(url_for("view_rma", rma_id=rma_id))

    # ========== GET: render blank form ==========
    cur.execute("SELECT customer_id, customer_name FROM customers ORDER BY customer_name")
    customers = cur.fetchall()

    cur.execute("SELECT user_id, full_name FROM users ORDER BY full_name")
    owners = cur.fetchall()

    conn.close()

    return render_template(
        "rma_new.html",
        customers=customers,
        owners=owners,
    )



@app.route("/rmas")
@login_required
def list_rmas():
    conn = get_db()
    cur = conn.cursor()

    # Get filter parameters
    search_query = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "")
    return_type_filter = request.args.get("return_type", "")
    customer_filter = request.args.get("customer_id", "")
    owner_filter = request.args.get("owner_id", "")
    from_date = request.args.get("from_date", "")
    to_date = request.args.get("to_date", "")
    credit_approved_filter = request.args.get("credit_approved", "")
    disposition_status_filter = request.args.get("disposition_status", "")

# Build query
    query = """
        SELECT 
            r.rma_id,
            r.status,
            r.date_opened,
            r.date_closed,
            r.customer_complaint_desc AS complaint,
            r.return_type,
            r.credit_approved,
            r.credit_rejected,
            r.credit_memo_number,
            c.customer_name,
            COALESCE(string_agg(DISTINCT u.full_name, ', '), '') AS owners,
            (
                SELECT MAX(d.date_dispositioned)
                FROM rma_lines rl
                JOIN dispositions d ON rl.rma_line_id = d.rma_line_id
                WHERE rl.rma_id = r.rma_id
            ) AS last_dispo_date
        FROM rmas r
        LEFT JOIN customers c ON r.customer_id = c.customer_id
        LEFT JOIN rma_owners ro ON r.rma_id = ro.rma_id
        LEFT JOIN users u ON ro.user_id = u.user_id
        WHERE 1=1
    """
    params = []

    if search_query:
        query += """
            AND (
                CAST(r.rma_id AS TEXT) ILIKE %s
                OR c.customer_name ILIKE %s
                OR r.customer_complaint_desc ILIKE %s
            )
        """
        search_pattern = f"%{search_query}%"
        params.extend([search_pattern, search_pattern, search_pattern])

    if status_filter:
        query += " AND r.status = %s"
        params.append(status_filter)

    if return_type_filter:
        query += " AND r.return_type = %s"
        params.append(return_type_filter)

    if customer_filter:
        query += " AND r.customer_id = %s"
        params.append(customer_filter)

    if owner_filter:
        query += " AND ro.user_id = %s"
        params.append(owner_filter)

    if from_date:
        query += " AND DATE(r.date_opened) >= %s"
        params.append(from_date)

    if to_date:
        query += " AND DATE(r.date_opened) <= %s"
        params.append(to_date)

    if credit_approved_filter == "pending":
        query += """
            AND r.return_type = 'Credit'
            AND (r.credit_approved IS NULL OR r.credit_approved = 0)
            AND (r.credit_rejected IS NULL OR r.credit_rejected = 0)
        """
    elif credit_approved_filter == "approved":
        query += " AND r.credit_approved = 1"
    elif credit_approved_filter == "rejected":
        query += " AND r.credit_rejected = 1"

    # NOTE: dispositionstatus column does not exist in the new schema,
    # so we temporarily ignore disposition_status_filter in the SQL.
    # We still pass it through current_filters so the UI keeps the value.
    # if disposition_status_filter:
    #     query += " AND r.dispositionstatus = %s"
    #     params.append(disposition_status_filter)

    query += """
        GROUP BY
            r.rma_id,
            r.status,
            r.date_opened,
            r.date_closed,
            r.customer_complaint_desc,
            r.return_type,
            r.credit_approved,
            r.credit_rejected,
            r.credit_memo_number,
            c.customer_name
        ORDER BY r.date_opened DESC
    """

    # 🔹 Run query and fetch rows
    cur.execute(query, params)
    rmas = cur.fetchall()

    # Get filter options
    cur.execute("SELECT * FROM customers ORDER BY customer_name")
    customers = cur.fetchall()

    cur.execute("SELECT user_id, full_name FROM users ORDER BY full_name")
    owners = cur.fetchall()

    conn.close()

    return render_template(
        "rma_list.html",
        rmas=rmas,
        customers=customers,
        owners=owners,
        status_options=STATUS_OPTIONS,
        current_filters={
            'search': search_query,
            'status': status_filter,
            'return_type': return_type_filter,
            'customer_id': customer_filter,
            'owner_id': owner_filter,
            'from_date': from_date,
            'to_date': to_date,
            'credit_approved': credit_approved_filter,
            'disposition_status': disposition_status_filter
        }
    )


@app.route("/rmas/<int:rma_id>")
@login_required
def view_rma(rma_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT 
            r.*,
            c.customer_name,
            c.contact_address,
            c.contact_email,
            creator.full_name AS created_by_name
        FROM rmas r
        LEFT JOIN customers c ON r.customer_id = c.customer_id
        LEFT JOIN users creator ON r.created_by_user_id = creator.user_id
        WHERE r.rma_id = %s
        """,
        (rma_id,),
    )

    rma = cur.fetchone()
 


    if not rma:
        conn.close()
        flash("RMA not found.", "error")
        return redirect(url_for("list_rmas"))

# Get line items + dispositions
    cur.execute("""
        SELECT 
            rl.rma_line_id      AS rma_line_id,
            rl.rma_id           AS rma_id,
            rl.part_number      AS part_number,
            rl.tool_number      AS tool_number,
            rl.item_description AS item_description,
            rl.qty_affected     AS qty_affected,
            rl.po_lot_number    AS po_lot_number,
            rl.total_cost       AS total_cost,

            d.disposition         AS disposition,
            d.failure_code        AS failure_code,
            d.failure_description AS failure_description,
            d.root_cause          AS root_cause,
            d.corrective_action   AS corrective_action,
            d.qty_scrap           AS qty_scrap,
            d.qty_rework          AS qty_rework,
            d.qty_replace         AS qty_replace,
            d.date_dispositioned  AS date_dispositioned,
            d.disposition_by      AS disposition_by,

            u.full_name           AS disposition_by_name

        FROM rma_lines rl
        LEFT JOIN dispositions d
            ON rl.rma_line_id = d.rma_line_id
        LEFT JOIN users u
            ON d.disposition_by = u.user_id
        WHERE rl.rma_id = %s
        ORDER BY rl.rma_line_id
    """, (rma_id,))
    lines = cur.fetchall()

    cur.execute("""
        SELECT 
            ro.is_primary,
            u.user_id,
            u.full_name
        FROM rma_owners ro
        JOIN users u ON ro.user_id = u.user_id
        WHERE ro.rma_id = %s
        ORDER BY ro.is_primary DESC, u.full_name
    """, (rma_id,))
    assigned_owners = cur.fetchall()

    # Get all users for owner dropdown
    cur.execute("""
        SELECT 
            user_id   AS "UserID",
            full_name AS "FullName"
        FROM users
        ORDER BY full_name
    """)

    all_owners = cur.fetchall()


    # Get status history
    cur.execute("""
        SELECT 
            sh.status_hist_id,
            sh.rma_id,
            sh.status,
            sh.changed_by,
            u.full_name as changed_byName,
            sh.changed_on,
            sh.comment
        FROM status_history sh
        LEFT JOIN users u ON sh.changed_by = u.user_id
        WHERE sh.rma_id = %s
        ORDER BY sh.changed_on DESC
    """, (rma_id,))
    statuses = cur.fetchall()

    # Get notes history
    cur.execute("""
        SELECT * FROM notes_history
        WHERE rma_id = %s
        ORDER BY modified_on DESC
    """, (rma_id,))
    notes_history = cur.fetchall()

    # Get attachments
    cur.execute("""
        SELECT 
            a.*,
            u.full_name as added_by_name
        FROM attachments a
        LEFT JOIN users u ON a.added_by::integer = u.user_id
        WHERE a.rma_id = %s
        ORDER BY a.date_added DESC
    """, (rma_id,))
    attachments = cur.fetchall()

    # Get all customers for reassignment dropdown
    cur.execute("SELECT * FROM customers ORDER BY customer_name")
    customers = cur.fetchall()

    # Get all users for owner assignment
    cur.execute("SELECT user_id, full_name FROM users ORDER BY full_name")
    all_owners = cur.fetchall()

    # Get credit history
    cur.execute("""
        SELECT 
            ch.*,
            u.full_name as actionByName
        FROM credit_history ch
        LEFT JOIN users u ON ch.action_by = u.user_id
        WHERE ch.rma_id = %s
        ORDER BY ch.action_on DESC
    """, (rma_id,))
    credit_history = cur.fetchall()

    conn.close()

    # Check for edit mode and other query parameters
    edit_mode = request.args.get('edit') == '1'
    edit_line = request.args.get('edit_line')
    show_notes_history = request.args.get('notes_history') == '1'
    edit_dispositions = request.args.get('edit_dispositions') == '1'

    return render_template(
        "rma_detail.html",
        rma=rma,
        lines=lines,                  # 👈 matches template {% if lines %}
        assigned_owners=assigned_owners,
        statuses=statuses,
        notes_history=notes_history,
        attachments=attachments,
        customers=customers,
        owners=all_owners,            # 👈 matches {% for o in owners %}
        credit_history=credit_history,
        status_options=STATUS_OPTIONS,
        edit_mode=edit_mode,
        edit_line=edit_line,
        show_notes_history=show_notes_history,
        edit_dispositions=edit_dispositions,
    )

@app.route("/rmas/<int:rma_id>/owners/<int:owner_id>/remove", methods=["POST"])
@login_required
def remove_rma_owner(rma_id, owner_id):
    """Remove an owner from an RMA"""
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("""
        DELETE FROM rma_owners 
        WHERE rma_id = %s AND user_id = %s
    """, (rma_id, owner_id))
    
    conn.commit()
    conn.close()
    
    flash("Owner removed successfully.", "success")
    return redirect(url_for("view_rma", rma_id=rma_id))


@app.route("/rmas/<int:rma_id>/lines/<int:line_id>/disposition", methods=["POST"])
@login_required
def add_disposition(rma_id, line_id):
    """Create or update the disposition for a specific RMA line."""
    conn = get_db()
    cur = conn.cursor()

    # Grab form values
    disposition        = request.form.get("disposition") or None
    failure_code       = request.form.get("failure_code") or None
    failure_desc       = request.form.get("failure_description") or None
    root_cause         = request.form.get("root_cause") or None
    corrective_action  = request.form.get("corrective_action") or None

    def to_int(value):
        if value is None or value == "":
            return None
        try:
            return int(value)
        except ValueError:
            return None

    qty_scrap   = to_int(request.form.get("qty_scrap"))
    qty_rework  = to_int(request.form.get("qty_rework"))
    qty_replace = to_int(request.form.get("qty_replace"))

    # Who is making this change
    user_id = session.get("user_id")
    now = datetime.now()

    # Check if a disposition already exists for this line
    cur.execute(
        "SELECT disposition_id FROM dispositions WHERE rma_line_id = %s",
        (line_id,),
    )
    existing = cur.fetchone()

    if existing:
        # UPDATE existing disposition
        cur.execute(
            """
            UPDATE dispositions
            SET
                disposition         = %s,
                failure_code        = %s,
                failure_description = %s,
                root_cause          = %s,
                corrective_action   = %s,
                qty_scrap           = %s,
                qty_rework          = %s,
                qty_replace         = %s,
                date_dispositioned  = %s,
                disposition_by      = %s
            WHERE rma_line_id = %s
            """,
            (
                disposition,
                failure_code,
                failure_desc,
                root_cause,
                corrective_action,
                qty_scrap,
                qty_rework,
                qty_replace,
                now,
                user_id,
                line_id,
            ),
        )
    else:
        # INSERT new disposition
        cur.execute(
            """
            INSERT INTO dispositions (
                rma_line_id,
                disposition,
                failure_code,
                failure_description,
                root_cause,
                corrective_action,
                qty_scrap,
                qty_rework,
                qty_replace,
                date_dispositioned,
                disposition_by
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                line_id,
                disposition,
                failure_code,
                failure_desc,
                root_cause,
                corrective_action,
                qty_scrap,
                qty_rework,
                qty_replace,
                now,
                user_id,
            ),
        )

    conn.commit()
    conn.close()

    flash("Disposition saved.", "success")
    return redirect(url_for("view_rma", rma_id=rma_id))

# ============================================
# CREDIT PAGE VIEW ROUTE
# ============================================
@app.route('/rmas/<int:rma_id>/credit')
@login_required
def view_rma_credit(rma_id):
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT r.*,
               c.customer_name,
               u_approved.full_name as credit_approved_by_name,
               u_rejected.full_name as credit_rejected_by_name
        FROM rmas r
        LEFT JOIN customers c ON r.customer_id = c.customer_id
        LEFT JOIN users u_approved ON r.credit_approved_by = u_approved.user_id
        LEFT JOIN users u_rejected ON r.credit_rejected_by = u_rejected.user_id
        WHERE r.rma_id = %s
    """, (rma_id,))
    
    rma = cur.fetchone()
    cur.close()
    conn.close()
    
    if not rma:
        flash('RMA not found', 'error')
        return redirect(url_for('index'))
    
    return render_template('rma_credit.html', rma=rma)


# ============================================
# APPROVE CREDIT ROUTE
# ============================================
@app.route('/rmas/<int:rma_id>/credit/approve', methods=['POST'])
@login_required
def approve_credit(rma_id):
    """Approve a credit request"""
    credit_amount = request.form.get('credit_amount')
    credit_memo_number = request.form.get('credit_memo_number', '').strip() or None
    
    if not credit_amount:
        flash('Credit amount is required', 'error')
        return redirect(url_for('view_rma_credit', rma_id=rma_id))
    
    try:
        credit_amount = float(credit_amount)
        if credit_amount <= 0:
            flash('Credit amount must be greater than 0', 'error')
            return redirect(url_for('view_rma_credit', rma_id=rma_id))
    except ValueError:
        flash('Invalid credit amount', 'error')
        return redirect(url_for('view_rma_credit', rma_id=rma_id))
    
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("""
        UPDATE rmas
        SET credit_approved = 1,
            credit_approved_on = %s,
            credit_approved_by = %s,
            credit_amount = %s,
            credit_memo_number = %s,
            credit_rejected = 0,
            credit_rejected_on = NULL,
            credit_rejected_by = NULL,
            credit_rejection_reason = NULL
        WHERE rma_id = %s
    """, (datetime.now(), session['user_id'], credit_amount, credit_memo_number, rma_id))
    
    conn.commit()
    cur.close()
    conn.close()
    
    flash(f'Credit approved for ${credit_amount:.2f}', 'success')
    return redirect(url_for('view_rma_credit', rma_id=rma_id))


# ============================================
# REJECT CREDIT ROUTE
# ============================================
@app.route('/rmas/<int:rma_id>/credit/reject', methods=['POST'])
@login_required
def reject_credit(rma_id):
    """Reject a credit request"""
    rejection_reason = request.form.get('rejection_reason', '').strip()
    
    if not rejection_reason:
        flash('Rejection reason is required', 'error')
        return redirect(url_for('view_rma_credit', rma_id=rma_id))
    
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("""
        UPDATE rmas
        SET credit_rejected = 1,
            credit_rejected_on = %s,
            credit_rejected_by = %s,
            credit_rejection_reason = %s,
            credit_approved = 0,
            credit_approved_on = NULL,
            credit_approved_by = NULL,
            credit_amount = NULL
        WHERE rma_id = %s
    """, (datetime.now(), session['user_id'], rejection_reason, rma_id))
    
    conn.commit()
    cur.close()
    conn.close()
    
    flash('Credit request has been rejected', 'warning')
    return redirect(url_for('view_rma_credit', rma_id=rma_id))


# ============================================
# MARK CREDIT AS ISSUED ROUTE
# ============================================
@app.route('/rmas/<int:rma_id>/credit/issue', methods=['POST'])
@login_required
def mark_credit_issued(rma_id):
    """Mark an approved credit as issued"""
    credit_memo_number = request.form.get('credit_memo_number', '').strip()
    
    if not credit_memo_number:
        flash('Credit memo number is required', 'error')
        return redirect(url_for('view_rma_credit', rma_id=rma_id))
    
    conn = get_db()
    cur = conn.cursor()
    
    # Check if credit is approved
    cur.execute("SELECT credit_approved FROM rmas WHERE rma_id = %s", (rma_id,))
    result = cur.fetchone()
    
    if not result or not result['credit_approved']:
        flash('Credit must be approved before it can be issued', 'error')
        cur.close()
        conn.close()
        return redirect(url_for('view_rma_credit', rma_id=rma_id))
    
    cur.execute("""
        UPDATE rmas
        SET credit_issued_on = %s,
            credit_memo_number = %s
        WHERE rma_id = %s
    """, (datetime.now(), credit_memo_number, rma_id))
    
    conn.commit()
    cur.close()
    conn.close()
    
    flash(f'Credit marked as issued with CM# {credit_memo_number}', 'success')
    return redirect(url_for('view_rma_credit', rma_id=rma_id))


# ============================================
# REOPEN CREDIT REQUEST ROUTE
# ============================================
@app.route('/rmas/<int:rma_id>/credit/reopen', methods=['POST'])
@login_required
def reopen_credit(rma_id):
    """Reopen a rejected credit request for reconsideration"""
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("""
        UPDATE rmas
        SET credit_rejected = 0,
            credit_rejected_on = NULL,
            credit_rejected_by = NULL,
            credit_rejection_reason = NULL
        WHERE rma_id = %s
    """, (rma_id,))
    
    conn.commit()
    cur.close()
    conn.close()
    
    flash('Credit request has been reopened for reconsideration', 'success')
    return redirect(url_for('view_rma_credit', rma_id=rma_id))

@app.route("/rmas/<int:rma_id>/acknowledge", methods=["POST"])
@login_required
def acknowledge_rma(rma_id):
    """Mark an RMA as acknowledged by the current user."""
    conn = get_db()
    cur = conn.cursor()

    user = get_current_user()
    if not user:
        conn.close()
        flash("Unable to determine current user.", "error")
        return redirect(url_for("list_rmas"))

    now = datetime.now()

    # Store undo info if you want (optional)
    session["last_undo"] = {
        "action": "restore_acknowledged",
        "data": {
            "rma_id": rma_id,
        },
    }

    # Update the RMA header
    cur.execute(
        """
        UPDATE rmas
        SET acknowledged = 1,
            acknowledged_on = %s,
            acknowledged_by = %s,
            status = CASE 
                        WHEN status = 'Draft' THEN 'Acknowledged'
                        ELSE status
                     END
        WHERE rma_id = %s
        """,
        (now, user["user_id"], rma_id),
    )

    # Optional: log into status_history as well
    cur.execute(
        """
        INSERT INTO status_history (rma_id, status, changed_by, changed_on, comment)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (rma_id, "Acknowledged", user["user_id"], now, "Marked as acknowledged"),
    )

    conn.commit()
    conn.close()

    flash("RMA acknowledged.", "success")
    return redirect(url_for("view_rma", rma_id=rma_id))


@app.route("/rmas/<int:rma_id>/edit_inline", methods=["POST"])
@login_required
def edit_rma_inline(rma_id):
    """Handle inline editing of RMA from detail view"""
    conn = get_db()
    cur = conn.cursor()
    
    customer_id = request.form.get("customer_id")
    return_type = request.form.get("return_type")
    complaint = request.form.get("complaint", "").strip()
    internal_notes = request.form.get("internal_notes", "").strip()
    credit_memo = request.form.get("credit_memo", "").strip()
    
    if not customer_id:
        flash("Customer is required.", "error")
        return redirect(url_for("view_rma", rma_id=rma_id, edit='1'))
    
    # Track if notes changed
    cur.execute("SELECT internal_notes FROM rmas WHERE rma_id = %s", (rma_id,))
    old_rma = cur.fetchone()
    notes_changed = old_rma and old_rma['internal_notes'] != internal_notes
    
    # Update RMA (status is managed separately via the status update card)
    cur.execute(
        """
        UPDATE rmas
        SET customer_id = %s,
            return_type = %s,
            customer_complaint_desc = %s,
            internal_notes = %s,
            credit_memo_number = %s,
            notes_last_modified = %s,
            notes_modified_by = %s
        WHERE rma_id = %s
        """,
        (
            customer_id,
            return_type,
            complaint,
            internal_notes,
            credit_memo,
            datetime.now() if notes_changed else old_rma.get('notes_last_modified'),
            session.get('username') if notes_changed else old_rma.get('notes_modified_by'),
            rma_id
        ),
    )
    
    # If notes changed, add to history
    if notes_changed:
        cur.execute(
            """
            INSERT INTO notes_history (rma_id, notes_content, modified_by, modified_on)
            VALUES (%s, %s, %s, %s)
            """,
            (rma_id, internal_notes, session.get('username'), datetime.now())
        )
    
    conn.commit()
    conn.close()
    
    flash("RMA updated successfully.", "success")
    return redirect(url_for("view_rma", rma_id=rma_id))


@app.route("/rmas/<int:rma_id>/edit", methods=["GET", "POST"])
@login_required
def edit_rma(rma_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM rmas WHERE rma_id = %s", (rma_id,))
    rma = cur.fetchone()

    if not rma:
        conn.close()
        flash("RMA not found.", "error")
        return redirect(url_for("list_rmas"))

    if request.method == "POST":
        customer_id = request.form.get("customer_id")
        return_type = request.form.get("return_type")
        complaint = request.form.get("complaint", "").strip()
        root_cause = request.form.get("root_cause", "").strip()
        corrective_action = request.form.get("corrective_action", "").strip()

        if not all([customer_id, return_type, complaint]):
            flash("Customer, Return Type, and Complaint are required.", "error")
            cur.execute("SELECT * FROM customers ORDER BY customer_name")
            customers = cur.fetchall()
            conn.close()
            return render_template("edit_rma.html", rma=rma, customers=customers)

        cur.execute(
            """
            UPDATE rmas
            SET customer_id = %s, return_type = %s, Complaint = %s,
                root_cause = %s, corrective_action = %s
            WHERE rma_id = %s
            """,
            (customer_id, return_type, complaint, root_cause, corrective_action, rma_id),
        )

        conn.commit()
        conn.close()

        flash("RMA updated successfully.", "success")
        return redirect(url_for("view_rma", rma_id=rma_id))

    # GET
    cur.execute("SELECT * FROM customers ORDER BY customer_name")
    customers = cur.fetchall()
    conn.close()

    return render_template("edit_rma.html", rma=rma, customers=customers)

@app.route("/dashboard/filter/<filter>")
@login_required
def dashboard_filtered(filter):
    """Show filtered RMAs from dashboard"""
    conn = get_db()
    cur = conn.cursor()
    
    user = get_current_user()
    
    # Get RMAs assigned to current user
    cur.execute("""
        SELECT 
            r.rma_id,
            r.status,
            r.date_opened,
            r.date_closed,
            r.customer_complaint_desc,
            r.return_type,
            c.customer_name,
            ro.is_primary
        FROM rmas r
        LEFT JOIN customers c ON r.customer_id = c.customer_id
        LEFT JOIN rma_owners ro ON r.rma_id = ro.rma_id
        WHERE ro.user_id = %s 
          AND r.status NOT IN ('Closed', 'Rejected')
        ORDER BY r.date_opened ASC
    """, (user['user_id'],))
    
    all_rmas = cur.fetchall()
    
    # Filter based on urgency
    filtered_rmas = []
    for rma in all_rmas:
        if rma['date_opened']:
            from datetime import datetime
            opened = datetime.strptime(rma['date_opened'], "%Y-%m-%d %H:%M:%S")
            days_open = (datetime.now() - opened).days
            
            if filter == 'urgent' and days_open >= 14:
                filtered_rmas.append(rma)
            elif filter == 'warning' and 7 <= days_open < 14:
                filtered_rmas.append(rma)
            elif filter == 'normal' and days_open < 7:
                filtered_rmas.append(rma)
    
    conn.close()
    
    filter_names = {
        'urgent': 'Urgent (>14 days)',
        'warning': 'Warning (7-14 days)',
        'normal': 'Normal (<7 days)'
    }
    
    return render_template(
        'dashboard_filtered.html',
        rmas=filtered_rmas,
        filter_name=filter_names.get(filter, 'Filtered'),
        filter_type=filter
    )

@app.route("/rmas/<int:rma_id>/delete", methods=["POST"])
@login_required
def delete_rma(rma_id):
    conn = get_db()
    cur = conn.cursor()

    # Get RMA to show in flash message
    cur.execute("SELECT rma_id FROM rmas WHERE rma_id = %s", (rma_id,))
    rma = cur.fetchone()

    if not rma:
        conn.close()
        flash("RMA not found.", "error")
        return redirect(url_for("list_rmas"))

    # Delete related records (cascading)
    cur.execute("DELETE FROM rma_lines WHERE rma_id = %s", (rma_id,))
    cur.execute("DELETE FROM rma_owners WHERE rma_id = %s", (rma_id,))
    cur.execute("DELETE FROM status_history WHERE rma_id = %s", (rma_id,))
    cur.execute("DELETE FROM notes_history WHERE rma_id = %s", (rma_id,))
    cur.execute("DELETE FROM attachments WHERE rma_id = %s", (rma_id,))
    cur.execute("DELETE FROM credit_history WHERE rma_id = %s", (rma_id,))
    cur.execute("DELETE FROM rmas WHERE rma_id = %s", (rma_id,))

    conn.commit()
    conn.close()

    flash(f"RMA{rma_id:04d} deleted successfully.", "success")
    return redirect(url_for("list_rmas"))


# ============ LINE ITEMS ============

@app.route("/rmas/<int:rma_id>/rma_line/add", methods=["POST"])
@login_required
def add_line_item(rma_id):
    conn = get_db()
    cur = conn.cursor()

    # Grab form values
    part_number = request.form.get("part_number") or None
    tool_number = request.form.get("tool_number") or None
    item_description = request.form.get("item_description") or None
    po_lot_number = request.form.get("po_lot_number") or None

    qty_raw = request.form.get("qty_affected")
    cost_raw = request.form.get("total_cost")

    # Safely convert numeric fields
    qty_affected = int(qty_raw) if qty_raw not in (None, "", " ") else None
    total_cost = float(cost_raw) if cost_raw not in (None, "", " ") else None

    # Adjust table / column names here to match your DB schema
    cur.execute(
        """
        INSERT INTO rma_lines (
            rma_id,
            part_number,
            tool_number,
            item_description,
            qty_affected,
            po_lot_number,
            total_cost
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (rma_id, part_number, tool_number, item_description, qty_affected, po_lot_number, total_cost),
    )

    conn.commit()
    conn.close()

    flash("Line item added.", "success")
    return redirect(url_for("view_rma", rma_id=rma_id))



@app.route("/rmas/<int:rma_id>/line_items/<int:rma_line_id>/delete", methods=["POST"])
@login_required
def delete_line_item(rma_id, rma_line_id):
    conn = get_db()
    cur = conn.cursor()

    # Delete from the correct table/PK
    cur.execute(
        """
        DELETE FROM rma_lines
        WHERE rma_line_id = %s
          AND rma_id = %s
        """,
        (rma_line_id, rma_id),
    )

    conn.commit()
    conn.close()

    flash("Line item deleted.", "success")
    return redirect(url_for("view_rma", rma_id=rma_id))




# ============ RMA OWNERS ============

@app.route("/rmas/<int:rma_id>/owners/update", methods=["POST"])
@login_required
def update_owners(rma_id):
    """Add owners to an RMA"""
    owner_ids = request.form.getlist("owner_ids")
    
    if not owner_ids:
        flash("Please select at least one owner.", "error")
        return redirect(url_for("view_rma", rma_id=rma_id))
    
    conn = get_db()
    cur = conn.cursor()
    
    # Add new owners (skip if already assigned)
    for owner_id in owner_ids:
        # Check if already assigned
        cur.execute("""
            SELECT 1 FROM rma_owners 
            WHERE rma_id = %s AND user_id = %s
        """, (rma_id, owner_id))
        
        if not cur.fetchone():
            cur.execute("""
                INSERT INTO rma_owners (rma_id, user_id, is_primary)
                VALUES (%s, %s, 0)
            """, (rma_id, owner_id))
    
    conn.commit()
    conn.close()
    
    flash("Owners added successfully.", "success")
    return redirect(url_for("view_rma", rma_id=rma_id))


# ============ STATUS CHANGES ============

@app.route("/rmas/<int:rma_id>/status", methods=["POST"])
@login_required
def change_status(rma_id):
    new_status = request.form.get("status")
    comment = request.form.get("comment", "").strip()

    if not new_status or new_status not in STATUS_OPTIONS:
        flash("Invalid status.", "error")
        return redirect(url_for("view_rma", rma_id=rma_id))

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db()
    cur = conn.cursor()

    # Get current status for undo
    cur.execute("SELECT status FROM rmas WHERE rma_id = %s", (rma_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        flash("RMA not found.", "error")
        return redirect(url_for("list_rmas"))

    old_status = row["status"]

    # Store undo info
    session["last_undo"] = {
        "action": "restore_status",
        "data": {
            "rma_id": rma_id,
            "Oldstatus": old_status,
            "Newstatus": new_status,
        },
    }

    # Update RMA status
    if new_status in ['Closed', 'Rejected']:
        cur.execute(
            "UPDATE rmas SET status = %s, date_closed = %s WHERE rma_id = %s",
            (new_status, now, rma_id),
        )
    else:
        cur.execute(
            "UPDATE rmas SET status = %s, date_closed = NULL WHERE rma_id = %s",
            (new_status, rma_id),
        )

    # Log to history
    cur.execute(
        """
        INSERT INTO status_history (rma_id, status, changed_by, changed_on, comment)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (rma_id, new_status, session["user_id"], now, comment),
    )

    conn.commit()
    conn.close()

    flash(f"status changed to '{new_status}'.", "success")
    return redirect(url_for("view_rma", rma_id=rma_id))


# ============ NOTES / INTERNAL NOTES ============

@app.route("/rmas/<int:rma_id>/notes", methods=["POST"])
@login_required
def update_notes(rma_id):
    """Update Internal Notes on an RMA and log to notes_history."""
    new_notes = (request.form.get("internal_notes") or "").strip()
    now = datetime.now()

    conn = get_db()
    cur = conn.cursor()

    # Get the previous notes (for undo, if you want)
    cur.execute(
        "SELECT internal_notes FROM rmas WHERE rma_id = %s",
        (rma_id,),
    )
    row = cur.fetchone()
    old_notes = row["internal_notes"] if row and row["internal_notes"] else ""

    # 🔹 Save undo info in session (optional but your UI uses `last_undo`)
    session["last_undo"] = {
        "action": "restore_notes",
        "data": {
            "rma_id": rma_id,
            "internal_notes": old_notes,
        },
    }

    # 🔹 Insert a history entry – uses the *actual* columns
    cur.execute(
        """
        INSERT INTO notes_history (rma_id, notes_content, modified_by, modified_on)
        VALUES (%s, %s, %s, %s)
        """,
        (rma_id, new_notes, session.get("full_name"), now),
    )

    # 🔹 Update the main RMA record
    cur.execute(
        """
        UPDATE rmas
        SET internal_notes = %s,
            notes_last_modified = %s,
            notes_modified_by = %s
        WHERE rma_id = %s
        """,
        (new_notes, now, session.get("full_name"), rma_id),
    )

    conn.commit()
    conn.close()

    flash("Notes updated.", "success")
    return redirect(url_for("view_rma", rma_id=rma_id))



# ============ ATTACHMENTS ============

@app.route("/rmas/<int:rma_id>/attachments/add", methods=["POST"])
@login_required
def add_attachment(rma_id):
    if "file" not in request.files:
        flash("No file part in request.", "error")
        return redirect(url_for("view_rma", rma_id=rma_id))

    file = request.files["file"]
    if file.filename == "":
        flash("No file selected.", "error")
        return redirect(url_for("view_rma", rma_id=rma_id))

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        
        # Format RMA number as RMA-XXXX
        rma_folder_name = f"RMA-{rma_id:04d}"
        
        # Try to save to network location first
        try:
            network_dir = os.path.join(app.config["NETWORK_UPLOAD_PATH"], rma_folder_name)
            os.makedirs(network_dir, exist_ok=True)
            full_path = os.path.join(network_dir, filename)
            file.save(full_path)
            
            # Store the network path in database
            stored_path = full_path
            flash("Attachment uploaded to network location.", "success")
        except Exception as e:
            # Fallback to local storage if network is unavailable
            upload_dir = os.path.join(app.config["UPLOAD_FOLDER"], rma_folder_name)
            os.makedirs(upload_dir, exist_ok=True)
            full_path = os.path.join(upload_dir, filename)
            file.save(full_path)
            stored_path = full_path
            flash(f"Attachment uploaded to local storage (network unavailable: {str(e)})", "warning")

        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO attachments (rma_id, attachment_type, file_path, filename, added_by, date_added)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (rma_id, "File", stored_path, filename, session["user_id"], datetime.now()),
        )
        conn.commit()
        conn.close()

        return redirect(url_for("view_rma", rma_id=rma_id))
    else:
        flash("File type not allowed.", "error")
        return redirect(url_for("view_rma", rma_id=rma_id))



@app.route("/rmas/<int:rma_id>/attachments/<int:attachment_id>/delete", methods=["POST"])
@login_required
def delete_attachment(rma_id, attachment_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT file_path FROM attachments WHERE attachment_id = %s AND rma_id = %s", (attachment_id, rma_id))
    row = cur.fetchone()

    if row:
        filepath = row["file_path"]
        # file_path now stores the full path, so use it directly
        if os.path.exists(filepath):
            os.remove(filepath)

        cur.execute("DELETE FROM attachments WHERE attachment_id = %s", (attachment_id,))
        conn.commit()
        flash("Attachment deleted.", "success")
    else:
        flash("Attachment not found.", "error")

    conn.close()
    return redirect(url_for("view_rma", rma_id=rma_id))


@app.route("/rmas/<int:rma_id>/status_history/<int:history_id>/delete", methods=["POST"])
@login_required
def delete_status_history(rma_id, history_id):
    """Delete a status history entry"""
    conn = get_db()
    cur = conn.cursor()
    
    # Verify the history entry belongs to this RMA
    cur.execute(
        "SELECT status_hist_id FROM status_history WHERE status_hist_id = %s AND rma_id = %s",
        (history_id, rma_id)
    )
    row = cur.fetchone()
    
    if row:
        cur.execute("DELETE FROM status_history WHERE status_hist_id = %s", (history_id,))
        conn.commit()
        flash("Status history entry deleted.", "success")
    else:
        flash("Status history entry not found.", "error")
    
    conn.close()
    return redirect(url_for("view_rma", rma_id=rma_id))


@app.route("/rmas/<int:rma_id>/attachments/open_folder")
@login_required
def open_attachment_folder(rma_id):
    """Open the RMA attachments folder in Windows Explorer"""
    import subprocess
    
    # Format RMA number as RMA-XXXX
    rma_folder_name = f"RMA-{rma_id:04d}"
    
    # Try network location first
    network_folder = os.path.join(app.config["NETWORK_UPLOAD_PATH"], rma_folder_name)
    
    if os.path.exists(network_folder):
        folder_path = network_folder
    else:
        # Fallback to local folder
        folder_path = os.path.join(app.config["UPLOAD_FOLDER"], rma_folder_name)
    
    # Create folder if it doesn't exist
    os.makedirs(folder_path, exist_ok=True)
    
    try:
        # Open folder in Windows Explorer
        subprocess.Popen(f'explorer "{folder_path}"')
        flash(f"Opening folder: {folder_path}", "success")
    except Exception as e:
        flash(f"Could not open folder: {str(e)}", "error")
    
    return redirect(url_for("view_rma", rma_id=rma_id))


@app.route("/rmas/<int:rma_id>/attachments/<int:attachment_id>/open")
@login_required
def open_specific_attachment(rma_id, attachment_id):
    """Open a specific attachment file in its default application"""
    import subprocess
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT file_path, filename FROM attachments WHERE attachment_id = %s AND rma_id = %s", (attachment_id, rma_id))
    row = cur.fetchone()
    conn.close()
    
    if row and os.path.exists(row["file_path"]):
        try:
            # Open the file with its default application
            os.startfile(row["file_path"])
            flash(f"Opening {row['filename']}...", "success")
        except Exception as e:
            flash(f"Could not open file: {str(e)}", "error")
    else:
        flash("File not found.", "error")
    
    return redirect(url_for("view_rma", rma_id=rma_id))


# ============ CUSTOMERS ============

@app.route("/customers")
@login_required
def list_customers():
    conn = get_db()
    cur = conn.cursor()

    # Pull customers + counts of RMAs + open RMAs
    cur.execute("""
        SELECT 
            c.customer_id,
            c.customer_name,
            c.contact_name,
            c.contact_email,
            COUNT(r.rma_id) AS rma_count,
            COUNT(CASE WHEN r.status NOT IN ('Closed', 'Rejected') THEN 1 END) AS open_count
        FROM customers c
        LEFT JOIN rmas r ON c.customer_id = r.customer_id
        GROUP BY c.customer_id, c.customer_name, c.contact_name, c.contact_email
        ORDER BY c.customer_name
    """)
    customers = cur.fetchall()
    conn.close()

    return render_template("customers.html", customers=customers)


@app.route("/customers/new", methods=["GET", "POST"])
@login_required
def new_customer():
    if request.method == "POST":
        name = request.form.get("customer_name", "").strip()
        contact_name = request.form.get("contact_name", "").strip()
        contact_email = request.form.get("contact_email", "").strip()

        if not name:
            flash("Customer name is required.", "error")
            return redirect(url_for("new_customer"))

        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO customers (customer_name, contact_name, contact_email)
            VALUES (%s, %s, %s)
        """, (name, contact_name, contact_email))
        conn.commit()
        conn.close()

        flash("Customer created successfully.", "success")
        return redirect(url_for("list_customers"))

    return render_template("customer_new.html")


@app.route("/customers/<int:customer_id>/edit", methods=["GET", "POST"])
@login_required
def edit_customer(customer_id):
    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":
        name = request.form.get("customer_name", "").strip()
        contact_name = request.form.get("contact_name", "").strip()
        contact_email = request.form.get("contact_email", "").strip()

        if not name:
            flash("Customer name is required.", "error")
            conn.close()
            flash("Customer name is required.", "error")
            return redirect(url_for("edit_customer", customer_id=customer_id))

        cur.execute("""
            UPDATE customers
            SET customer_name = %s,
                contact_name = %s,
                contact_email = %s
            WHERE customer_id = %s
        """, (name, contact_name, contact_email, customer_id))
        conn.commit()
        conn.close()

        flash("Customer updated.", "success")
        return redirect(url_for("list_customers"))

    cur.execute("SELECT * FROM customers WHERE customer_id = %s", (customer_id,))
    customer = cur.fetchone()
    conn.close()

    if not customer:
        flash("Customer not found.", "error")
        return redirect(url_for("list_customers"))

    return render_template("customer_edit.html", customer=customer)

@app.route("/customers/<int:customer_id>/delete", methods=["POST"])
@admin_required
def delete_customer(customer_id):
    """Delete a customer if they have no RMAs."""
    conn = get_db()
    cur = conn.cursor()

    # Check if this customer is referenced by any RMAs
    cur.execute(
        """
        SELECT COUNT(*) AS rma_count
        FROM rmas
        WHERE customer_id = %s
        """,
        (customer_id,),
    )
    row = cur.fetchone()
    rma_count = row["rma_count"] if row and row["rma_count"] is not None else 0

    if rma_count > 0:
        conn.close()
        flash(
            "Cannot delete customer: there are RMAs linked to this customer.",
            "error",
        )
        return redirect(url_for("list_customers"))

    # Safe to delete
    cur.execute(
        "DELETE FROM customers WHERE customer_id = %s",
        (customer_id,),
    )
    conn.commit()
    conn.close()

    flash("Customer deleted successfully.", "success")
    return redirect(url_for("list_customers"))




# ============ UNDO LAST ACTION ============

@app.route("/undo", methods=["POST"])
@login_required
def undo_last():
    undo_info = session.get("last_undo")
    if not undo_info:
        flash("Nothing to undo.", "info")
        return redirect(request.referrer or url_for("index"))

    action = undo_info["action"]
    data = undo_info["data"]

    conn = get_db()
    cur = conn.cursor()

    if action == "restore_status":
        cur.execute(
            "UPDATE rmas SET status = %s WHERE rma_id = %s",
            (data["Oldstatus"], data["rma_id"]),
        )
        flash(f"status reverted to '{data['Oldstatus']}'.", "info")

    elif action == "restore_credit_approval":
        cur.execute(
            """
            UPDATE rmas
            SET credit_approved = %s,
                credit_approvedOn = %s,
                credit_approvedBy = %s
            WHERE rma_id = %s
            """,
            (
                data["credit_approved"],
                data["credit_approvedOn"],
                data["credit_approvedBy"],
                data["rma_id"],
            ),
        )
        flash("Credit approval reverted.", "info")

    conn.commit()
    conn.close()

    # Clear undo after using it
    session.pop("last_undo", None)

    return redirect(request.referrer or url_for("index"))


# ============ METRICS / ANALYTICS ============

@app.route("/metrics")
@login_required
def metrics():
    conn = get_db()
    cur = conn.cursor()
    
    # Get week filter parameter
    week = request.args.get('week', 'all')
    
    # Determine date range and label
    from datetime import datetime, timedelta
    today = datetime.now().date()
    
    if week == 'this_week':
        # Monday of current week
        start_date = today - timedelta(days=today.weekday())
        end_date = today
        week_label = f"This Week ({start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')})"
    elif week == 'last_week':
        # Last Monday to Sunday
        start_date = today - timedelta(days=today.weekday() + 7)
        end_date = start_date + timedelta(days=6)
        week_label = f"Last Week ({start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')})"
    elif week == 'last_4_weeks':
        start_date = today - timedelta(weeks=4)
        end_date = today
        week_label = f"Last 4 Weeks ({start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')})"
    else:
        start_date = None
        end_date = None
        week_label = "All Time"
    
    # Build WHERE clause for date filtering
    if start_date and end_date:
        date_filter = f"WHERE date_opened BETWEEN '{start_date}' AND '{end_date}'"
    else:
        date_filter = ""
    
    # Total RMAs
    cur.execute(f"SELECT COUNT(*) AS count FROM rmas {date_filter}")
    total_rmas = cur.fetchone()['count']
    
    # Credits approved count
    cur.execute(f"SELECT COUNT(*) AS count FROM rmas {date_filter} {'AND' if date_filter else 'WHERE'} credit_approved = 1")
    credit_approved_count = cur.fetchone()['count']
    
    # Credits requested count
    cur.execute(f"SELECT COUNT(*) AS count FROM rmas {date_filter} {'AND' if date_filter else 'WHERE'} return_type = 'Credit'")
    credit_requested_count = cur.fetchone()['count']
    
    # Status breakdown
    cur.execute(f"""
        SELECT status, COUNT(*) AS count
        FROM rmas
        {date_filter}
        GROUP BY status
        ORDER BY count DESC
    """)
    status_breakdown = cur.fetchall()

    # Return type breakdown
    cur.execute(f"""
        SELECT return_type, COUNT(*) AS count
        FROM rmas
        {date_filter}
        GROUP BY return_type
        ORDER BY count DESC
    """)
    return_type_breakdown = cur.fetchall()
    
    # Disposition breakdown
    cur.execute(f"""
        SELECT d.disposition, COUNT(*) AS count
        FROM dispositions d
        JOIN rma_lines rl ON d.rma_line_id = rl.rma_line_id
        JOIN rmas r ON rl.rma_id = r.rma_id
        {date_filter}
        GROUP BY d.disposition
        ORDER BY count DESC
    """)
    disposition_breakdown = cur.fetchall()
    
    # Count RMAs with/without dispositions
    cur.execute(f"""
        SELECT COUNT(DISTINCT r.rma_id) AS count
        FROM rmas r
        JOIN rma_lines rl ON r.rma_id = rl.rma_id
        JOIN dispositions d ON rl.rma_line_id = d.rma_line_id
        {date_filter}
    """)
    rmas_with_dispositions = cur.fetchone()['count']
    
    cur.execute(f"""
        SELECT COUNT(DISTINCT r.rma_id) AS count
        FROM rmas r
        LEFT JOIN rma_lines rl ON r.rma_id = rl.rma_id
        LEFT JOIN dispositions d ON rl.rma_line_id = d.rma_line_id
        {date_filter}
        {'AND' if date_filter else 'WHERE'} d.disposition_id IS NULL
    """)
    rmas_without_dispositions = cur.fetchone()['count']

    # Top customers by RMA count
    cur.execute(f"""
        SELECT c.customer_id, c.customer_name, COUNT(r.rma_id) AS rma_count
        FROM customers c
        LEFT JOIN rmas r ON c.customer_id = r.customer_id
        {date_filter.replace('WHERE', 'WHERE' if 'WHERE' in date_filter else 'AND') if date_filter else ''}
        GROUP BY c.customer_id, c.customer_name
        HAVING COUNT(r.rma_id) > 0
        ORDER BY rma_count DESC
        LIMIT 10
    """)
    top_customers = cur.fetchall()

    # Owner workload (current open RMAs)
    cur.execute("""
        SELECT 
            u.user_id AS "OwnerID",
            u.full_name AS "OwnerName",
            COUNT(DISTINCT r.rma_id) AS total,
            COUNT(
                DISTINCT CASE 
                    WHEN r.status NOT IN ('Closed', 'Rejected') THEN r.rma_id 
                END
            ) AS active
        FROM users u
        LEFT JOIN rma_owners ro ON u.user_id = ro.user_id
        LEFT JOIN rmas r ON ro.rma_id = r.rma_id
        GROUP BY u.user_id, u.full_name
        HAVING COUNT(DISTINCT r.rma_id) > 0
        ORDER BY active DESC, total DESC
    """)
    owner_workload = cur.fetchall()

    # Average time to close (for closed RMAs)
    cur.execute(f"""
        SELECT 
            AVG(
                EXTRACT(
                    EPOCH FROM (
                        date_closed::timestamp - date_opened::timestamp
                    )
                ) / 86400.0
            ) AS avg_days
        FROM rmas
        {date_filter}
        {'AND' if date_filter else 'WHERE'} status = 'Closed' AND date_closed IS NOT NULL
    """)
    avg_time_result = cur.fetchone()
    avg_days_to_close = (
        round(avg_time_result["avg_days"], 1)
        if avg_time_result and avg_time_result["avg_days"] is not None
        else None
    )

    conn.close()

    return render_template(
        "metrics.html",
        week=week,
        week_label=week_label,
        total_rmas=total_rmas,
        credit_approved_count=credit_approved_count,
        credit_requested_count=credit_requested_count,
        status_breakdown=status_breakdown,
        return_type_breakdown=return_type_breakdown,
        disposition_breakdown=disposition_breakdown,
        rmas_with_dispositions=rmas_with_dispositions,
        rmas_without_dispositions=rmas_without_dispositions,
        top_customers=top_customers,
        owner_workload=owner_workload,
        avg_days_to_close=avg_days_to_close
    )

# ============ CREDIT MANAGEMENT ============

@app.route("/credits/dashboard")
@login_required
def credit_dashboard():
    """Dashboard for credit-type RMAs"""
    conn = get_db()
    cur = conn.cursor()
    
    # Pending credits
    cur.execute("""
        SELECT 
            r.rma_id,
            r.date_opened,
            r.customer_complaint_desc AS complaint,
            c.customer_name,
            COALESCE(string_agg(DISTINCT u.full_name, ', '), '') AS owners
        FROM rmas r
        LEFT JOIN customers c ON r.customer_id = c.customer_id
        LEFT JOIN rma_owners ro ON r.rma_id = ro.rma_id
        LEFT JOIN users u ON ro.user_id = u.user_id
        WHERE r.return_type = 'Credit'
          AND (r.credit_approved IS NULL OR r.credit_approved = 0)
          AND (r.credit_rejected IS NULL OR r.credit_rejected = 0)
        GROUP BY
            r.rma_id,
            r.date_opened,
            r.customer_complaint_desc,
            c.customer_name
        ORDER BY r.date_opened
    """)
    pending_credits = cur.fetchall()
    
    # Approved credits
    cur.execute("""
        SELECT 
            r.rma_id,
            r.date_opened,
            r.credit_approved_on,
            r.credit_amount,
            r.credit_memo_number,
            c.customer_name
        FROM rmas r
        LEFT JOIN customers c ON r.customer_id = c.customer_id
        WHERE r.credit_approved = 1
        ORDER BY r.credit_approved_on DESC
        LIMIT 20
    """)
    approved_credits = cur.fetchall()
    
    # Rejected credits
    cur.execute("""
        SELECT 
            r.rma_id,
            r.date_opened,
            r.credit_rejected_on,
            c.customer_name
        FROM rmas r
        LEFT JOIN customers c ON r.customer_id = c.customer_id
        WHERE r.credit_rejected = 1
        ORDER BY r.credit_rejected_on DESC
        LIMIT 20
    """)
    rejected_credits = cur.fetchall()
    
    # Summary stats
    cur.execute("""
        SELECT 
            COUNT(*) AS total_credit_rmas,
            SUM(CASE WHEN credit_approved = 1 THEN 1 ELSE 0 END) AS approved_count,
            SUM(CASE WHEN credit_rejected = 1 THEN 1 ELSE 0 END) AS rejected_count,
            SUM(
                CASE 
                    WHEN (credit_approved IS NULL OR credit_approved = 0) 
                     AND (credit_rejected IS NULL OR credit_rejected = 0)
                    THEN 1 ELSE 0 
                END
            ) AS pending_count,
            SUM(
                CASE 
                    WHEN credit_approved = 1 THEN COALESCE(credit_amount, 0)
                    ELSE 0 
                END
            ) AS total_approved_amount
        FROM rmas
        WHERE return_type = 'Credit'
    """)
    stats = cur.fetchone()
    
    conn.close()
    
    return render_template(
        "credit_dashboard.html",
        pending_credits=pending_credits,
        approved_credits=approved_credits,
        rejected_credits=rejected_credits,
        stats=stats
    )


@app.route("/rmas/<int:rma_id>/approve_credit", methods=["POST"])
@login_required
def toggle_credit_approval(rma_id):
    """
    Simple toggle for credit_approved flag.
    This version only flips the boolean + timestamp/by,
    not amount/memo. Use /credit/approve for full approval.
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    conn = get_db()
    cur = conn.cursor()
    
    # Get current status
    cur.execute("""
        SELECT credit_approved, credit_approved_on, credit_approved_by
        FROM rmas
        WHERE rma_id = %s
    """, (rma_id,))
    row = cur.fetchone()
    
    if not row:
        conn.close()
        flash("RMA not found.", "error")
        return redirect(url_for("list_rmas"))
    
    # Store undo info
    session["last_undo"] = {
        "action": "restore_credit_approval",
        "data": {
            "rma_id": rma_id,
            "credit_approved": row["credit_approved"],
            "credit_approved_on": row["credit_approved_on"],
            "credit_approved_by": row["credit_approved_by"],
        },
    }
    
    # Toggle credit approval
    new_status = 0 if row["credit_approved"] else 1
    
    if new_status:
        cur.execute("""
            UPDATE rmas
            SET credit_approved = 1,
                credit_approved_on = %s,
                credit_approved_by = %s
            WHERE rma_id = %s
        """, (now, session["user_id"], rma_id))
        flash("Credit approved.", "success")
    else:
        cur.execute("""
            UPDATE rmas
            SET credit_approved = 0,
                credit_approved_on = NULL,
                credit_approved_by = NULL
            WHERE rma_id = %s
        """, (rma_id,))
        flash("Credit approval removed.", "info")
    
    conn.commit()
    conn.close()
    
    return redirect(url_for("view_rma", rma_id=rma_id))


# ============ NOTIFICATION PREFERENCES ============

@app.route("/preferences/notifications", methods=["GET", "POST"])
@login_required
def notification_preferences():
    user_id = session["user_id"]
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    if request.method == "POST":
        # 1) Get the days threshold (number input)
        days_threshold = int(request.form.get("rma_age", 7))

        # 2) Helper to turn checkboxes into booleans
        def cb(name: str) -> bool:
            return name in request.form

        notify_sunday    = cb("notify_sunday")
        notify_monday    = cb("notify_monday")
        notify_tuesday   = cb("notify_tuesday")
        notify_wednesday = cb("notify_wednesday")
        notify_thursday  = cb("notify_thursday")
        notify_friday    = cb("notify_friday")
        notify_saturday  = cb("notify_saturday")

        # 3) Time dropdown (already a string like "09:00")
        notification_time = request.form.get("notification_time", "09:00")

        # 4) Update (or insert) into Postgres using booleans
        cur.execute(
            """
            UPDATE notification_preferences
            SET
                days_threshold   = %s,
                notify_sunday    = %s,
                notify_monday    = %s,
                notify_tuesday   = %s,
                notify_wednesday = %s,
                notify_thursday  = %s,
                notify_friday    = %s,
                notify_saturday  = %s,
                notification_time = %s
            WHERE user_id = %s
            """,
            (
                days_threshold,
                notify_sunday,
                notify_monday,
                notify_tuesday,
                notify_wednesday,
                notify_thursday,
                notify_friday,
                notify_saturday,
                notification_time,
                user_id,
            ),
        )

        conn.commit()
        flash("Notification preferences updated.", "success")
        return redirect(url_for("notification_preferences"))

    # GET: load existing prefs
    cur.execute(
        "SELECT * FROM notification_preferences WHERE user_id = %s",
        (user_id,),
    )
    prefs = cur.fetchone()

    if not prefs:
        prefs = {
            "days_threshold": 7,
            "notify_sunday": False,
            "notify_monday": True,
            "notify_tuesday": True,
            "notify_wednesday": True,
            "notify_thursday": True,
            "notify_friday": True,
            "notify_saturday": False,
            "notification_time": "09:00",
        }

    conn.close()
    return render_template("notifications.html", prefs=prefs)





# ============ ADMIN - MANUAL REMINDER TRIGGER ============

@app.route("/admin/send-reminders", methods=["POST"])
@login_required
def admin_send_reminders():
    """Manually trigger reminder emails (admin only)"""
    user = get_current_user()
    
    # Check if user is admin (you can customize this check)
    if user['role'] != 'admin':
        flash('You do not have permission to perform this action.', 'error')
        return redirect(url_for('index'))
    
    # Trigger the reminder script
    import subprocess
    try:
        result = subprocess.run(['python', 'send_reminders.py'], 
                              capture_output=True, 
                              text=True,
                              timeout=60)
        
        if result.returncode == 0:
            flash('Reminder emails sent successfully. Check logs for details.', 'success')
        else:
            flash(f'Error sending reminders: {result.stderr}', 'error')
    except Exception as e:
        flash(f'Error triggering reminders: {str(e)}', 'error')
    
    return redirect(url_for('index'))


# ============ ADMIN - USER MANAGEMENT ============

@app.route("/admin/users")
@admin_required
def admin_users():
    """List all users (admin only)"""
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT user_id, username, full_name, email, role, created_on, last_login
        FROM users
        ORDER BY created_on DESC
    """)
    users = cur.fetchall()
    conn.close()
    
    return render_template("admin_users.html", users=users)


@app.route("/admin/users/<int:user_id>/role", methods=["POST"])
@admin_required
def change_user_role(user_id):
    """Change a user's role (admin only)"""
    current_user = get_current_user()
    
    # Prevent changing own role
    if user_id == current_user['user_id']:
        flash('You cannot change your own role.', 'error')
        return redirect(url_for('admin_users'))
    
    new_role = request.form.get('role')
    if new_role not in ['user', 'admin']:
        flash('Invalid role.', 'error')
        return redirect(url_for('admin_users'))
    
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("""
        UPDATE users
        SET role = %s
        WHERE user_id = %s
    """, (new_role, user_id))
    
    conn.commit()
    conn.close()
    
    flash(f'User role updated to {new_role}.', 'success')
    return redirect(url_for('admin_users'))

@app.route("/admin/users/<int:user_id>/delete", methods=["POST"])
@admin_required
def delete_user(user_id):
    """Delete a user if they are not referenced by any RMAs/ownership."""
    current = get_current_user()

    # Don't let someone delete themself
    if current and current["user_id"] == user_id:
        flash("You cannot delete your own account.", "error")
        return redirect(url_for("admin_users"))

    conn = get_db()
    cur = conn.cursor()

    # 1) Check if this user is referenced by any RMAs
    cur.execute(
        """
        SELECT
            COUNT(*) AS rma_count
        FROM rmas r
        WHERE r.created_by_user_id = %s
           OR r.assigned_to_user_id = %s
           OR r.closed_by = %s
           OR r.acknowledged_by = %s
           OR r.credit_approved_by = %s
           OR r.credit_rejected_by = %s
        """,
        (user_id, user_id, user_id, user_id, user_id, user_id),
    )
    row = cur.fetchone()
    rma_count = row["rma_count"] if row and row["rma_count"] is not None else 0

    # 2) Check if they are listed as an owner on any RMAs
    cur.execute(
        """
        SELECT COUNT(*) AS owner_count
        FROM rma_owners
        WHERE user_id = %s
        """,
        (user_id,),
    )
    row2 = cur.fetchone()
    owner_count = row2["owner_count"] if row2 and row2["owner_count"] is not None else 0

    if rma_count > 0 or owner_count > 0:
        conn.close()
        flash(
            "Cannot delete user: they are referenced in existing RMAs/ownership. "
            "Reassign or clean up those RMAs first.",
            "error",
        )
        return redirect(url_for("admin_users"))

    # 3) Safe to delete: wipe notification prefs + the user row
    cur.execute(
        "DELETE FROM notification_preferences WHERE user_id = %s",
        (user_id,),
    )
    cur.execute(
        "DELETE FROM rma_owners WHERE user_id = %s",
        (user_id,),
    )
    cur.execute(
        "DELETE FROM users WHERE user_id = %s",
        (user_id,),
    )

    conn.commit()
    conn.close()

    flash("User deleted successfully.", "success")
    return redirect(url_for("admin_users"))




@app.route("/admin/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
def edit_user(user_id):
    """Edit a user's details (admin only, or edit yourself)"""
    current_user = get_current_user()
    
    # Only admins can access this page (users edit themselves via Profile)
    if current_user['role'] != 'admin':
        flash('You do not have permission to access this page.', 'error')
        return redirect(url_for('index'))
    conn = get_db()
    cur = conn.cursor()
    
    # Get user to edit
    cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
    user = cur.fetchone()
    
    if not user:
        conn.close()
        flash('User not found.', 'error')
        return redirect(url_for('admin_users'))
    
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip()
        new_password = request.form.get("new_password", "")
        
        if not all([full_name, email]):
            flash('Full name and email are required.', 'error')
            return render_template("edit_user.html", user=user, is_self=(user_id == current_user['user_id']))
        
        # Check if email is taken by another user
        cur.execute("SELECT user_id FROM users WHERE email = %s AND user_id != %s", (email, user_id))
        if cur.fetchone():
            conn.close()
            flash('email already in use by another user.', 'error')
            return render_template("edit_user.html", user=user, is_self=(user_id == current_user['user_id']))
        
        # Update user
        if new_password:
            if len(new_password) < 6:
                flash('Password must be at least 6 characters.', 'error')
                conn.close()
                return render_template("edit_user.html", user=user, is_self=(user_id == current_user['user_id']))
            
            password_hash = generate_password_hash(new_password)
            cur.execute("""
                UPDATE users 
                SET full_name = %s, email = %s, password_hash = %s
                WHERE user_id = %s
            """, (full_name, email, password_hash, user_id))
        else:
            cur.execute("""
                UPDATE users 
                SET full_name = %s, email = %s
                WHERE user_id = %s
            """, (full_name, email, user_id))
        
        conn.commit()
        conn.close()
        
        # Update session if editing self
        if user_id == current_user['user_id']:
            session['full_name'] = full_name
        
        flash('User updated successfully.', 'success')
        return redirect(url_for('admin_users'))
    
    conn.close()
    return render_template("edit_user.html", user=user, is_self=(user_id == current_user['user_id']))


# ============ CONTEXT PROCESSOR ============

@app.context_processor
def inject_user():
    return dict(current_user=get_current_user())

ensure_admin_user()


if __name__ == "__main__":
    # Optional: only seed admin locally, Render calls it at import time
    ensure_admin_user()
    app.run(host="0.0.0.0", port=10000, debug=False)
