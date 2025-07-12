#!/bin/bash

CHROME_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PROFILE_DIR="Default"  # Change to your profile name if different

"$CHROME_PATH" \
  --remote-debugging-port=9222 \
  --user-data-dir=~/Library/Application\ Support/Google/Chrome \
  --profile-directory="$PROFILE_DIR"