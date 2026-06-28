#!/bin/bash
PLIST="$HOME/Library/LaunchAgents/com.getajob.plist"
launchctl unload "$PLIST" 2>/dev/null || true
rm -f "$PLIST"
echo "✓ GetAJob service removed"
