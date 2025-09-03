#!/bin/bash

set -e

APP_NAME="micro-cap-portfolio-manager"
VERSION="1.0.0"
DIST_NAME="${APP_NAME}-v${VERSION}"

echo "Creating distribution package: ${DIST_NAME}"

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf dist/

# Create distribution directory
echo "Creating distribution directory..."
mkdir -p "dist/${DIST_NAME}"

# Copy source code (excluding development files) - using cp instead of rsync
echo "Copying source code..."
cp -r . "dist/${DIST_NAME}/source/"

# Clean up unwanted files from the copy
echo "Cleaning up development files..."
cd "dist/${DIST_NAME}/source/"
rm -rf .git tests/ .pytest_cache __pycache__ archive/ .env dist/ build/ 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
cd ../../..

# Copy installer
echo "Copying installer..."
cp deploy/install.sh "dist/${DIST_NAME}/"
chmod +x "dist/${DIST_NAME}/install.sh"

# Create README for distribution
echo "Creating distribution README..."
cat > "dist/${DIST_NAME}/README.txt" << 'READMEEOF'
Micro-Cap Portfolio Manager v1.0.0
==================================

A professional portfolio management application for micro-cap stock trading
with real-time data, performance tracking, and comprehensive analytics.

Features:
✅ Real-time market data (Finnhub, Yahoo Finance)
✅ Portfolio tracking and performance analysis
✅ Risk management tools
✅ Historical data analysis (up to 6 months)
✅ Daily portfolio summaries
✅ Professional-grade logging and error handling

INSTALLATION INSTRUCTIONS:
=========================

1. Open Terminal (Applications → Utilities → Terminal)

2. Navigate to this folder:
   cd /path/to/micro-cap-portfolio-manager-v1.0.0

3. Run the installer:
   chmod +x install.sh
   ./install.sh

4. After installation, start the application:
   portfolio-manager

5. Open your browser to: http://localhost:8501

FIRST-TIME SETUP:
================

Demo Mode (Synthetic Data):
- App starts in demo mode by default
- No API key required
- Perfect for testing and learning

Live Trading Mode:
1. Get free API key from: https://finnhub.io
2. Edit configuration: ~/.portfolio-manager/src/.env
3. Set: APP_ENV=production
4. Set: FINNHUB_API_KEY=your_key_here
5. Restart the application

SUPPORT:
========

- Data is stored in: ~/.portfolio-manager/data/
- Configuration: ~/.portfolio-manager/src/.env
- Logs: Check terminal output for any issues

Requirements:
- macOS 10.14+ (Mojave or later)
- Python 3.11+ (downloads from python.org if needed)
- Internet connection for live data

Enjoy your portfolio management! 📈
READMEEOF

# Create system requirements check script
echo "Creating system check script..."
cat > "dist/${DIST_NAME}/check_system.sh" << 'CHECKEOF'
#!/bin/bash

echo "Portfolio Manager - System Requirements Check"
echo "============================================="
echo ""

# Check macOS version
echo "macOS Version:"
sw_vers
echo ""

# Check Python
echo "Python Check:"
if command -v python3 &> /dev/null; then
    python3 --version
    if python3 --version | grep -E "3\.(11|12|13)" > /dev/null; then
        echo "✅ Python version is compatible"
    else
        echo "❌ Python 3.11+ required"
        echo "Download from: https://python.org"
    fi
else
    echo "❌ Python 3 not found"
    echo "Download from: https://python.org"
fi
echo ""

# Check internet connectivity
echo "Internet Connectivity:"
if ping -c 1 google.com &> /dev/null; then
    echo "✅ Internet connection active"
else
    echo "⚠️  No internet connection (required for live data)"
fi
echo ""

# Check available disk space
echo "Disk Space:"
df -h ~ | head -2
echo ""

echo "System check complete!"
CHECKEOF

chmod +x "dist/${DIST_NAME}/check_system.sh"

# Create uninstaller
echo "Creating uninstaller..."
cat > "dist/${DIST_NAME}/uninstall.sh" << 'UNINSTALLEOF'
#!/bin/bash

APP_NAME="portfolio-manager"
INSTALL_DIR="$HOME/.${APP_NAME}"

echo "Portfolio Manager Uninstaller"
echo "============================="
echo ""

if [ ! -d "${INSTALL_DIR}" ]; then
    echo "Portfolio Manager is not installed."
    exit 0
fi

echo "This will remove:"
echo "- Application: ${INSTALL_DIR}"
echo "- Command launcher: /usr/local/bin/${APP_NAME}"
echo "- Desktop shortcut: ~/Desktop/Micro-Cap Portfolio Manager.command"
echo ""
echo "⚠️  Your data will be backed up to: ${INSTALL_DIR}.backup"
echo ""

read -p "Continue with uninstall? (y/N): " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Uninstall cancelled."
    exit 0
fi

# Backup data
if [ -d "${INSTALL_DIR}/data" ]; then
    echo "Backing up your data..."
    cp -r "${INSTALL_DIR}/data" "${INSTALL_DIR}.backup" 2>/dev/null || true
fi

# Remove installation
echo "Removing application..."
rm -rf "${INSTALL_DIR}"

# Remove launcher
echo "Removing command launcher..."
sudo rm -f "/usr/local/bin/${APP_NAME}"

# Remove desktop shortcut
echo "Removing desktop shortcut..."
rm -f "$HOME/Desktop/Micro-Cap Portfolio Manager.command"

echo ""
echo "✅ Portfolio Manager has been uninstalled."
echo "📁 Your data backup: ${INSTALL_DIR}.backup"
echo ""
UNINSTALLEOF

chmod +x "dist/${DIST_NAME}/uninstall.sh"

# Create archives
echo "Creating archives..."
cd dist/

# Create tar.gz archive
echo "Creating ${DIST_NAME}.tar.gz..."
tar -czf "${DIST_NAME}.tar.gz" "${DIST_NAME}/"

# Create zip archive  
echo "Creating ${DIST_NAME}.zip..."
zip -r "${DIST_NAME}.zip" "${DIST_NAME}/" > /dev/null 2>&1 || zip -r "${DIST_NAME}.zip" "${DIST_NAME}/"

cd ..

echo ""
echo "✅ Distribution package created successfully!"
echo "📦 dist/${DIST_NAME}.tar.gz"
echo "📦 dist/${DIST_NAME}.zip"
echo ""
echo "Distribution contents:"
ls -la "dist/${DIST_NAME}/"
echo ""
echo "Archive sizes:"
ls -lh dist/*.tar.gz dist/*.zip 2>/dev/null || echo "Archives created"
echo ""
echo "🚀 Ready for deployment!"
echo ""
echo "To test locally:"
echo "1. cd dist/${DIST_NAME}"
echo "2. ./check_system.sh"
echo "3. ./install.sh"