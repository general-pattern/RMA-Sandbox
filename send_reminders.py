#!/usr/bin/env python3
"""
RMA Email Reminder System

Sends automated email reminders to owners about their open RMAs
based on their individual notification preferences.

Usage:
    python send_reminders.py

Schedule with Windows Task Scheduler or Linux cron for automatic reminders.
"""

import sqlite3
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

DB_PATH = "rma.db"

# Email configuration - same as app.py
EMAIL_CONFIG = {
    'enabled': True,
    'smtp_server': 'smtp.gmail.com',
    'smtp_port': 587,
    'sender_email': 'your-email@gmail.com',
    'sender_password': 'your-app-password',
    'base_url': 'http://127.0.0.1:5000'
}


def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def should_send_reminder(owner_prefs):
    """
    Check if owner should receive a reminder based on their preferences
    
    Args:
        owner_prefs: dict with EmailEnabled, Frequency, LastSent
    
    Returns:
        bool: True if reminder should be sent
    """
    if not owner_prefs['EmailEnabled']:
        return False
    
    if not owner_prefs['LastSent']:
        return True  # Never sent before
    
    try:
        last_sent = datetime.strptime(owner_prefs['LastSent'], "%Y-%m-%d %H:%M:%S")
    except:
        return True  # Invalid date, send anyway
    
    now = datetime.now()
    days_since_last = (now - last_sent).days
    
    frequency = owner_prefs['Frequency']
    
    if frequency == 'daily':
        return days_since_last >= 1
    elif frequency == 'every_3_days':
        return days_since_last >= 3
    elif frequency == 'weekly':
        return days_since_last >= 7
    else:
        return days_since_last >= 1  # Default to daily


def get_rmas_for_reminder(owner_id, age_threshold):
    """
    Get RMAs assigned to owner that meet the age threshold
    
    Args:
        owner_id: int
        age_threshold: int (days)
    
    Returns:
        list of RMA dicts
    """
    conn = get_db()
    cur = conn.cursor()
    
    query = """
        SELECT DISTINCT r.RMAID, r.DateOpened, r.Status, r.CustomerComplaintDesc,
               c.CustomerName
        FROM rmas r
        JOIN rma_owners ro ON r.RMAID = ro.RMAID
        JOIN customers c ON r.CustomerID = c.CustomerID
        WHERE ro.OwnerID = ?
          AND r.Status NOT IN ('Closed', 'Rejected')
          AND DATE(r.DateOpened) <= DATE('now', '-' || ? || ' days')
        ORDER BY r.DateOpened ASC
    """
    
    cur.execute(query, (owner_id, age_threshold))
    rmas = cur.fetchall()
    conn.close()
    
    return rmas


def calculate_days_open(date_opened):
    """Calculate how many days an RMA has been open"""
    try:
        opened = datetime.strptime(date_opened, "%Y-%m-%d %H:%M:%S")
        now = datetime.now()
        return (now - opened).days
    except:
        return 0


