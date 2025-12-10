```markdown

\# Complete Deployment Guide



\## 🎯 Step-by-Step Deployment to Render.com



\### Prerequisites

\- GitHub account

\- Render.com account (free)

\- Your RMA app code



\### Step 1: Prepare Your Code



1\. \*\*Remove database files from git\*\*

&nbsp;  ```bash

&nbsp;  cd /path/to/RMA\_app

&nbsp;  git rm --cached rma.db rma.db.backup

&nbsp;  git add .gitignore

&nbsp;  git commit -m "Remove database files from tracking"

&nbsp;  ```



2\. \*\*Verify all new files are present\*\*

&nbsp;  - \[ ] Procfile

&nbsp;  - \[ ] startup.sh

&nbsp;  - \[ ] requirements.txt (updated)

&nbsp;  - \[ ] runtime.txt

&nbsp;  - \[ ] .env.example

&nbsp;  - \[ ] .gitignore (updated)



3\. \*\*Make startup.sh executable\*\*

&nbsp;  ```bash

&nbsp;  chmod +x startup.sh

&nbsp;  ```



4\. \*\*Generate SECRET\_KEY\*\*

&nbsp;  ```bash

&nbsp;  python -c "import secrets; print(secrets.token\_hex(32))"

&nbsp;  ```

&nbsp;  Save this - you'll need it for Render!



\### Step 2: Push to GitHub



1\. \*\*Add all changes\*\*

&nbsp;  ```bash

&nbsp;  git add .

&nbsp;  git commit -m "Prepare RMA system for production deployment"

&nbsp;  git push origin main

&nbsp;  ```



2\. \*\*Verify on GitHub\*\*

&nbsp;  - Check that rma.db is NOT in the repository

&nbsp;  - Confirm all new files are there



\### Step 3: Deploy on Render



1\. \*\*Create new Web Service\*\*

&nbsp;  - Go to https://dashboard.render.com

&nbsp;  - Click "New +" → "Web Service"

&nbsp;  - Connect your GitHub account

&nbsp;  - Select your RMA\_app repository



2\. \*\*Configure Service\*\*

&nbsp;  ```

&nbsp;  Name: rma-system

&nbsp;  Region: Oregon (US West) or closest to you

&nbsp;  Branch: main

&nbsp;  Runtime: Python 3

&nbsp;  Build Command: pip install -r requirements.txt

&nbsp;  Start Command: bash startup.sh

&nbsp;  ```



3\. \*\*Add Environment Variables\*\*

&nbsp;  Click "Advanced" → "Add Environment Variable"

&nbsp;  

&nbsp;  Add these:

&nbsp;  ```

&nbsp;  SECRET\_KEY = \[paste the key you generated]

&nbsp;  FLASK\_ENV = production

&nbsp;  ```



4\. \*\*Configure Instance\*\*

&nbsp;  - Instance Type: Free

&nbsp;  - Auto-Deploy: Yes



5\. \*\*Create Web Service\*\*

&nbsp;  - Click "Create Web Service"

&nbsp;  - Wait 5-10 minutes for deployment



\### Step 4: First Login \& Setup



1\. \*\*Access your app\*\*

&nbsp;  - URL will be: `https://rma-system.onrender.com` (or your custom name)



2\. \*\*Login with default admin\*\*

&nbsp;  - Username: `admin`

&nbsp;  - Password: `Admin123!`



3\. \*\*IMMEDIATELY change admin password\*\*

&nbsp;  - Click user menu → Profile

&nbsp;  - Update password

&nbsp;  - Save changes



4\. \*\*Create your account\*\*

&nbsp;  - Admin → Manage Users → Add User

&nbsp;  - Create your personal admin account

&nbsp;  - Logout and login with your account



5\. \*\*Delete default admin\*\* (optional but recommended)

&nbsp;  - Admin → Manage Users

&nbsp;  - Delete the default `admin` account



\### Step 5: Configure Application



1\. \*\*Add Customers\*\*

&nbsp;  - Admin → Customers → Add Customer

&nbsp;  - Add all your customers



2\. \*\*Add Internal Owners\*\*

&nbsp;  - Admin → Internal Owners → Add Owner

&nbsp;  - Add all staff who will handle RMAs



3\. \*\*Create Users\*\*

&nbsp;  - Admin → Manage Users → Add User

