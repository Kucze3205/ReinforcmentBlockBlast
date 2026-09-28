# Punktacja apki kontra nasz wzór, na całych partiach z mostu

Bilet: [#183](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/183), powód: [#173](../../issues/173)
(partia z wynikiem końcowym **29 907** w ok. 175 ruchach, ~170 pkt/postawienie w apce
kontra ~52,6 pkt/postawienie w symulatorze tej samej polityki). **Zaraportowano, nie
naprawiono** — `scoring.py` i `game.py` nietknięte (patrz `git diff --stat` tej gałęzi).

## Metoda

Narzędzie: `tools/score_from_trajectory.py` (nowe w tym zadaniu). Dla jednej partii
bierze listę plików `chunkN_*.jsonl`/`moves_chunkN*.jsonl` z `bridge/runs/<id>/`,
odtwarza każdy ruch z jego **własnego** zaobserwowanego `board`/`tray` (most zapisuje
pełny stan przy każdym ruchu, nie różnicę) i liczy przyrost punktów dwoma wzorami:

- **main** — dokładnie `game.py::apply_placement` (kopia logiki, nie import, żeby nie
  dawać temu narzędziu praw zapisu do `game.py`; zgodność sprawdzona w
  `tests/test_score_from_trajectory.py`),
- **alt** — drabinka `U(combo)` 10/15/20 z `docs/rozjazd-punktacja-generator.md` §1
  (combo rośnie o liczbę wyczyszczonych linii, nie o 1), **nigdy niewdrożona**, liczona
  tu wyłącznie jako druga kolumna do porównania.

Skrypt **nie zgaduje granic partii sam** — miesza je z fałszywymi zatrzymaniami mostu
(`petla_bez_postepu`, `okno: ustawienia_wstecz` po padzie apki, warianty ekranu końca
gry, których most nie rozpoznaje — patrz `## Odkrycia`). Który zestaw kawałków należy do
jednej partii i jaki był jej prawdziwy wynik końcowy jest odczytane ręcznie z narracji
`bridge/runs/<id>/pomiar.json` i podane przez `--first-chunk`/`--last-chunk`/`--apka-final`.

Jedno polecenie na partię, np.:

```
python3 tools/score_from_trajectory.py bridge/runs/c1819ed \
    --last-chunk 9 --apka-final 29907 --apka-final-source chunk9_gameover.png
```

### Partie policzone

Kryterium doboru: partia ma wynik końcowy **odczytany z ekranu końca gry**, nie tylko
z licznika w trakcie (`## Cel` biletu). W `bridge/runs/*` takie partie są dokładnie
trzy — dwie z `c1819ed` (#173) i jedna z `1402cff` (#164, wynik 8532 wspomniany w
kontekście biletu). Pozostałe przebiegi z `moves.jsonl`/`analiza.py`
(`0d96333`, `1bd38fa`, `b4a7d26`) kończą się `"koniec": "brak legalnego ruchu wg
odczytu"`, `"gra nie jest na pierwszym planie"` albo `"limit_ruchow"` — most stracił
partię z oczu albo skończył sufitem, żaden nie ma wyniku z ekranu końca gry, więc nie
spełniają kryterium (i tak liczą naszym wzorem swój fragment — patrz ich własne
`analiza.json` — ale bez punktu odniesienia z apki nie wnoszą nic do tego porównania).

| partia | kawałki | postawień | luki | wynik apki | źródło wyniku apki | wynik **main** | wynik **alt** |
|---|---|---:|---|---:|---|---:|---:|
| A — `c1819ed`, partia 1 | 2–9 (kawałek 1 brakuje — nadpisany przed zapisem, patrz `pomiar.json`) | 155 z ~175 | kawałek 1 (20 ruchów) całkowicie brakuje: stan combo na starcie kawałka 2 nieznany, przyjęto 0; 1× `ok=false` (kawałek 9, ruch 14, tuż przed reklamą) | **29 907** | `chunk9_gameover.png` ("Can you Top that?") | 6 302 | 13 317 |
| B — `c1819ed`, partia 2 | 10–15 (komplet, bez brakujących kawałków) | 104 | 1× `ok=false` (kawałek 15, ruch 3); wynik końcowy **nieodczytany przez most** (zakończył kawałek fałszywym `brak legalnego ruchu wg odczytu`) — odczytany ręcznie przez weryfikatora z `chunk15_after_back.png` po `KEYCODE_BACK` na nierozpoznanej reklamie statycznej | **20 345** | `chunk15_after_back.png` ("Your Best is Next", wariant niebieski) | 6 040 | 13 355 |
| C — `1402cff`, partia | 1–7 (komplet) | 111 | pad apki w kawałku 2 (`ok=false` na ruchu 0, potem 6× fałszywe `ustawienia_wstecz`→`petla_bez_postepu`); wynik ciągły przed/po (264→321), więc **ta sama partia**, nie restart; 1× `ok=false` (kawałek 7, ruch 9, tuż przed reklamą) | **8 532** | `chunk7_010_gameover_screen.png` ("Can you Top that?"), wynik potwierdzony w narracji `bridge/runs/1402cff/pomiar.json` | 4 282 | 8 032 |

Uwaga do partii A: wynik apki (29 907) liczy się od ruchu 0 partii, ale replay zaczyna
się od ruchu 20 (kawałek 1 brakuje). Punkty **zarobione w widocznym oknie** to
`29 907 − 405 = 29 502` (405 to wynik apki już przy pierwszym widocznym ruchu) — to jest
liczba użyta niżej do pkt/postawienie i porównania z `main`/`alt`, żeby porównywać ten
sam zestaw 155 ruchów po obu stronach.

### pkt/postawienie i udział czyszczeń

Udział czyszczeń apki jest **szacowany**, nie zmierzony wprost: `placement_points`
(punkty za samo postawienie) są identyczne w obu wzorach (nie zmienia ich ani `main`,
ani `alt`), więc `wynik_apki − placement_total` daje przybliżony udział czyszczeń apki
przy założeniu, że apka też nalicza punkty za postawienie jako liczbę komórek (Z-7,
`docs/calibration-assumptions.md`) — założenie niepotwierdzone dla apki wprost w tym
bilecie, tylko przeniesione z kalibracji R10.

| partia | pkt/postawienie **main** | pkt/postawienie **alt** | pkt/postawienie **apka** | udział czyszczeń main | udział czyszczeń alt | udział czyszczeń apka (szac.) |
|---|---:|---:|---:|---:|---:|---:|
| A | 40,66 | 85,92 | **190,34** | 88,9% | 94,7% | 97,6% |
| B | 58,08 | 128,41 | **195,62** | 91,6% | 96,2% | 97,5% |
| C | 38,58 | 72,36 | **76,86** | 89,4% | 94,4% | 94,7% |

Dla porównania, symulator (`docs/ile-do-10-mln.md`, 300 partii `lookahead:weights.json`,
`main`): 55,85 pkt/postawienie łącznie w serii, 93,03% wyniku z czyszczeń. Rząd wielkości
udziału czyszczeń (~90–98%) jest **spójny** między apką (trzy partie z mostu) i
symulatorem (300 partii) niezależnie od tego, który wzór policzy licznik — różnica jest
w tym, ile te czyszczenia płacą, nie w tym, skąd się bierze wynik.

### Stosunek apka / nasz wzór

| partia | apka / main | apka / alt |
|---|---:|---:|
| A | 4,68× | 2,22× |
| B | 3,37× | 1,52× |
| C | **1,99×** | **1,06×** |

`alt` (drabinka `U(combo)`) jest w każdej z trzech partii bliżej apki niż `main`, i w
partii C — jedynej **kompletnej** partii bez brakujących kawałków w tym zestawie —
niemal się z nią pokrywa (1,06×). Partie A i B rozjeżdżają się bardziej, ale obie mają
znaną przyczynę zajeżdżającą w tę samą stronę: A brakuje 20 ruchów na starcie (stan
combo nieznany, przyjęty 0 — to zaniża `main`/`alt` względem tego, co realnie
się działo), a B ma wyższe maksymalne combo (`main`: 15, `alt`: 23 — patrz łańcuchy
niżej) niż C, więc drabinka `alt` (próg 20 dopiero od combo 11) ma tu mniej miejsca,
żeby dogonić apkę na najwyższych combo, jeśli apka rośnie stromiej jeszcze wyżej niż
zakłada trzystopniowa drabinka z `eae980f`.

### Łańcuchy combo (main / alt)

| partia | combo max (main) | combo max (alt) | mediana długości łańcucha (main, z tych partii) |
|---|---:|---:|---:|
| A | 15 | 17 | 1 (43 łańcuchy, rozkład: 4×3, 9×2, 30×1) |
| B | 15 | 23 | 1 (27 łańcuchów: 1×5, 1×4, 2×3, 8×2, 15×1) |
| C | 14 | 17 | 1 (29 łańcuchów: 4×4, 2×3, 23×1) |

Mediana 1 (dominują izolowane pojedyncze czyszczenia) jest **niższa** niż mediana 9 z
`docs/ile-do-10-mln.md` (symulator, 300 partii `lookahead`, `main`). To spójne z
oczekiwaniem: te trzy partie z mostu grały polityki `lookahead-ntuple`/`lookahead` na
**żywej** apce z realnym ryzykiem błędu odczytu i mniejszą próbką (370 ruchów łącznie
kontra dziesiątki tysięcy w symulatorze), więc rozkład jest szumniejszy — nie jest to
sprzeczność z symulatorem, tylko inna wielkość próby. `combo max` 14–23 w tych trzech
partiach jest w tym samym rzędzie wielkości co maksimum 96 z 300 partii symulatora.

## Porównanie ruch po ruchu

**Żadna z trzech partii nie ma spójnego (niemalejącego przez całą partię) licznika OCR**
(`ocr_spojny_w_partii=false` we wszystkich trzech — sprawdzone programowo przez
`tools/score_from_trajectory.py`), więc kryterium z `## Cel` biletu ("tam, gdzie OCR
jest spójny — ruch po ruchu") **nie jest spełnione w żadnej z trzech partii jako
całości**. Powód jest udokumentowany już w `pomiar.json` tych przebiegów: "OCR wyniku
mocno niestabilny", "kilka odczytów OCR wyniku zaniżonych/błędnych po drodze" — bridge
sam mówi, że `ok` (zgodność planszy) jest wiarygodne, ale `score` z OCR bywa szumem.

Przykład z kawałka 9 partii A (ruchy 0–14, ciąg OCR lokalnie rosnący — wygląda "czysto"):

| ruch | apka (delta) | main (gained) | alt (gained) | linie | combo (main/alt) |
|---:|---:|---:|---:|---:|---:|
| 0–2, 5, 7 | 4 | 4 | 4 | 0 | — |
| 3 | 34 | 34 | 34 | 1 | 3/3 |
| 4 | 44 | 44 | 44 | 1 | 4/4 |
| 6 | 54 | 54 | 54 | 1 | 5/5 |
| 8 | **69** | 64 | 94 | 1 | 6/6 |
| 9 | **201** | 144 | 244 | 2 | 7/8 |
| 10 | **72** | 4 | 4 | 0 | 7/8 |
| 11–13 | 4 | 4 | 4 | 0 | — |

Ruchy bez czyszczenia i pierwsze trzy czyszczenia (combo ≤5, próg `alt` jeszcze nie
przekroczony) zgadzają się **co do punktu** z oboma wzorami — to samo zjawisko co w
pomiarze R10 (`docs/calibration-assumptions.md`), tylko na żywej partii zamiast
laboratoryjnej sesji. Ale ruch 10 psuje obraz: apka pokazuje +72 przy **zerze**
wyczyszczonych linii wg odczytu planszy (`ok=true` na tym ruchu) — taki przyrost nie
istnieje w żadnym z dwóch wzorów bez czyszczenia, więc to **musi być błąd OCR**, nie
inna reguła. To znaczy, że nawet lokalnie rosnący fragment licznika miesza prawdziwe
przyrosty z szumem, i ruchy 8–9 (gdzie `main`/`alt` różnią się między sobą i oba różnią
się od apki) nie dają się jednoznacznie rozstrzygnąć na ich podstawie — delty 69 i 201
nie pasują czysto do żadnego wzoru, ale też nie są "okrągłe" w sposób, który by
wykluczał błąd pojedynczej cyfry OCR na tysiącach punktów w tym zakresie wielkości
liczb (wynik już >29 000 w tym momencie partii).

**Wniosek dla tej sekcji: dane nie rozstrzygają na poziomie pojedynczego ruchu.**
OCR wyniku apki jest zbyt zaszumiony w tych trzech partiach, żeby wiarygodnie
zweryfikować regułę ruch po ruchu — potrzebna byłaby albo partia z czystszym OCR, albo
narzędzie mostu czytające wynik dokładniej (poza budżetem tego biletu).

## Jawne zdanie

**Wzór `alt` (drabinka `U(combo)` z `docs/rozjazd-punktacja-generator.md`) tłumaczy te
trzy partie z mostu wyraźnie lepiej niż zamrożony `main`** — stosunek apka/wzór spada z
3,4–4,7× (`main`) do 1,1–2,2× (`alt`) na łącznie 370 ruchach z trzech partii, w tym 111
ruchów jednej **kompletnej** partii (C, `1402cff`) gdzie `alt` trafia w wynik apki z
dokładnością 6% (8 032 wobec 8 532). To stoi **wyłącznie na agregacie końcowym trzech
partii** (155+104+111 ruchów), nie na dopasowaniu ruch po ruchu — ten poziom
szczegółowości nie rozstrzyga (patrz sekcja wyżej), a dwie z trzech partii (A, B) mają
udokumentowane luki (brakujący kawałek, nierozpoznany koniec gry), które ciągną wynik w
tę samą stronę, więc nie są niezależnym potwierdzeniem trzeciej. Innymi słowy: **kierunek
jest spójny w trzech niezależnych partiach i dwóch przebiegach mostu, ale próbka (trzy
partie, jedna z nich kompletna) jest za mała, żeby to uznać za rozstrzygnięcie** — to
materiał do #20, decyzję o ewentualnym wdrożeniu `alt` (albo zebraniu kolejnych
kompletnych partii z apki) podejmie orchestrator.

## Odkrycia

- Most miesza fałszywe zatrzymania (`petla_bez_postepu` po padzie apki, `okno` po
  nierozpoznanym typie reklamy) z prawdziwym końcem partii — bez ręcznej lektury
  `pomiar.json` nie da się automatycznie posklejać kawałków w partie (już opisane w
  #164/#173/#169, potwierdzone tutaj przy budowie tego narzędzia).
- Licznik `score` z OCR miewa przyrosty niezgodne z żadną regułą przy `ok=true` na
  planszy (ruch 10, kawałek 9, partia A: +72 przy zero liniach) — to nowy, konkretny
  przykład zjawiska, które `pomiar.json` już nazywało "OCR niestabilny", przydatny jako
  test case, gdyby ktoś chciał policzyć most z dokładniejszym odczytem wyniku.

## Pomiar 2 (#191): partia D z sesji danych tego cyklu

Bilet: [#191](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/191) · dane:
`bridge/runs/cb91077/pomiar.json` (#190, sesja danych na moście, polityka greedy, 12 kawałków, 3 pełne
partie plus czwarta w toku). **Zaraportowano, nie naprawiono** — `scoring.py`, `game.py`, `generator.py`
nietknięte, `reward_shape_changed: no`.

### Dobór partii: tylko cała partia bez dziur

Kryterium tego zadania jest ostrzejsze niż w #183 ("wynik z ekranu końca" tam wystarczał nawet z brakującym
kawałkiem) — tu liczy się **cała partia bez dziur** w surowej trajektorii. Z trzech partii w `cb91077`:

- **partia 1** (kawałki 1–3): `chunk3_moves.jsonl` utracony (nadpisany przed skopiowaniem, udokumentowane
  wprost w `pomiar.json`, pole `kawalki[2]`) — brak surowego `board`/`tray`/`move` dla ruchów 0–10, tylko
  log konsoli. **Wykluczona.**
- **partia 2** (kawałki 3–7): `pomiar.json` (pole `partie[1]`) twierdzi "bez dziur", ale to sprzeczne z
  własnym opisem kawałka 3 wyżej w tym samym pliku — `chunk3_moves.jsonl` naprawdę nie istnieje na dysku
  (sprawdzone `ls bridge/runs/cb91077/*.jsonl`), więc brakuje ruchów 12–29 kawałka 3 (start partii 2, ok.
  18 ruchów). **Wykluczona** mimo etykiety w źródle — patrz `## Odkrycia` w `docs/z6-tacka-a-plansza.md`
  (Pomiar 3, #191).
- **partia 3** (kawałki 7–12): wszystkie kawałki mają zachowany surowy `chunkN_moves.jsonl`, bez restartu
  apki. Jedyna komplikacja to wewnątrz-kawałkowa granica: kawałek 7 zawiera koniec partii 2 (ruchy 0–10) i
  początek partii 3 (ruchy 11–29), kawałek 12 zawiera koniec partii 3 (ruch 0) i początek partii 4
  (ruchy 1–29) — `tools/score_from_trajectory.py` tnie tylko po całych plikach, nie po numerze ruchu
  wewnątrz pliku, więc granice partii 3 wycięto ręcznie ze strumienia wpisów (drugie wystąpienie `n=11` w
  `chunk7_moves.jsonl` to pierwszy prawdziwy ruch partii 3 — pierwsze to wpis przejściowy bez `move`; ruch
  `n=0` w `chunk12_moves.jsonl` to ostatni ruch partii 3, kolejne wpisy już partia 4). **Włączona jako
  partia D.**

### Partia D

| partia | kawałki | postawień | luki | wynik apki | źródło wyniku apki | wynik **main** | wynik **alt** |
|---|---|---:|---|---:|---|---:|---:|
| D — `cb91077`, partia 3 | 7 (od ruchu 11) – 12 (do ruchu 0) | 140 (komplet, bez dziur) | 1× `ok=false` (kawałek 7, ruch 10 — sam koniec partii poprzedniej, poza oknem partii D); 1× `ok=false` (kawałek 12, ruch 0 — koniec partii D, oczekiwane) | **12 990** | `chunk12_gameover3_screen.png` ("Fun doesn't Stop Here!") | 7 604 | 16 089 |

### Tabela zbiorcza (A–D)

| partia | kawałki | postawień | apka | main | alt | apka/main | apka/alt |
|---|---|---:|---:|---:|---:|---:|---:|
| A — `c1819ed` p.1 | 2–9 | 155 z ~175 | 29 907 (29 502 w widocznym oknie) | 6 302 | 13 317 | 4,68× | 2,22× |
| B — `c1819ed` p.2 | 10–15 | 104 | 20 345 | 6 040 | 13 355 | 3,37× | 1,52× |
| C — `1402cff` | 1–7 | 111 | 8 532 | 4 282 | 8 032 | 1,99× | 1,06× |
| D — `cb91077` p.3 | 7–12 | 140 | 12 990 | 7 604 | 16 089 | **1,71×** | **0,81×** |

Partia D jest pierwszą w tym zestawie, gdzie `alt` **przekracza** apkę (0,81× — apka niższa niż `alt`), nie
tylko zbliża się do niej z dołu jak w A/B/C. Combo max partii D jest też najwyższe z czterech (`main`: 22,
`alt`: 24, przeciw 14–15/17–23 w A–C) — spójne z wcześniejszą obserwacją z #183, że drabinka trójstopniowa
`alt` (10/15/20) rośnie zbyt stromo przy wysokich combo względem tego, co realnie robi apka, jeśli ekstrapolować
poza zakres, w którym ją dopasowano.

| partia | pkt/postawienie **main** | pkt/postawienie **alt** | pkt/postawienie **apka** | udział czyszczeń main | udział czyszczeń alt | udział czyszczeń apka (szac.) |
|---|---:|---:|---:|---:|---:|---:|
| D | 54,31 | 114,92 | **92,79** | 91,66% | 96,06% | 95,12% |

Udział czyszczeń (main/alt/apka szac.) jest w tym samym rzędzie wielkości 91–96% co w A–C i w symulatorze
(93,03%) — spójne z resztą zestawu niezależnie od tego, który wzór (main/alt) się użyje.

### Jawne zdanie

**Żaden z dwóch wzorów nie trzyma się wyniku apki w granicach ±10% na wszystkich czterech partiach.**
`main` jest systematycznie ZA NISKI (1,71×–4,68× poniżej apki na wszystkich czterech). `alt` jest bliżej na
trzech pierwszych (1,06×–2,22×, wciąż poza ±10%), ale na partii D **przeskakuje na drugą stronę** i
przekracza apkę (0,81×, też poza ±10%, w przeciwnym kierunku) — więc `alt` nie jest nawet spójnie
jednostronny, dodatkowy dowód, że trójstopniowa drabinka 10/15/20 nie jest właściwym wzorem apki, tylko
przybliżeniem lepszym niż `main` w wąskim zakresie combo, w jakim była kalibrowana.