def send_reminder_email(owner, rmas):
    """
    Send reminder email to owner
    
    Args:
        owner: dict with OwnerName, OwnerEmail
        rmas: list of RMA dicts
    
    Returns:
        bool: True if sent successfully
    """
    if not EMAIL_CONFIG['enabled']:
        print(f"  Email disabled in config - skipping {owner['OwnerName']}")
        return False
    
    if not rmas:
        print(f"  No RMAs to notify for {owner['OwnerName']}")
        return False
    
    # Build email
    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"RMA Reminder - You have {len(rmas)} open RMA{'s' if len(rmas) != 1 else ''} requiring attention"
    msg['From'] = EMAIL_CONFIG['sender_email']
    msg['To'] = owner['OwnerEmail']
    
    # Plain text version
    text_body = f"""Hi {owner['OwnerName']},

You have {len(rmas)} open RMA{'s' if len(rmas) != 1 else ''} requiring attention:

"""
    
    for idx, rma in enumerate(rmas, 1):
        days_open = calculate_days_open(rma['DateOpened'])
        rma_code = f"RMA{rma['RMAID']:04d}"
        text_body += f"""{idx}. {rma_code} - {rma['CustomerName']} ({days_open} days old)
   Status: {rma['Status']}
   Customer Complaint: {rma['CustomerComplaintDesc'] or 'N/A'}
   View RMA: {EMAIL_CONFIG['base_url']}/rmas/{rma['RMAID']}

"""
    
    text_body += """Please review and update these RMAs at your earliest convenience.

---
You're receiving this because you have email reminders enabled.
Update your preferences: """ + EMAIL_CONFIG['base_url'] + "/profile"
    
    # HTML version
    html_body = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .header {{ background-color: #2563eb; color: white; padding: 20px; border-radius: 5px; }}
            .rma-item {{ 
                background-color: #f9fafb; 
                border-left: 4px solid #2563eb; 
                padding: 15px; 
                margin: 10px 0; 
                border-radius: 3px;
            }}
            .rma-code {{ font-weight: bold; font-size: 16px; color: #1f2937; }}
            .customer {{ color: #6b7280; }}
            .days-old {{ 
                display: inline-block;
                background-color: #fef3c7;
                color: #92400e;
                padding: 2px 8px;
                border-radius: 3px;
                font-size: 12px;
                font-weight: 600;
            }}
            .status {{ 
                display: inline-block;
                padding: 2px 8px;
                border-radius: 3px;
                font-size: 12px;
                font-weight: 600;
            }}
            .view-link {{ 
                display: inline-block;
                background-color: #2563eb;
                color: white;
                padding: 8px 16px;
                text-decoration: none;
                border-radius: 4px;
                margin-top: 10px;
            }}
            .footer {{ 
                margin-top: 30px;
                padding-top: 20px;
                border-top: 1px solid #e5e7eb;
                color: #6b7280;
                font-size: 12px;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h2 style="margin: 0;">RMA Reminder</h2>
        </div>
        
        <p>Hi {owner['OwnerName']},</p>
        
        <p>You have <strong>{len(rmas)}</strong> open RMA{'s' if len(rmas) != 1 else ''} requiring attention:</p>
    """
    
    for idx, rma in enumerate(rmas, 1):
        days_open = calculate_days_open(rma['DateOpened'])
        rma_code = f"RMA{rma['RMAID']:04d}"
        
        html_body += f"""
        <div class="rma-item">
            <div>
                <span class="rma-code">{rma_code}</span> - 
                <span class="customer">{rma['CustomerName']}</span>
                <span class="days-old">{days_open} days old</span>
            </div>
            <div style="margin-top: 5px;">
                <strong>Status:</strong> {rma['Status']}<br>
                <strong>Customer Complaint:</strong> {rma['CustomerComplaintDesc'] or 'N/A'}
            </div>
            <a href="{EMAIL_CONFIG['base_url']}/rmas/{rma['RMAID']}" class="view-link">View RMA →</a>
        </div>
        """
    
    html_body += f"""
        <p>Please review and update these RMAs at your earliest convenience.</p>
        
        <div class="footer">
            <p>You're receiving this because you have email reminders enabled.</p>
            <p><a href="{EMAIL_CONFIG['base_url']}/profile">Update your preferences</a></p>
        </div>
    </body>
    </html>
    """
    
    # Attach both versions
    part1 = MIMEText(text_body, 'plain')
    part2 = MIMEText(html_body, 'html')
    msg.attach(part1)
    msg.attach(part2)
    
    # Send email
    try:
        server = smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port'])
        server.starttls()
        server.login(EMAIL_CONFIG['sender_email'], EMAIL_CONFIG['sender_password'])
        server.send_message(msg)
        server.quit()
        print(f"  ✓ Sent reminder to {owner['OwnerName']} ({len(rmas)} RMAs)")
        return True
    except Exception as e:
        print(f"  ✗ Failed to send to {owner['OwnerName']}: {e}")
        return False


def update_last_sent(owner_id):
    """Update the LastSent timestamp for an owner"""
    conn = get_db()
    cur = conn.cursor()
    
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("""
        UPDATE owner_notification_preferences
        SET LastSent = ?
        WHERE OwnerID = ?
    """, (now, owner_id))
    
    conn.commit()
    conn.close()


def main():
    """Main function to process all reminders"""
    print("="*70)
    print("RMA Email Reminder System")
    print("="*70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    if not EMAIL_CONFIG['enabled']:
        print("⚠️  Email is DISABLED in configuration")
        print("   Enable it in EMAIL_CONFIG to send reminders")
        return
    
    conn = get_db()
    cur = conn.cursor()
    
    # Get all owners with their preferences
    cur.execute("""
        SELECT o.OwnerID, o.OwnerName, o.OwnerEmail,
               p.EmailEnabled, p.Frequency, p.RMAAge, p.LastSent
        FROM internal_owners o
        LEFT JOIN owner_notification_preferences p ON o.OwnerID = p.OwnerID
    """)
    owners = cur.fetchall()
    conn.close()
    
    if not owners:
        print("No owners found in database")
        return
    
    print(f"Processing {len(owners)} owners...")
    print()
    
    sent_count = 0
    skipped_count = 0
    
    for owner in owners:
        owner_dict = dict(owner)
        print(f"• {owner_dict['OwnerName']}:")
        
        # Check if should send
        if not should_send_reminder(owner_dict):
            freq = owner_dict.get('Frequency', 'daily')
            last = owner_dict.get('LastSent', 'Never')
            print(f"  ⊘ Skipping (Freq: {freq}, Last sent: {last})")
            skipped_count += 1
            continue
        
        if not owner_dict['EmailEnabled']:
            print(f"  ⊘ Email reminders disabled")
            skipped_count += 1
            continue
        
        # Get RMAs for this owner
        age_threshold = owner_dict.get('RMAAge', 3)
        rmas = get_rmas_for_reminder(owner_dict['OwnerID'], age_threshold)
        
        if not rmas:
            print(f"  ℹ No RMAs meet criteria (Age threshold: {age_threshold} days)")
            skipped_count += 1
            continue
        
        # Send email
        if send_reminder_email(owner_dict, rmas):
            update_last_sent(owner_dict['OwnerID'])
            sent_count += 1
        else:
            skipped_count += 1
    
    print()
    print("="*70)
    print(f"Summary:")
    print(f"  • Emails sent: {sent_count}")
    print(f"  • Skipped: {skipped_count}")
    print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)


if __name__ == "__main__":
    main()
