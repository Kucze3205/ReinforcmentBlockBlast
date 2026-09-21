#!/usr/bin/env bash
# Sonda: instaluje splity Block Blasta, uruchamia grę, zbiera zrzuty i logi do probe-out/.
set -u
OUT=probe-out
PKG=com.block.juggle
mkdir -p "$OUT"

adb install-multiple -r -g assets/*.apk 2>&1 | tee "$OUT/install.txt"
grep -q Success "$OUT/install.txt" || { echo "INSTALL FAILED"; exit 1; }

adb logcat -c
adb shell monkey -p "$PKG" -c android.intent.category.LAUNCHER 1 >/dev/null

for t in 20 45 70; do
  sleep $((t - ${prev:-0})); prev=$t
  adb exec-out screencap -p > "$OUT/shot_${t}s.png"
  echo "t=${t}s pid=$(adb shell pidof $PKG)" | tee -a "$OUT/status.txt"
done

adb shell dumpsys window | grep mCurrentFocus | tee -a "$OUT/status.txt"
adb logcat -d > "$OUT/logcat.txt"
grep -E "FATAL EXCEPTION|No config chosen|Integrity" "$OUT/logcat.txt" | tee "$OUT/errors.txt"

[ -n "$(adb shell pidof $PKG)" ] || { echo "GAME NOT RUNNING"; exit 1; }
[ ! -s "$OUT/errors.txt" ] || { echo "ERRORS IN LOG"; exit 1; }
echo "PROBE OK (sprawdź zrzuty: czy to ekran rozgrywki)"
