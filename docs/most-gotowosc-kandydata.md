# Gotowość mostu na kandydata `gain_weight` (#260)

Kandydat: `lookahead-ntuple:ntuple/survival-adce-400k.json@beam=128,samples=0,complete=1,gain_weight=100000` (#248).
Narzędzie: `tools/most_gotowosc_kandydata.py --policy <spec>`; dane: `docs/data/260-most-gotowosc.json`.
Pomiar offline na stanach z `bridge/runs/*/chunk*_moves.jsonl`. **Zaraportowano, nie naprawiono** — `bridge.py`,
`policies.py`, `benchmark.py`, `game.py`, `scoring.py`, `generator.py`, `pieces.py`, `ntuple*` nietknięte.

## 1. Ścieżka decyzji: działa

Odtworzona ścieżka `bridge.main`: `build_policy(spec, {"torch_seed": 0})` → `reset(run_id)` →
`Piece(macierz z logu, "slot<i>", -1)` → `legal_moves` → `make_game_stub(board, pieces)` → `policy.act`.
Rdzeń natywny jest aktywny (`ntuple.native` ≠ `None`).

- **2831 unikalnych stanów** (929 z 1 kawałkiem na tacce, 950 z 2, 952 z 3), z 12 przebiegów. Pominięte: 23 wiersze
  końca partii (śmieci z nakładki, #249), 37 wierszy bez ruchu (okna/restarty), 70 powtórzeń (ponowienia po `ok=false`).
- **Wyjątki: 0. Nielegalne akcje: 0.** Próbka 1 na 25 stanów liczona dwa razy: decyzje identyczne (determinizm przy `samples=0`).
- **Czas decyzji kandydata** (ms, ten runner, jedna decyzja): mediana **1,92**, p95 **16,3**, max **67,6**.
  Wg tacki: 1 kawałek — mediana 0,28 / max 0,6; 2 kawałki — 2,11 / 67,6; 3 kawałki — 7,5 / 39,6 (p95 25,8).
- **`decision_ms` w logach** (to, co mierzył most, głównie inne polityki): ogółem mediana 0,42, p95 19,0, max 103,9;
  `greedy` (2480 stanów) mediana 0,37 / p95 1,21 / max 4,63; `lookahead-ntuple` (351 stanów, wcześniejsze specyfikacje)
  mediana 16,5 / p95 51,3 / max 103,9. Kandydat jest więc szybszy niż dotychczasowe `lookahead-ntuple` z logów,
  a względem czasu przeciągnięcia i odczytu (sekundy na ruch) pomijalny. Zastrzeżenie: stany z logów to głównie
  plansze rzadkie z krótkich partii polityk bez gwarancji; gęste plansze z długich partii `complete=1` mogą uruchamiać
  przegląd wyczerpujący (`_tray_complete_search`) i dawać dłuższe czasy — w logach ich nie ma (nie mierzone tutaj).

Rozjazdów nie znaleziono; nic do zmiany.

## 2. Stan combo: zaślepka nie odpowiada grze, ale decyzje prawie się nie zmieniają

**Skąd most bierze `combo`.** Nigdzie. `bridge.main` woła `make_game_stub(board, pieces)` (`bridge.py:740`), a
`make_game_stub` (`bridge.py:583-588`) ma `combo=0` jako domyślny argument i na sztywno
`combo_counter=COMBO_COUNTER_BASE` (=3). Most nie czyta combo z ekranu ani nie śledzi go między ruchami; w dzienniku nie
ma pola `combo`. W każdej decyzji polityka widzi więc „świeże" combo, niezależnie od faktycznej serii.

**Rekonstrukcja.** Reguły `scoring.py`/`Game.apply_placement` zastosowane do zalogowanych ruchów (start przebiegu z pustą
planszą, reset po końcu partii; łańcuch „wiarygodny", dopóki plansza wiersza = `observed` poprzedniego i ruch był `ok`
albo nie zmienił planszy):

- Stan rekonstruowany różni się od zaślepki `(0, 3)` w **2630 z 2831 stanów** (93%); wśród 1669 stanów wiarygodnych — w 1545.
  Rozjazd jest normą: po każdym czyszczeniu combo ≥ 1, licznik zawsze schodzi poniżej 3.
- Log niesie `expected`/`observed` tylko dla **planszy** (`ok` = zgodność siatki), nie dla combo, więc zgodność combo
  nie jest sprawdzalna z tych pól. Jedyny pośredni test: przyrost `score` odczytany z ekranu między kolejnymi wierszami vs
  punkty wg `scoring.py` (1371 porównań, tylko wiarygodne, `ok`): zgodne z rekonstrukcją combo **652**, z zaślepką (combo=0)
  **557**. Wśród 523 ruchów, gdzie oba modele dają różne punkty, ekran zgadza się z rekonstrukcją w 95 (18%). Czyli
  punktacja apki nie jest wzorem z `scoring.py` (zgodnie z `docs/punktacja-apka-vs-wzor.md`), więc **stanu combo apki
  z tych logów nie da się zweryfikować**; rekonstrukcja mówi tylko, co policzyłby symulator.
- **Decyzje zmienione przez stan combo: 4 z 2831** (0,14%; 0,15% stanów z różnicą); w podzbiorze wiarygodnym 2 z 1669.
  Kandydat liczony dwa razy na tym samym stanie: z zaślepką i z `combo`/`combo_counter` z rekonstrukcji. Przykłady
  w JSON (`combo.przyklady`).

**Wniosek.** `gain_weight=100000` waży punkty ~100 razy więcej niż postawienia, a `gain` niesie combo-mnożnik tylko przy
czyszczeniu; gdy kilka ułożeń tacki ma równe czyszczenia, combo skaluje je równo, więc kolejność się nie zmienia.
Na tych stanach `gain_weight` przenosi się na apkę bez odczytu combo z ekranu; w ~0,15% decyzji wybór byłby inny. To
rozjazd między symulatorem a mostem, ale niewielki i nie rozstrzygalny przy pomocy logów (apka liczy punkty inaczej).
Uwaga: klucz scalania stanów przy `gain_weight != 0` zawiera combo i licznik (`docs/punkty-na-postawienie.md`), więc
zaślepka nie psuje kluczy — po prostu wszystkie korzenie startują z `(0, 3)`.

**Gdyby chciano to zamknąć (bez zmieniania teraz):** w `bridge.main` (`bridge.py`, pętla ruchów, przy
`make_game_stub` w l. 740) prowadzić `combo`/`combo_counter` według `Game.apply_placement` po każdym `ok` ruchu, resetować
po końcu partii i po oknach, i podać oba pola do `make_game_stub` (dziś tylko `combo`, `combo_counter` stały; trzeba
dodać argument). Dodatkowo `ok=false` z niezmienioną planszą nie przesuwa stanu. Pomiar zysku: powtórzyć to narzędzie po zmianie.

## 3. Koszt realnej partii 1 mln przy 684,6 pkt/postawienie

Przelicznik apka/wzór jak w `docs/most-tacki-ukladalne.md` (1,43–4,68×, założenie stałości; 684,6 pkt/postawienie to
punkty wg naszego wzoru). Pojemność sesji: 739 udanych postawień w najdłuższym przebiegu (`1b1763a`); tempo 5–10 postawień/min
(szacunek weryfikatora, nie pomiar).

| przelicznik | pkt apki/postawienie | postawień na 1 mln | kawałki po 60 | sesje verifiera (739) | czas przy 5–10/min |
|---|---:|---:|---:|---:|---|
| 1,00× (sam wzór) | 684,6 | 1 461 | 25 | 1,98 | 2,4–4,9 h |
| 1,43× | 979,0 | 1 021 | 18 | 1,38 | 1,7–3,4 h |
| 4,68× | 3 203,9 | 312 | 6 | 0,42 | 0,5–1,0 h |

Przy 141 pkt/postawienie było 7092 / 4960 / 1515 postawień, czyli kandydat obniża koszt ≈ 4,9×. Realna partia to 6–25
kawałków, 0,4–2 sesji; mniejsza niż dotychczas zagrożenie ze strony reklam/okien/zawieszek, choć ciągła gra bez przerwy
przez ≥ 1000–1500 postawień nadal nie była na moście grana.

## Odkrycia

- Wyniki apki nie zgadzają się ze wzorem `scoring.py` w ~52% ruchów z wiarygodnym stanem (652/1371 zgodnych nawet po
  rekonstrukcji combo), więc kalibracja punktacji (nie tylko combo) rozstrzyga o tym, czy `gain_weight` optymalizuje
  to, co liczy apka.
