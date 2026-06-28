#!/bin/bash
# Installs GetAJob as a macOS LaunchAgent (auto-starts on login, restarts on crash).
set -e

LABEL="com.getajob"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

mkdir -p "$HOME/Library/LaunchAgents"
mkdir -p "$SCRIPT_DIR/data"

cat > "$PLIST" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$SCRIPT_DIR/run.sh</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>ThrottleInterval</key>
    <integer>60</integer>
    <key>StandardOutPath</key>
    <string>$SCRIPT_DIR/data/service.log</string>
    <key>StandardErrorPath</key>
    <string>$SCRIPT_DIR/data/service.err</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>HOME</key>
        <string>$HOME</string>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin</string>
    </dict>
</dict>
</plist>
PLIST_EOF

launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"

echo ""
echo "✓ GetAJob service installed and running"
echo "  Dashboard: http://localhost:8000"
echo "  Logs:      $SCRIPT_DIR/data/service.log"
echo "  Errors:    $SCRIPT_DIR/data/service.err"
echo ""
echo "  Stop:      launchctl unload $PLIST"
echo "  Remove:    bash $SCRIPT_DIR/uninstall_service.sh"
