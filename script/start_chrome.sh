#!/bin/bash

# Start Chrome with remote debugging enabled
# This script starts Chrome with the necessary flags for remote debugging

echo "Starting Chrome with remote debugging on port 9222..."

# Kill any existing Chrome processes (optional)
# pkill -f "Google Chrome"

# Start Chrome with remote debugging
# Note: You may need to adjust the path to Chrome based on your system
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
        --remote-debugging-port=9222 \
        --user-data-dir=/tmp/chrome-debug \
        --no-first-run \
        --no-default-browser-check \
        --disable-default-apps \
        --disable-popup-blocking \
        --disable-background-timer-throttling \
        --disable-backgrounding-occluded-windows \
        --disable-renderer-backgrounding \
        --disable-features=TranslateUI \
        --disable-ipc-flooding-protection
else
    # Linux
    google-chrome \
        --remote-debugging-port=9222 \
        --user-data-dir=/tmp/chrome-debug \
        --no-first-run \
        --no-default-browser-check \
        --disable-default-apps \
        --disable-popup-blocking \
        --disable-background-timer-throttling \
        --disable-backgrounding-occluded-windows \
        --disable-renderer-backgrounding \
        --disable-features=TranslateUI \
        --disable-ipc-flooding-protection
fi

echo "Chrome started with remote debugging enabled."
echo "You can now run the Python crawler script." 