#!/bin/bash

echo "🚀 Starting RMA System..."

# We are now using Postgres/Neon instead of local SQLite.
# Skip old SQLite init/migration scripts on Render.

echo "📊 Skipping SQLite init_db.py and migrate_db.py (using Postgres/Neon)..."
echo "🔄 Skipping migrate_consolidate_users.py (legacy SQLite migration)..."

echo "✅ Database assumed ready (tables managed via Neon SQL script)"

# Start the application
echo "🌐 Starting web server on port ${PORT:-10000}..."
exec gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120
