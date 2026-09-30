#!/usr/bin/env bash
# Jedna partia serii weryfikacyjnej (#287): start apki, partia_serii.py, logcat. Wołany przez seria.yml.
# Kody 0/1/2 partii (cel/przegrana/przerwanie) to wyniki, nie awarie: krok kończy się zerem; wynik niesie pomiar.json.
set -u
OUT="$KATALOG"
source tools/start_apki.sh

python3 tools/partia_serii.py "$POLITYKA" "$KATALOG" --limit-minut "$LIMIT_MINUT"
status=$?
echo "$status" > "$KATALOG/kod_wyjscia.txt"
adb logcat -d > "$KATALOG/logcat.txt"
[ "$status" -le 2 ]
