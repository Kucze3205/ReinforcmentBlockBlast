#!/usr/bin/env bash
# Most (#18): instaluje grę, akceptuje ToS, oddaje sterowanie bridge.py.
set -u
OUT=bridge-out
source tools/start_apki.sh

python3 bridge.py "${MOVES:-30}"
status=$?
adb logcat -d > "$OUT/logcat.txt"   # gra potrafi zniknąć w trakcie partii — ślad do diagnozy
exit $status
