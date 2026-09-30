# Tempo mostu (#266)

Cel: ≥ 17 postawień/min (w #262 było 12,6). Nowy cel pętli — 10 partii do 1 mln licznika apki, ok. 3950 postawień
(`CONTEXT.md`, „Cel i weryfikacja") — przy 12,6/min to ~315 min, przy 17/min ~232 min.

**Przełącznik:** `BRIDGE_TEMPO=stare` odtwarza dawną ścieżkę 1:1; bez zmiennej działa nowa. Jedna sesja
verifiera może zmierzyć oba warianty na tej samej partii.

Czasy poniżej to **szacunki** z kodu (sleepy są dokładne, koszt jednego `adb` nie był mierzony).
Tempo policzy verifier z pól `t` i `t_ms` pliku ruchów.

## Koszt jednego ruchu — stara ścieżka

| krok | wywołania `adb` | `sleep` |
|---|---|---|
| `in_game` (`dumpsys window`) | 1 | — |
| `drag`: DOWN + 10 × MOVE | 11 (osobne `adb shell input motionevent`) | — |
| `drag`: oczekiwanie na klocek + zrzut celowania | 1 (screencap) | 0,5 s |
| `drag`: UP | 1 | — |
| `stable_state`: min. 2 × `settled_state` (3 klatki po 0,25 s) | 6 (screencap) | 6 × 0,25 = 1,5 s |
| zapis PNG: `_state`, `_read` (annotate), `_aim` | 0 | — |
| decyzja polityki (`decision_ms`) | 0 | — |
| **razem** | **20** | **2,0 s** |

Każde `adb shell input motionevent` uruchamia osobny proces na urządzeniu, `screencap -p` koduje PNG po stronie
urządzenia. Szacunek: 12 motioneventów ≈ 1,5–3 s, 7 zrzutów ≈ 2–3 s, `dumpsys` ≈ 0,3 s. Budżet przy 12,6/min to
4,75 s na ruch. Gdy animacja wydłuża `stable_state`, dochodzą kolejne 3 klatki.

## Nowa ścieżka

| krok | wywołania `adb` | `sleep` |
|---|---|---|
| `in_game` — tylko gdy: poprzedni ruch niezgodny, brak ruchów, albo co `IN_GAME_EVERY` = 10 ruchów | 0 (zwykle) | — |
| `drag`: DOWN + 10 × MOVE w jednym `adb shell "...; ..."` | 1 | — |
| `drag`: oczekiwanie + zrzut celowania | 1 | 0,5 s (bez zmiany) |
| `drag`: UP | 1 | — |
| `stable_state`: 1 klatka na odczyt, stop gdy dwie kolejne klatki dają ten sam stan | min. 2 | 0,2 s między klatkami |
| zapis PNG: `_state`, `_aim` (`_read` tylko w `BRIDGE_TEMPO=stare`; `final.png` zawsze) | 0 | — |
| **razem** | **5** (6 z `in_game`) | **0,7 s** (min.) |

Test `tests/test_bridge_tempo.py` (atrapa `adb`): ruch z `in_game` — **stara 20 → nowa 6** wywołań `adb`.

## Zmiany i uzasadnienie

1. **Jedno `adb shell` na DOWN + 10 MOVE** (−10 wywołań). Największa pozycja: 11 osobnych procesów hosta i urządzenia.
   Współrzędne i kolejność zdarzeń identyczne (test porównuje ostatni MOVE i punkt `finger`), więc cel na planszy ten sam.
   Ryzyko: zdarzenia idą bez przerw między wywołaniami — jeśli gra gubi przyspieszony gest, verifier zobaczy
   rozbieżności w `ok`; wtedy `BRIDGE_TEMPO=stare`.
2. **`stable_state` z jedną klatką na odczyt** (−4 zrzuty min., −1,1 s snu). Stara wersja czytała 3 klatki dwa razy,
   żeby zgodzić się z samą sobą. Nowa: dwie kolejne klatki o tym samym stanie (pola z sumy obu, tacka z ostatniej).
   `settled_state` (start, 3 klatki dla animacji tutorialu) bez zmian.
3. **`in_game` rzadziej** (−1 wywołanie na ruch). Sprawdzane zawsze, gdy coś budzi wątpliwość (poprzedni ruch
   niezgodny z oczekiwaniem, brak legalnych ruchów, pusta plansza), inaczej co 10 ruchów.
4. **Bez `_read.png` na ruch** (oszczędność kodowania PNG w procesie). Wykrywania okien i odczytu planszy nie ruszano.
5. **Bez zmiany:** 0,5 s oczekiwania w `drag` i zrzut celowania (kształt gestu niezmierzony na emulatorze),
   progi okien, `FRAMES`, `DRAG_GAIN`, `LIFT`.

## Znaczniki czasu

Każdy wiersz pliku ruchów ma `t` (`time.time()`, s). Wiersze z ruchem mają też `t_ms`:
`odczyt` (od początku iteracji do decyzji, w tym `read_score`, okna, `in_game`), `decyzja`,
`przeciagniecie` (`drag` + zapis `_aim.png`), `stabilny_stan` (`stable_state` po ruchu). Wartości w ms.

## Dalsze opcje (niezrobione — wymagają pomiaru)

Skrócenie 0,5 s oczekiwania albo zastąpienie gestu jednym `input draganddrop`/`swipe` wymaga emulatora.