&nbsp;  - Create accounts for all staff



4\. \*\*Test RMA Creation\*\*

&nbsp;  - RMAs → New RMA

&nbsp;  - Create test RMA

&nbsp;  - Verify everything works



\### Step 6: Email Setup (Optional)



If you want email notifications:



1\. \*\*Get Gmail App Password\*\*

&nbsp;  - Go to myaccount.google.com

&nbsp;  - Security → 2-Step Verification

&nbsp;  - App passwords → Generate

&nbsp;  - Copy the 16-character password



2\. \*\*Update app.py on GitHub\*\*

&nbsp;  ```python

&nbsp;  EMAIL\_CONFIG = {

&nbsp;      'enabled': True,

&nbsp;      'smtp\_server': 'smtp.gmail.com',

&nbsp;      'smtp\_port': 587,

&nbsp;      'sender\_email': 'your-email@gmail.com',

&nbsp;      'sender\_password': 'your-16-char-app-password',

&nbsp;      'base\_url': 'https://rma-system.onrender.com'

&nbsp;  }

&nbsp;  ```



3\. \*\*Push update\*\*

&nbsp;  ```bash

&nbsp;  git add app.py

&nbsp;  git commit -m "Enable email notifications"

&nbsp;  git push

&nbsp;  ```



4\. \*\*Wait for auto-redeploy\*\* (5 mins)



5\. \*\*Test notifications\*\*

&nbsp;  - Create RMA with owner assigned

&nbsp;  - Owner should receive email



\## 🔍 Monitoring Your App



\### View Logs

\- Dashboard → Your Service → Logs

\- Shows real-time application output



\### Check Health

\- Dashboard → Your Service → Events

\- Shows deployment history



\### Monitor Usage

\- Dashboard → Your Service → Metrics

\- CPU, Memory, Request stats



\## 🐛 Common Issues \& Fixes



\### Issue: App won't start

\*\*Solution:\*\*

\- Check logs for errors

\- Verify startup.sh has correct permissions

\- Check environment variables are set



\### Issue: Database resets on restart

\*\*Solution:\*\*

\- Render free tier doesn't persist files

\- Upgrade to paid tier ($7/month) for disk persistence

\- Or use external database (PostgreSQL)



\### Issue: Attachments disappear

\*\*Solution:\*\*

\- Same as database - need paid tier for file persistence

\- Or use external storage (S3, Cloudinary)



\### Issue: Can't login after deployment

\*\*Solution:\*\*

\- Database was reinitialized

\- Use default: admin / Admin123!

\- Check logs for startup errors



\## 💰 Cost Considerations



\### Free Tier Limitations

\- ✅ Unlimited apps

\- ✅ Automatic HTTPS

\- ⚠️ Sleeps after 15 min inactivity (takes 30s to wake)

\- ⚠️ Database/files reset on restart

\- ⚠️ 750 hours/month compute



\### Upgrade to Paid ($7/month)

\- ✅ No sleep

\- ✅ Persistent disk (10GB)

\- ✅ Better performance

\- ✅ More compute hours



\### Recommended for Production

\- Start with free tier for testing

\- Upgrade once you're sure it works

\- Or use Railway.app (similar pricing, better free tier)



\## 🔄 Making Updates



1\. \*\*Make changes locally\*\*

&nbsp;  ```bash

&nbsp;  # Edit files

&nbsp;  git add .

&nbsp;  git commit -m "Update description"

&nbsp;  git push

&nbsp;  ```



2\. \*\*Render auto-deploys\*\*

&nbsp;  - Detects push

&nbsp;  - Rebuilds automatically

&nbsp;  - Live in 5-10 minutes



3\. \*\*Manual deploy\*\*

&nbsp;  - Dashboard → Your Service

&nbsp;  - Click "Manual Deploy" → "Deploy latest commit"



\## 🎉 Success!



Your RMA system should now be:

\- ✅ Live on the internet

\- ✅ Accessible from any device

\- ✅ Secure with HTTPS

\- ✅ Ready for production use



\*\*Next Steps:\*\*

1\. Share URL with your team

2\. Train users on the system

3\. Monitor usage for first week

4\. Consider upgrading for persistence

5\. Set up regular backups



\*\*Need help?\*\* Check Render docs: https://render.com/docs

```



---

