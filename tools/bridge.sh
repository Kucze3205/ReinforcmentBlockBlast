#!/usr/bin/env bash
# Most (#18): instaluje grę, przechodzi ToS i tutorial, oddaje sterowanie bridge.py.
set -u
OUT=bridge-out
PKG=com.block.juggle
mkdir -p "$OUT"

# Po pierwszym starcie obraz Play aktualizuje pakiety i zabija procesy — czekamy, aż ucichnie (#14).
sleep 90
adb shell settings put global verifier_verify_adb_installs 0
adb shell settings put global package_verifier_enable 0

adb install-multiple -r -g assets/*.apk 2>&1 | tee "$OUT/install.txt"
grep -q Success "$OUT/install.txt" || { echo "INSTALL FAILED"; exit 1; }

adb shell monkey -p "$PKG" -c android.intent.category.LAUNCHER 1 >/dev/null
sleep 25
adb shell input tap 160 437   # Accept Terms of Use
sleep 15
adb exec-out screencap -p > "$OUT/boot_1_tutorial.png"
adb shell input tap 265 603   # Skip tutorialu
sleep 5
adb exec-out screencap -p > "$OUT/boot_2_after_skip.png"

python3 bridge.py "${MOVES:-30}"
