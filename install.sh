#!/bin/bash

# RMA System Enhancement Installation Script
# This script helps you install all the new features safely

echo "╔══════════════════════════════════════════════════════════╗"
echo "║  RMA System Enhancement - Installation Script           ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# Check if we're in the right directory
if [ ! -f "rma.db" ]; then
    echo "❌ Error: rma.db not found in current directory"
    echo "   Please run this script from your RMA system directory"
    exit 1
fi

echo "✓ Found rma.db in current directory"
echo ""

# Step 1: Backup
echo "Step 1: Creating backup..."
BACKUP_DIR="backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
cp rma.db "$BACKUP_DIR/rma.db"
cp app.py "$BACKUP_DIR/app.py" 2>/dev/null || true
cp -r templates "$BACKUP_DIR/" 2>/dev/null || true
cp -r static "$BACKUP_DIR/" 2>/dev/null || true
echo "✓ Backup created in: $BACKUP_DIR"
echo ""

# Step 2: Run migration
echo "Step 2: Running database migration..."
if [ ! -f "migrate_db.py" ]; then
    echo "❌ Error: migrate_db.py not found"
    echo "   Please ensure all files are in the current directory"
    exit 1
fi

python3 migrate_db.py
if [ $? -eq 0 ]; then
    echo "✓ Database migration completed successfully"
else
    echo "❌ Migration failed - check error messages above"
    exit 1
fi
echo ""

# Step 3: Check for required files
echo "Step 3: Checking for required files..."
MISSING_FILES=0

for file in "app.py" "metrics.html" "rma_detail.html" "base.html" "style.css"; do
    if [ ! -f "$file" ]; then
        echo "❌ Missing: $file"
        MISSING_FILES=$((MISSING_FILES + 1))
    else
        echo "✓ Found: $file"
    fi
done

if [ $MISSING_FILES -gt 0 ]; then
    echo ""
    echo "❌ Missing $MISSING_FILES required file(s)"
    echo "   Please copy all updated files to this directory first"
    exit 1
fi
echo ""

# Step 4: Copy templates
echo "Step 4: Installing templates..."
mkdir -p templates
cp metrics.html templates/
cp rma_detail.html templates/
cp base.html templates/
echo "✓ Templates installed"
echo ""

# Step 5: Copy static files
echo "Step 5: Installing static files..."
mkdir -p static
cp style.css static/
echo "✓ Static files installed"
echo ""

# Step 6: Summary
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  Installation Complete!                                  ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "✓ Database migrated"
echo "✓ Files installed"
echo "✓ Backup saved to: $BACKUP_DIR"
echo ""
echo "Next steps:"
echo "1. Restart your Flask application:"
echo "   python3 app.py"
echo ""
echo "2. Test the new features:"
echo "   - Open an RMA to see time tracking"
echo "   - Click '📊 Metrics' in the navigation"
echo "   - Test credit approval on an RMA"
echo "   - Edit an RMA to add a credit memo number"
echo ""
echo "📚 Documentation:"
echo "   - Quick Start: QUICK_REFERENCE.md"
echo "   - Full Guide: README_NEW_FEATURES.md"
echo "   - Workflows: WORKFLOW_GUIDE.md"
echo ""
echo "🎉 Enjoy your enhanced RMA system!"
