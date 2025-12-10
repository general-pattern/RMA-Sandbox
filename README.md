```markdown

\# RMA System - Returns \& Rework Tracking



A comprehensive Flask-based web application for managing Return Merchandise Authorizations (RMAs) with advanced tracking, notifications, and analytics.



\## 🚀 Features



\- \*\*RMA Management\*\*: Create, track, and manage returns from creation to closure

\- \*\*Status Workflow\*\*: Draft → Acknowledged → In Progress → Closed/Rejected

\- \*\*Multiple Owners\*\*: Assign multiple internal owners to each RMA

\- \*\*Email Notifications\*\*: Automatic email alerts for new assignments

\- \*\*Dispositions\*\*: Track failure analysis, root cause, and corrective actions

\- \*\*Metrics Dashboard\*\*: Real-time analytics and reporting

\- \*\*File Attachments\*\*: Upload and manage documents per RMA

\- \*\*Audit Trail\*\*: Complete history of status changes and modifications

\- \*\*User Management\*\*: Role-based access control (Admin/User)

\- \*\*Undo Functionality\*\*: Revert recent changes



\## 📋 Requirements



\- Python 3.11+

\- SQLite3

\- Flask and dependencies (see requirements.txt)



\## 🛠️ Local Development Setup



1\. \*\*Clone the repository\*\*

&nbsp;  ```bash

&nbsp;  git clone 

&nbsp;  cd RMA\_app

&nbsp;  ```



2\. \*\*Create virtual environment\*\*

&nbsp;  ```bash

&nbsp;  python -m venv venv

&nbsp;  source venv/bin/activate  # On Windows: venv\\Scripts\\activate

&nbsp;  ```



3\. \*\*Install dependencies\*\*

&nbsp;  ```bash

&nbsp;  pip install -r requirements.txt

&nbsp;  ```



4\. \*\*Initialize database\*\*

&nbsp;  ```bash

&nbsp;  python init\_db.py

&nbsp;  python migrate\_db.py

&nbsp;  python migrate\_multiple\_owners.py

&nbsp;  ```



5\. \*\*Set environment variables\*\*

&nbsp;  ```bash

&nbsp;  cp .env.example .env

&nbsp;  # Edit .env with your settings

&nbsp;  ```



6\. \*\*Run the application\*\*

&nbsp;  ```bash

&nbsp;  python app.py

&nbsp;  ```



7\. \*\*Access the app\*\*

&nbsp;  - Open browser to `http://localhost:10000`

&nbsp;  - Default admin login: `admin` / `Admin123!`

&nbsp;  - \*\*⚠️ Change this immediately!\*\*



\## 🚢 Deployment (Render.com)



1\. \*\*Prepare for deployment\*\*

&nbsp;  ```bash

&nbsp;  # Remove database from git if tracked

&nbsp;  git rm --cached rma.db rma.db.backup

&nbsp;  git commit -m "Remove database files"

&nbsp;  ```



2\. \*\*Push to GitHub\*\*

&nbsp;  ```bash

&nbsp;  git add .

&nbsp;  git commit -m "Prepare for deployment"

&nbsp;  git push origin main

&nbsp;  ```



3\. \*\*Deploy on Render\*\*

&nbsp;  - Go to https://render.com

&nbsp;  - Click "New +" → "Web Service"

&nbsp;  - Connect your GitHub repository

&nbsp;  - Configure:

&nbsp;    - \*\*Name\*\*: rma-system (or your choice)

&nbsp;    - \*\*Environment\*\*: Python 3

&nbsp;    - \*\*Build Command\*\*: `pip install -r requirements.txt`

&nbsp;    - \*\*Start Command\*\*: `bash startup.sh`

&nbsp;  - Add environment variables:

&nbsp;    - `SECRET\_KEY`: Generate with `python -c 'import secrets; print(secrets.token\_hex(32))'`

&nbsp;    - `FLASK\_ENV`: production

&nbsp;  - Click "Create Web Service"



4\. \*\*First login\*\*

&nbsp;  - Visit your deployed URL

&nbsp;  - Login with: `admin` / `Admin123!`

&nbsp;  - Go to Profile → Change password immediately

&nbsp;  - Create additional users as needed



\## 📧 Email Configuration



To enable email notifications:



1\. \*\*Get Gmail App Password\*\*

&nbsp;  - Go to Google Account settings

&nbsp;  - Security → 2-Step Verification → App passwords

&nbsp;  - Generate password for "Mail"



2\. \*\*Update app.py\*\*

&nbsp;  ```python

&nbsp;  EMAIL\_CONFIG = {

&nbsp;      'enabled': True,

&nbsp;      'smtp\_server': 'smtp.gmail.com',

&nbsp;      'smtp\_port': 587,

&nbsp;      'sender\_email': 'your-email@gmail.com',

&nbsp;      'sender\_password': 'your-app-password',

&nbsp;      'base\_url': 'https://your-app.onrender.com'

&nbsp;  }

&nbsp;  ```



3\. \*\*Configure notification preferences\*\*

&nbsp;  - Each owner can customize in Profile → Notifications



\## 🔧 Maintenance



\### Backup Database

```bash

python -c "import shutil; from datetime import datetime; shutil.copy('rma.db', f'rma\_backup\_{datetime.now().strftime(\\"%Y%m%d\_%H%M%S\\")}.db')"

```



\### Send Manual Reminders

```bash

python send\_reminders.py

```



\### View Logs

```bash

\# On Render

render logs --tail

```



\## 👥 Default Roles



\- \*\*Admin\*\*: Full access, can manage users, customers, owners

\- \*\*User\*\*: Can create and manage RMAs, view all data



\## 📚 Project Structure



```

RMA\_app/

├── app.py                 # Main Flask application

├── schema.sql            # Database schema

├── init\_db.py            # Database initialization

├── migrate\_db.py         # Database migrations

├── requirements.txt      # Python dependencies

├── Procfile             # Deployment config

├── startup.sh           # Startup script

├── templates/           # HTML templates

├── static/             # CSS, JS, images

└── uploads/            # File attachments (gitignored)

```



\## 🐛 Troubleshooting



\*\*Database not found\*\*

\- Run `python init\_db.py`



\*\*Permission denied on startup.sh\*\*

\- Run `chmod +x startup.sh`



\*\*Email not sending\*\*

\- Check EMAIL\_CONFIG in app.py

\- Verify Gmail app password

\- Check firewall/port 587



\*\*Can't login\*\*

\- Reset admin password in database directly

\- Or delete rma.db and reinitialize



\## 📝 License



Internal use only - Not for public distribution



\## 👤 Author



Megan Beckman - Quality Control Department



\## 🙏 Support



For issues or questions, contact your system administrator.

```



---

