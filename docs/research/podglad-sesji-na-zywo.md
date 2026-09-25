# Podgląd pracy sesji na żywo (`stream-json`)

Bilet: #69 (źródło: #68). Data: 2026-09-25. Wersja CLI: 2.1.278 (ta sama co w `session.yml`).
Znaczniki: **[T]** — sprawdzone lokalnie uruchomieniem, **[K]** — wynika z kodu repo, **[Z]** — nieprzetestowane.

## Werdykt: ROBIĆ

Tanie i małe: ~6 linii w `agent.sh`, jeden nowy plik filtra (~25 linii), zero zmian w `session.yml`.
Koszt czasu i tokenów: zerowy (ta sama sesja, inny format wyjścia). Jedyne rzeczy do pilnowania to trzy pułapki niżej.

## Fakty

- `claude -p ... --output-format stream-json --verbose` działa w 2.1.278; **`--verbose` jest wymagane** **[T]**.
- Wyjście to NDJSON, jedno zdarzenie na linię. Typy z próbnej sesji (1 odczyt pliku, 10 zdarzeń, 15,9 KB): `system/init` (6,4 KB), `rate_limit_event`, `assistant` (bloki `thinking` / `tool_use` z `name` i `input` / `text`), `user` (`tool_result`), `system/thinking_tokens`, `result` (koszt, tokeny, `is_error`) **[T]**.
- Rozmiar surowy: ~1–2 KB na zdarzenie, `tool_result` niesie całą treść odczytu — sesja na 150 tur to rząd kilku MB **[Z]**. Log po filtrze (jedna linia na `tool_use`/`text`, ~100–200 B): dziesiątki KB **[Z]**. Bez `--include-partial-messages` (zalałoby log).
- Log kroku w Actions pokazuje linie na bieżąco (musi być flush po każdej linii). Job summary (`$GITHUB_STEP_SUMMARY`) renderuje się dopiero po zakończeniu kroku — **nie nadaje się na „na żywo"**, pominąć **[Z]**.

## Pułapki (wszystkie obchodzone małym kosztem)

1. **`machine_cause` w `loop.py` psuje się na NDJSON.** `json.loads` całego pliku rzuca `ValueError` → `d={}` → gubi `api_error_status` i `terminal_reason` **[K]** (`.github/loop/loop.py:358`).
   Gorzej: regex `rate_limit` na surowym pliku trafia w `rate_limit_event`, który jest w **każdej** sesji, także udanej **[T]** → `limited=True` zawsze → crash raportowany jako `paused` „Limit subskrypcji" **[K]**.
   **Rozwiązanie bez ruszania `loop.py`:** filtr zapisuje do `$OUT/claude-execution-output.json` wyłącznie ostatnie zdarzenie `result` (obiekt, jak dziś przy `--output-format json`). Surowy strumień idzie do innego pliku (`stream.ndjson`).
2. **Pad filtra zabija agenta** (SIGPIPE na zapisie `claude` do rury). Rozwiązanie: filtr łapie wyjątki per linia, a w potoku `python3 filter.py || cat >/dev/null`.
3. **Kod wyjścia.** `echo $? > agent-exit` po potoku da kod ostatniego polecenia, nie `claude`/`timeout`. Rozwiązanie: `${PIPESTATUS[0]}` (bez `pipefail`, bo `set -u` już jest, a `exit 0` na końcu zostaje).

## Czego filtr nie może wypisywać (log jest publiczny)

Nie drukować treści `tool_result` (w roli `emulator` mogą tam być dane z prywatnego release'u) ani `thinking`. Drukować: nazwę narzędzia + skrócony `input` (~150 znaków, `Bash` → komenda), tekst modelu, końcowy wiersz `result` (tury, koszt). Sekrety rejestrowane w Actions są maskowane automatycznie; to tylko drugie zabezpieczenie.

## Checkpointy i `finalize`

Nietknięte: pętla `sleep 120` → `publish` + `git push` jest procesem niezależnym od potoku, `kill $SYNC` zostaje. `finalize` czyta `agent-exit` i `claude-execution-output.json` — oba pliki zachowują dotychczasowy format (pułapki 1 i 3).

## Trudność zmiany

`.github/` jest chronione przed agentem — zmianę robi właściciel (albo osobny mechanizm). Zakres:
- `.github/loop/stream_filter.py` (nowy): czyta stdin, wypisuje podgląd z flush, zapisuje `stream.ndjson` i `claude-execution-output.json`.
- `.github/loop/agent.sh`: `--output-format stream-json --verbose`, `| python3 "$GITHUB_WORKSPACE/loop/.github/loop/stream_filter.py" || cat >/dev/null`, `PIPESTATUS[0]`.
- `session.yml`, `loop.py`: bez zmian.

## Do sprawdzenia przy pierwszym prawdziwym przebiegu **[Z]**

Że linie faktycznie pojawiają się w UI Actions w trakcie kroku (brak buforowania pod `bash` bez TTY), oraz rzeczywisty rozmiar `stream.ndjson` po długiej sesji.
