# Z-6: czy tacka trzech klocków zależy od stanu planszy

Bilet: #78 (pomiar 1) i #182 (pomiar 2) · założenie w
`docs/calibration-assumptions.md` (Z-6) · skrypty: `tools/analiza_z6.py`
(pomiar 1), `tools/z6_pary.py` + `tools/z6_testy.py` + `tools/z6_pomiar2.py`
(pomiar 2, patrz sekcja „Pomiar 2” niżej — więcej danych, mocniejsze testy).

## Pomiar 1 (#78) — werdykt

Bilet: #78 · dane: `bridge/runs/d550db3/pomiar.json` (33 pary „plansza → tacka”,
zebrane przez most z prawdziwego Block Blasta, #60) · skrypt: `tools/analiza_z6.py`

**Za mało danych.** 33 pary nie rozstrzygają Z-6 na progu istotności, który
przeżywa korektę za wielokrotne testowanie. Jest jeden sugestywny, ale
niepotwierdzony sygnał (patrz Test 2) i jeden test, który w tej próbie jest
strukturalnie ślepy niezależnie od liczby par (Test 1). **Potrzeba około
190–230 rund mostu** (patrz „Ile danych trzeba”), nie tylko „więcej par przy
tym samym stylu gry”.

## Dane

`pomiar.json`: 100 rund, 33 pary rozpoznane w 100%, plansza 8×8 w chwili
nowej tacki + trzy nazwy klocków (nazwy z `pieces.py`, więc typ kanoniczny
i orientacja są znane wprost).

Plansze w tej próbie są w większości puste: zapełnienie od 0% do 58%,
mediana 23%. To jest artefakt stylu gry (bota/gracza), z którego most
zbierał dane — most nie kontrolował zapełnienia.

## Metoda

`tools/analiza_z6.py` liczy dla każdej z 33 rund:

- **zapełnienie planszy** (`n_filled / 64`),
- **liczbę kanonicznych typów z `pieces.py`, które wciąż mieszczą się gdzieś
  na tej planszy** (`n_playable_types`, 0–15) — sprawdzone przez `Board.can_place_piece`
  dla każdej orientacji każdego typu, na każdej pozycji,
- **średni rozmiar (liczba komórek) trzech klocków w tacce**.

Hipoteza zerowa (H0) to dosłownie `generator.py`: typ losowany 1/15,
niezależnie od planszy, potem orientacja 1/n w obrębie typu.

### Test 1 — czy tacka faworyzuje grywalne typy

Dla każdego z 99 wylosowanych klocków (33×3) sprawdzono, czy jego typ
mieści się gdzieś na planszy tej rundy. Pod H0 prawdopodobieństwo trafienia
w grywalny typ w rundzie *i* wynosi `n_playable_types_i / 15` — bo losowanie
nie widzi planszy. Suma tych 99 niezależnych, nieidentycznych prób
Bernoulliego to rozkład **Poissona-dwumianowy** (Poisson binomial); policzony
dokładnie przez splot (bez przybliżeń, bez scipy).

**Wynik:** obserwowane 99/99 grywalnych wobec oczekiwanych pod H0 98,60.
p-wartość jednostronna (H1: generator faworyzuje grywalność) = **0,66**,
próg α = 0,05. Nie odrzuca H0 — ale to prawie nic nie mówi, bo:

**Efekt sufitowy.** W 31 z 33 rund wszystkie 15 typów kanonicznych mieściło
się na planszy (plansze za puste, żeby cokolwiek wykluczyć). Tylko 2 rundy
miały 14/15. Przy takim rozkładzie zmiennej wyjaśniającej test 1 nie ma
mocy niezależnie od liczby par: policzona moc dla wzrostu prawdopodobieństwa
grywalności o 0,01/0,05/0,10 wynosi odpowiednio 0,048 / 0,012 / 0,000 —
moc **maleje**, nie rośnie, bo baza pod H0 jest już przy suficie (p ≈ 0,996).
Żeby ten test cokolwiek wykrył, most musi zebrać dane z **pełniejszych
plansz** (dłuższa gra pod koniec partii, gorsza gra, albo celowe
zapychanie), nie tylko więcej rund w tym samym stylu.

### Test 2 — czy rozmiar klocka koreluje z zapełnieniem

Korelacja rang Spearmana między zapełnieniem planszy a średnim rozmiarem
(liczbą komórek) trzech klocków w tacce tej samej rundy. Pod H0 rozmiar nie
zależy od zapełnienia (generator.py losuje bez świadomości planszy), więc
istotność liczona testem permutacyjnym (20 000 permutacji, ziarno=6):
losowe przetasowanie przypisania zapełnienie↔tacka jest równie prawdopodobne
jak obserwowane.

**Wynik:** n = 33, ρ = **−0,349** (im pełniejsza plansza, tym mniejsze
klocki), p (dwustronne, permutacyjne) = **0,047**, próg α = 0,05.

To przechodzi próg 0,05 *bez korekty* — ale w tej sesji policzono 2 testy na
tych samych 33 parach. Po korekcie Bonferroniego (α = 0,05/2 = 0,025) wynik
**nie przechodzi**. Werdykt: sygnał wart replikacji, nie potwierdzenie.
Nie naciągam tego do „zależna”.

## Ile danych trzeba

Moc testu 2 przy n = 33 (α = 0,05, moc docelowa 0,80): najmniejsze
wykrywalne |ρ| = 0,471 — obserwowane 0,349 jest poniżej tego progu, stąd
wynik niepewny mimo p < 0,05 (mała próba przecenia rzadkie skrajne
wyniki permutacji).

Żeby wykryć efekt wielkości obserwowanej (ρ = 0,349) z mocą 0,80:

| próg istotności | n par potrzebnych |
|---|---|
| α = 0,05 (bez korekty) | **63** |
| α = 0,025 (Bonferroni za 2 testy) | **75** |

Stosunek par do rund w tej próbie: 33 pary / 100 rund ≈ 0,33 pary/rundę
(tacka trzyklockowa trwa ~3 postawienia). Żeby zebrać 63–75 par tym samym
tempem, most musi przejść **około 190–230 rund** — 2–2,3× dłuższy przebieg
niż ten, który dał obecne 33 pary. To dolna granica: liczba zakłada taką
samą siłę efektu i taki sam rozkład zapełnienia jak w tej próbie; jeśli
prawdziwy efekt jest słabszy, potrzeba więcej.

Test 1 osobno wymaga nie tylko więcej par, ale **innego rozkładu
zapełnienia** — sesji, w której plansza realnie dochodzi do stanu, gdzie
część z 15 typów przestaje się mieścić. Sama liczba par tego nie naprawi.

## Co to znaczy dla generatora (pomiar 1)

`generator.py` i `pieces.py` **nie zostały ruszone** — to zadanie tylko
raportuje. Obecne dane nie dają podstawy do przepisania generatora na
warunkowy: jeden test jest strukturalnie ślepy w tej próbie, drugi daje
sygnał, który nie przeżywa korekty za wielokrotne testowanie. Decyzja
o kolejnym pomiarze (dłuższy przebieg mostu, z naciskiem na pełniejsze
plansze) należy do orchestratora.

## Pomiar 2 (#182)

Bilet: #182 · dane: wszystkie `bridge/runs/*/` (surowe `moves.jsonl` /
`moves_chunk*.jsonl` / `chunk*_moves.jsonl`, oraz `d550db3/pomiar.json` —
jedyny przebieg bez surowych logów) · skrypty: `tools/z6_pary.py` (ekstrakcja),
`tools/z6_testy.py` (testy), `tools/z6_pomiar2.py` (jedna komenda, obie
części) · dane pośrednie: `docs/data/z6-pary.json`.

### Ekstrakcja par

Wiersz w logu mostu liczy się jako "nowa tacka" tylko gdy wszystkie 3 sloty
tacki są niepuste (pierwszy ruch po rozdaniu — potem sloty zerują się do
`null` w miarę stawiania). Plansza takiego wiersza jest brana pod uwagę
tylko jeśli da się ją zweryfikować **w tym samym pliku**: wiersz ma indeks
i > 0, poprzedni wiersz ma pole `ok == true`, a jego `observed` zgadza się
z `board` bieżącego wiersza. Wiersz i == 0 (początek pliku/chunka) jest
ZAWSZE odrzucany — nawet jeśli faktycznie kontynuuje poprzedni plik (część
chunków rzeczywiście się łączy, sprawdzone ręcznie np. dla
`c1819ed/chunk2_moves.jsonl` → `chunk3_moves.jsonl`), bo część chunków
zaczyna się po restarcie apki (nieciągłość planszy), a bez dodatkowych
metadanych nie da się tego pewnie odróżnić. Świadomie konserwatywny wybór:
kosztuje najwyżej jedną parę na plik.

Deduplikacja jest globalna, po treści (plansza + nazwy trzech klocków w
kolejności slotów), niezależnie od pliku i przebiegu — retry-loop mostu
podczas zawieszek (okno ustawień, reklama) loguje wielokrotnie identyczny
wiersz, co inaczej policzyłoby tę samą tackę kilka razy.

**Wynik ekstrakcji: 299 par zaakceptowanych, 454 odrzuconych:**

| powód odrzucenia | liczba |
|---|---|
| `poprzedni_wiersz_bez_ruchu` (poprzedni wiersz to okno/reklama/restart — brak `ok`) | 292 |
| `poprzedni_ruch_rozbiezny` (poprzedni ruch miał `ok == false`) | 146 |
| `brak_weryfikowalnego_poprzednika` (i == 0 w pliku) | 11 |
| `duplikat` (ta sama plansza+tacka już policzona) | 5 |

Zero par odrzucono z powodu nierozpoznanego kształtu tacki lub złego rozmiaru
planszy — kandydatów z takimi problemami po prostu nie było wśród wierszy,
które przeszły pierwsze dwa filtry (te problemy w surowych logach istnieją,
ale dotyczą wierszy z zawieszek, które i tak odpadają jako
`poprzedni_wiersz_bez_ruchu`).

Źródła (liczba par per przebieg): `c1819ed` 81, `1402cff` 74, `0d96333` 39,
`1bd38fa` 37, `d550db3` 33, `b4a7d26` 19, `495cd91` 16. Przebiegi `44a8ea2` i
część plików `495cd91`/`c1819ed` bez pełnych, zweryfikowanych tacek nie
wniosły par (m.in. `44a8ea2/pomiar.json` to raport z INNEGO pytania —
reklamy/ustawienia, nie pary plansza-tacka, i nie jest tu czytany).

Zapełnienie planszy w zaakceptowanych parach: min = 0,000, mediana = 0,250,
max = 0,625, średnia ≈ 0,261 — szersze niż w pomiarze 1 (który miał max
0,58, medianę 0,23), ale wciąż bez plansz bliskich pełnym. To ogranicza moc
testów (b) i (d) (patrz niżej).

### Testy (a)–(d)

H0 = dosłowny `generator.py`: typ losowany 1/15 niezależnie od planszy,
potem orientacja 1/n_pos w obrębie typu, trzy klocki losowane niezależnie.
Korekta Bonferroniego liczona za **8 testów** wykonanych w tym pomiarze (2 z
(a) + 4 kwartyle z (b) + 1 z (c) + 1 z (d)): próg istotności
α = 0,05 / 8 = **0,00625**.

**(a) Częstości typów i orientacji (chi-kwadrat).** 897 wylosowanych klocków
(299 par × 3). Typy: χ² = 379,3, df = 14, **p ≈ 2,8×10⁻⁷²**. Orientacje: χ² =
508,1, df = 40, **p ≈ 2,1×10⁻⁸²**. Oba miażdżąco odrzucają dosłowną
jednostajność 1/15, nawet po korekcie. Rozkład typów (obserwowane / 15-tej
części próby):

| typ | komórki | obs. | oczek. | stosunek |
|---|---|---|---|---|
| L | 4 | 131 | 59,8 | 2,19× |
| beam4 | 4 | 121 | 59,8 | 2,02× |
| rect23 | 6 | 104 | 59,8 | 1,74× |
| square2 | 4 | 95 | 59,8 | 1,59× |
| T | 4 | 79 | 59,8 | 1,32× |
| S | 4 | 75 | 59,8 | 1,25× |
| beam2 | 2 | 59 | 59,8 | 0,99× |
| beam3 | 3 | 50 | 59,8 | 0,84× |
| beam5 | 5 | 50 | 59,8 | 0,84× |
| square3 | 9 | 48 | 59,8 | 0,80× |
| corner3 | 3 | 31 | 59,8 | 0,52× |
| corner5 | 5 | 29 | 59,8 | 0,48× |
| 1x1 | 1 | 12 | 59,8 | 0,20× |
| diag2 | 2 | 7 | 59,8 | 0,12× |
| diag3 | 3 | 6 | 59,8 | 0,10× |

Nie widać prostej reguły "mniejsze = częstsze" (najrzadsze to `1x1`, jedna
komórka; najczęstsze `L` i `beam4`, po cztery). Wzór trzyma się niezależnie
sprawdzony na WSZYSTKICH wierszach `bridge/runs/*/*.jsonl` bez filtra
weryfikacji (2535 wystąpień klocków w tackach, licząc też te niepełne/w
trakcie stawiania — metoda inna, bo tam ten sam klocek bywa liczony
wielokrotnie, więc liczby się różnią, ale kierunek jest ten sam: `L` i
`rect23` mocno nad oczekiwaniem, `diag2`/`diag3`/`1x1` mocno pod). To nie jest
artefakt filtra weryfikacji z tego pomiaru.

> **Ważne zastrzeżenie interpretacyjne.** Test (a) sprawdza częstość
> BRZEGOWĄ (marginalną) typów — nie warunkuje po planszy. Odrzuca dosłowny
> model `generator.py` (jednostajność 1/15) sam w sobie, NIEZALEŻNIE od tego,
> czy generator "patrzy" na planszę. Wynik jest zgodny zarówno z hipotezą
> "generator ma stałe, nierówne wagi typów, ale nadal ślepy na planszę", jak
> i z hipotezą "generator jest świadomy planszy" (Z-6 sensu stricto). Testy
> (b)–(d) niżej próbują rozdzielić te dwie hipotezy, warunkując po stanie
> planszy — ale skoro sam rozkład brzegowy już jest tak daleki od H0, dodatnie
> wyniki w (c) mogą częściowo odzwierciedlać tę nierównowagę wag, a nie
> świadomość KONKRETNEJ planszy. Nie da się tego w pełni rozdzielić bez
> modelu H0 z nierównymi, ale planszo-ślepymi wagami (nie zbudowano go w tym
> pomiarze — poza budżetem zadania, `generator.py` nietknięty).

**(b) Test 1 z pomiaru 1 (#78), stratyfikowany po zapełnieniu** (kwartyle tej
próby, progi 0,156 / 0,25 / 0,359 — Poisson-dwumianowy, jak w pomiarze 1,
metoda statyczna bez czyszczenia linii):

| kwartyl | n par | zapełnienie | obs. grywalne | oczek. H0 | p (jednostronne) |
|---|---|---|---|---|---|
| 0 | 78 | 0,000–0,156 | 234 | 234,00 | 1,000 |
| 1 | 77 | 0,172–0,250 | 231 | 231,00 | 1,000 |
| 2 | 80 | 0,266–0,359 | 239 | 239,40 | 0,883 |
| 3 | 64 | 0,375–0,625 | 184 | 186,80 | 0,933 |

Żaden kwartyl, łącznie z najpełniejszym (0,375–0,625), nie pokazuje
faworyzowania grywalnych typów — w najpełniejszym kwartylu obserwacja jest
lekko PONIŻEJ oczekiwania H0, nie powyżej. Efekt sufitowy z pomiaru 1 jest tu
słabszy (mediana grywalnych typów w najpełniejszym kwartylu już bywa < 15),
ale nawet tak test 1 nie znajduje sygnału w żadnym paśmie zapełnienia.

**(c) Grywalność całej tacki** (można postawić wszystkie trzy klocki w
jakiejś kolejności — z czyszczeniem pełnych linii MIĘDZY postawieniami, bo
inaczej kolejność nie miałaby znaczenia; inna, ostrzejsza metoda niż w (b))
wobec oczekiwania H0 liczonego Monte Carlo (500 powtórzeń na planszę, ziarno
= 182, przez `generator.Generator` z `generator.py` — nie reimplementację)
na tych samych 299 planszach, testem Poissona-dwumianowego (p_i różne per
plansza, jak w (b)):

obserwowane 299/299 grywalnych (100%) wobec oczekiwanych pod H0 295,31
(98,8%). p-wartość (jednostronna, H1: generator faworyzuje grywalność) =
**0,0174**, dwustronna = **0,0398**. Przechodzi próg 0,05 *bez korekty*, ale
**nie przechodzi** progu Bonferroniego (0,00625) — dokładnie ten sam wzór co
Test 2 w pomiarze 1: sygnał wart replikacji, nie potwierdzenie. Efekt
sufitowy nadal ogranicza ten test (H0 samo z siebie przewiduje niemal pełną
grywalność, 98,8%, na tak rzadko wypełnionych planszach), stąd test (d).

**(d) To samo, tylko na planszach gdzie H0 daje grywalność < 0,9** — 13 z 299
plansz (4,3%; wszystkie z zapełnieniem ≥ 0,297, głównie z `1402cff` i
`0d96333`). Tu efekt względny jest największy w całym pomiarze: obserwowane
13/13 (100%) wobec oczekiwanych pod H0 10,45 (80,4%) — różnica ok. 20 punktów
procentowych. Mimo to p-wartość (jednostronna) = **0,0559**, dwustronna =
**0,0814** — **nie przechodzi nawet nieskorygowanego progu 0,05**. Przy
n = 13 test jest wyraźnie niedomocowany: przybliżenie normalne daje moc
≈ 0,40 dla wykrycia dokładnie tej różnicy (0,196) przy nieskorygowanym α;
przy α Bonferroniego (0,00625) moc spada do ≈ 0,01.

**Ile danych trzeba (test d).** Dublując rozkład tych samych 13 "trudnych"
plansz (ten sam profil p_i pod H0), moc przy α Bonferroniego (0,00625)
osiąga: k=2× (26 plansz) → 0,22; k=3× (39) → 0,66; **k=4× (52 plansze) →
0,92**. Licząc proporcją z tego pomiaru (13 trudnych plansz na 299 par,
4,3%) i zakładając ten sam udział, 52 trudne plansze odpowiadają ~1200
parom łącznie — **ok. 4× obecnej próby**. To dolna granica: jeśli kolejny
przebieg mostu celowo dąży do pełniejszych plansz (koniec partii, dłuższa
gra), udział "trudnych" plansz powinien wzrosnąć i potrzeba mniej par
łącznie — ale trzeba ich więcej niż 4×, jeśli grywa toczy się w podobnym
stylu jak dotąd.

### Werdykt (pomiar 2)

**H0 dosłowne (`generator.py`: jednostajne 1/15, ślepe na planszę) jest
zdecydowanie odrzucone — ale na podstawie SAMEJ częstości typów (test a,
p ≈ 10⁻⁷²), nie na podstawie zależności od planszy.** To ważny, mocny wynik
sam w sobie: prawdziwa gra NIE losuje typów jednostajnie, niezależnie od
tego, czy "patrzy" na planszę. `docs/calibration-assumptions.md` (Z-6, a
pośrednio i Z-5 w części o wagach) powinno to odnotować jako osobne ustalenie
od pytania "świadomość planszy" poniżej.

**Pytanie kluczowe dla Z-6 — czy dobór klocków zależy od KONKRETNEJ planszy,
a nie tylko od stałych, nierównych wag typów — pozostaje NIEROZSTRZYGNIĘTE.**
Test (b) nie znajduje żadnego sygnału faworyzowania grywalności w żadnym
kwartylu zapełnienia. Testy (c) i (d), czulsze bo sprawdzają grywalność całej
tacki z czyszczeniem linii, dają spójny kierunek (obserwacja > H0) na obu
poziomach agregacji, ale żaden nie przeżywa korekty za wielokrotne
testowanie — (c) jest blisko progu nieskorygowanego (p=0,017), (d) ma
największy efekt względny w całym pomiarze (100% vs 80,4%) ale za mało
plansz (13), by to potwierdzić. Potrzeba około **4× obecnej liczby par
(~1200)**, z naciskiem na planszę zapełnioną ≥ 30–40% (skąd pochodzi
obecnych 13 "trudnych" plansz) — sama liczba par przy tym samym stylu gry
tego nie naprawi, tak jak w pomiarze 1.

### Co to znaczy dla generatora (pomiar 2)

`generator.py` i `pieces.py` **nie zostały ruszone** — to zadanie tylko
raportuje, zgodnie z `## Cel` biletu #182. Silny wynik testu (a) sugeruje, że
model wag typów w `generator.py` (jednostajne 1/15) prawdopodobnie NIE
odpowiada oryginałowi, niezależnie od wyniku pytania o świadomość planszy —
ale to osobna decyzja kalibracyjna (jakie wagi, na jakiej podstawie) od
pytania Z-6 o zależność od planszy, i osobna od tego, czy warto przepisywać
`generator.py` na warunkowy (na to danych wciąż brakuje). Decyzja o
kolejnym pomiarze i o ewentualnej zmianie `generator.py` należy do
orchestratora.

## Pomiar 3 (#191)

Bilet: [#191](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/191) · powód: między pomiarem 2
i tym pomiarem `generator.py` przestał losować typy jednostajnie (1/15) — #186 wpisało do kodu wagi
zmierzone z tych samych 326 par co pomiar 2 plus dołożony `bridge/runs/d878d79/` (`docs/generator-wagi-typow.md`).
Testy (b)–(d) pomiaru 2 liczyły H0 Monte Carlo przez `generator.Generator`, więc automatycznie odziedziczyły
nowe wagi po zmianie kodu — ale test (a) porównywał się z jednostajnością, nie z nowym H0, i cała próba (326
par) posłużyła do wyliczenia tych wag, więc test (a) na tej samej próbie byłby kołowy. Ten pomiar: (1) przelicza
(a) na H0 = skalibrowany `generator.py` (nie 1/15) i tylko na parach spoza próby kalibracyjnej, (2) dolicza dane
z sesji tego cyklu (`bridge/runs/cb91077/`, #190) do wszystkiego innego. Zmiana w kodzie: `tools/z6_testy.py`
(`chi_square_types`/`chi_square_orientations` liczą teraz przeciw `PIECE_TYPE_WEIGHTS` z `generator.py`, nie
przeciw 1/15; nowy stały zbiór `CALIBRATION_RUN_DIRS` — osiem przebiegów, które weszły do kalibracji #186 —
i `is_out_of_calibration()`, który wybiera pary spoza niego). `generator.py`, `scoring.py`, `game.py`,
`pieces.py` **nietknięte** (`reward_shape_changed: no`).

### Dane

`tools/z6_pomiar2.py` uruchomiony ponownie (ekstrakcja przez `tools/z6_pary.py` bez zmian w logice) po
dołożeniu `bridge/runs/cb91077/` na dysku (12 kawałków, polityka greedy, #190) daje **431 par** (wzrost z 326
w #186/pomiar 2), z czego **105 nowych, spoza próby kalibracyjnej wag** — wszystkie z `cb91077`. Zapełnienie
≥ 40%: **76 / 431** par w całej próbie (17,6%), **18 / 105** wśród nowych (17,1%) — podobny udział jak
wcześniej, `cb91077` nie zmienia rozkładu zapełnienia w widoczny sposób. Zapełnienie w całej próbie:
min 0,000, mediana 0,250, max 0,625 (bez zmian względem pomiaru 2 co do zakresu — most wciąż nie zbiera
plansz bliskich pełnym).

### Testy (b)–(d): H0 = skalibrowany `generator.py`, wszystkie 431 par

H0 Monte Carlo (`Generator(seed=182)`, 500 powtórzeń na planszę, jak w pomiarze 2) już automatycznie liczy z
`PIECE_TYPE_WEIGHTS` — kod tych testów się nie zmienił, tylko dane wejściowe (`generator.py` po #186) i liczba
par. Korekta Bonferroniego za 8 testów w tym pomiarze (2 z (a) + 4 kwartyle z (b) + 1 z (c) + 1 z (d)):
α = 0,05/8 = **0,00625**.

**(b) Test 1 z pomiaru 1, stratyfikowany** (progi kwartyli tej próby: 0,156 / 0,25 / 0,359):

| kwartyl | n par | zapełnienie | obs. grywalne | oczek. H0 | p (jednostronne) |
|---|---|---|---|---|---|
| 0 | 114 | 0,000–0,156 | 342 | 342,00 | 1,000 |
| 1 | 110 | 0,172–0,250 | 330 | 330,00 | 1,000 |
| 2 | 118 | 0,266–0,359 | 353 | 353,40 | 0,883 |
| 3 | 89 | 0,375–0,625 | 257 | 260,80 | 0,960 |

Bez zmian jakościowych względem pomiaru 2: żaden kwartyl, łącznie z najpełniejszym, nie pokazuje
faworyzowania grywalnych typów.

**(c) Grywalność całej tacki** (permutacje kolejności, czyszczenie linii między postawieniami) na wszystkich
431 planszach: obserwowane **431/431 grywalnych (100%)** wobec oczekiwanych pod skalibrowanym H0 **425,62
(98,8%)**. p (jednostronne) = **0,002503**, dwustronne = **0,003677**. **To PRZECHODZI korektę Bonferroniego
(0,00625/8)** — pierwszy raz w tej serii pomiarów, że ten test przeżywa korektę za wielokrotne testowanie.
Efekt bezwzględny jest mały (różnica 1,2 punktu procentowego), ale przy n=431 mocny statystycznie.

**(d) To samo, tylko na planszach gdzie H0 daje grywalność < 0,9** — 18 z 431 (4,2%, podobny udział co w
pomiarze 2). Obserwowane **18/18 (100%)** wobec oczekiwanych **14,32 (79,5%)** — różnica ok. 20 punktów
procentowych, w tym samym rzędzie co w pomiarze 2 (tam 20 pp na 13 planszach). p (jednostronne) = **0,01415**,
dwustronne = **0,02987** — **NIE przechodzi** korekty Bonferroniego (próg 0,00625), choć jest bliżej niż w
pomiarze 2 (tam p=0,0559).

**Moc testu (d).** `tools.analiza_z6.power_normal_approx` ma błąd — parametr `alpha` jest przyjmowany, ale
`z_alpha` wewnątrz funkcji jest zakodowany na sztywno jako próg dla α=0,05 (`1.6449`), więc wywołanie z innym
`alpha` po cichu zwraca moc dla α=0,05, nie dla podanego progu (patrz `## Odkrycia` — nie naprawiono, poza
budżetem tego zadania, plik nie jest wymieniony w `## Budżet`). Policzone tu ręcznie, z poprawnym progiem
(`norm_ppf(1 - alpha)` z tego samego modułu, już tam obecny i poprawny) dla obserwowanego efektu (delta =
(18−14,32)/18 = 0,204):

| α | moc dla obserwowanego efektu (0,204) |
|---|---|
| 0,05 (nieskorygowane) | 0,600 |
| 0,00625 (Bonferroni/8) | **0,065** |

Test (d) jest przy tej liczności silnie niedomocowany po korekcie — moc 0,065 znaczy, że nawet gdyby prawdziwy
efekt był dokładnie taki jak obserwowany, test złapałby go tylko raz na ~15 powtórzeń tego pomiaru. Licząc tym
samym sposobem co w pomiarze 2 (k kopii tego samego profilu 18 "trudnych" plansz), moc przy α Bonferroniego
osiąga 0,80 dopiero przy **k=4× (72 plansze)**: k=1→0,065, k=2 (36)→0,501, k=3 (54)→0,878, k=4 (72)→0,984.
Przy obecnym udziale trudnych plansz (18/431 ≈ 4,2%) to odpowiada **~1700 parom łącznie** — więcej niż dolna
granica z pomiaru 2 (~1200), bo obserwowany efekt w tym pomiarze jest nieco mniejszy niż tam zakładano dla
ekstrapolacji.

### Test (a): tylko pary spoza próby kalibracyjnej (105 par, 315 klocków, z `cb91077`)

H0 = skalibrowany `generator.py` (`PIECE_TYPE_WEIGHTS`, nie 1/15). Liczony wyłącznie na 105 nowych parach —
inaczej byłby kołowy, bo te same 326 par posłużyły do wyliczenia wag testowanych tu jako H0.

**Chi-kwadrat typów:** χ² = 32,741, df = 14, **p = 0,003139**. **Chi-kwadrat orientacji:** χ² = 87,857, df = 40,
**p = 1,92·10⁻⁵**. Oba przechodzą korektę Bonferroniego (0,00625) — **nawet skalibrowane wagi typów z #186 nie
pasują do świeżej, niezależnej próby z `cb91077`.** To słabszy efekt niż w pomiarze 2 wobec jednostajności
(tam p ≈ 10⁻⁷², tu p ≈ 0,003 — o 69 rzędów wielkości bliżej progu), ale wciąż odrzuca H0 na progu istotności
tego pomiaru. Obserwowane liczności na 105 tackach (315 klocków) wobec oczekiwanych pod skalibrowanym H0:

| typ | obs. | oczek. (H0 skalibrowane) | stosunek |
|---|---:|---:|---:|
| L | 52 | 45,41 | 1,15× |
| beam4 | 37 | 43,48 | 0,85× |
| beam3 | 28 | 18,04 | 1,55× |
| beam5 | 30 | 18,68 | 1,61× |
| rect23 | 35 | 37,36 | 0,94× |
| square2 | 22 | 32,21 | 0,68× |
| square3 | 22 | 17,07 | 1,29× |
| T | 19 | 28,67 | 0,66× |
| S | 17 | 25,44 | 0,67× |
| corner5 | 13 | 10,31 | 1,26× |
| corner3 | 10 | 10,63 | 0,94× |
| 1x1 | 8 | 4,19 | 1,91× |
| diag2 | 4 | 2,25 | 1,78× |
| beam2 | 18 | 19,33 | 0,93× |
| diag3 | 0 | 1,93 | 0,00× |

Kierunek jest inny niż odchylenie wobec 1/15 w pomiarze 2 (tam `L`/`beam4`/`rect23` były najbardziej nad
oczekiwaniem, teraz `beam3`/`beam5`/`1x1`/`diag2` są nad, `T`/`S`/`square2` pod) — spójne z tym, że wagi #186
już wyłapały główny (silny) sygnał nierówności, a to co zostaje w resztkach jest szumem próby wielkości 105
tacek (315 klocków), nie systematycznym błędem kalibracji w jedną stronę. `diag3` na zerze przy oczekiwanych
1,93 to jedyna pojedyncza kategoria z widocznie dużym odchyleniem względnym, ale przy n_oczek.<2 to i tak
najmniej precyzyjnie zmierzony typ w całej próbie (6 obserwacji w kalibracji #186).

### Liczba par i moc

431 par łącznie (105 spoza kalibracji), 76 z zapełnieniem ≥ 40%. Test (d) — najbardziej ukierunkowany na
wykrycie zależności od KONKRETNEJ planszy — ma moc 0,065 przy obserwowanym efekcie i skorygowanym progu;
potrzeba ~4× obecnej liczby "trudnych" plansz (72 zamiast 18), co przy obecnym udziale odpowiada ~1700 parom
łącznie, żeby mieć moc 0,80.

### Werdykt (pomiar 3)

**Nierozstrzygnięte, ale kierunek przesunął się w stronę "generator widzi planszę" po raz pierwszy w tej
serii pomiarów.** Test (c) — grywalność całej tacki z czyszczeniem linii, wobec H0 liczonego już z
kalibrowanymi wagami typów (więc odporny na zarzut kołowości testu (a)) — **po raz pierwszy przechodzi
korektę Bonferroniego** (p=0,0025 < 0,00625), z efektem w tym samym kierunku co w pomiarze 2 (obserwacja >
H0). Ale test (d), czulszy metodologicznie (patrzy tylko na plansze, gdzie H0 przewiduje grywalność < 90%,
czyli tam gdzie sygnał powinien być najwyraźniejszy), wciąż NIE przechodzi korekty i ma moc zaledwie 0,065
dla dokładnie tego efektu, jaki obserwuje — więc jego brak istotności nie jest dowodem nieobecności efektu,
tylko brakiem mocy. Dodatkowo test (a), teraz liczony przeciw skalibrowanemu H0 i tylko na świeżych,
niekołowych danych, wciąż odrzuca dosłowne `PIECE_TYPE_WEIGHTS` (p=0,0031) — sugeruje, że same wagi typów
mogą wymagać dalszej kalibracji (więcej danych) niezależnie od pytania o świadomość planszy. Potrzeba więcej
danych mostu, z naciskiem na trudne (zapełnienie ≥ 30–40%) plansze, żeby test (d) miał szansę rozstrzygnąć
(c) niezależnie — orchestrator decyduje o kolejnym pomiarze.

## Pomiar 4 (#206)

Bilet: [#206](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/206) · powód: od pomiaru 3 doszły dwie
sesje mostu na dysku — `bridge/runs/4a1796f/` (#199, cztery całe partie) i `bridge/runs/4fb5ed9/` (sesja danych
tego cyklu, pięć całych partii, w tym po raz pierwszy dwa różne warianty niebieskiego ekranu końca gry). Ten
pomiar: (1) uruchamia `tools/z6_pomiar2.py` ponownie z tymi dwiema sesjami na dysku (bez zmiany logiki
ekstrakcji/testów — `CALIBRATION_RUN_DIRS`, `is_out_of_calibration()`, próg H0 bez zmian od #191), (2) liczy
test (a) tylko na parach spoza próby kalibracyjnej wag (teraz trzy przebiegi: `cb91077`, `4a1796f`, `4fb5ed9`),
(3) liczy moc testu (d) poprawionym `power_normal_approx` (parametr `alpha` już nie jest ignorowany, naprawione
w #198). `generator.py`, `scoring.py`, `game.py`, `pieces.py` **nietknięte** (`reward_shape_changed: no`).

### Dane

`tools/z6_pomiar2.py` daje **693 pary** (wzrost z 431 w pomiarze 3), z czego **367 spoza próby kalibracyjnej**
(wzrost z 105) — rozbicie źródeł nowych par: `cb91077` 105 (bez zmian, już policzone w pomiarze 3), `4a1796f`
70 (nowe, #199), `4fb5ed9` 192 (nowe, sesja tego cyklu). Zapełnienie ≥ 40%: **150 / 693** w całej próbie
(21,6%, wzrost z 17,6% w pomiarze 3), **92 / 367** wśród par spoza kalibracji (25,1%). Zapełnienie w całej
próbie: min 0,000, mediana 0,281, max 0,688 (maksimum wyżej niż w pomiarze 3 — `0,625` — dzięki `4fb5ed9`,
gdzie kawałki 1–4 i 18–21 doszły do plansz bardzo pełnych, patrz `pomiar.json` tej sesji).

### Testy (b)–(d): H0 = skalibrowany `generator.py`, wszystkie 693 pary

H0 Monte Carlo (`Generator(seed=182)`, 500 powtórzeń na planszę, bez zmian od pomiaru 2). Korekta Bonferroniego
za 8 testów (2 z (a) + 4 kwartyle z (b) + 1 z (c) + 1 z (d), bez zmian co do liczby): α = 0,05/8 = **0,00625**.

**(b) Test 1 z pomiaru 1, stratyfikowany** (progi kwartyli tej próby: 0,172 / 0,281 / 0,375):

| kwartyl | n par | zapełnienie | obs. grywalne | oczek. H0 | p (jednostronne) |
|---|---|---|---|---|---|
| 0 | 177 | 0,000–0,172 | 531 | 531,00 | 1,000 |
| 1 | 196 | 0,188–0,281 | 588 | 588,00 | 1,000 |
| 2 | 155 | 0,297–0,375 | 464 | 463,00 | 0,397 |
| 3 | 165 | 0,391–0,688 | 477 | 478,80 | 0,738 |

Bez zmian jakościowych względem pomiarów 2 i 3: żaden kwartyl nie pokazuje faworyzowania grywalnych typów —
ten test pozostaje strukturalnie mniej czuły niż (c)/(d) niezależnie od liczby par (patrz pomiar 1).

**(c) Grywalność całej tacki** na wszystkich 693 planszach: obserwowane **693/693 grywalnych (100%)** wobec
oczekiwanych pod skalibrowanym H0 **677,57 (97,8%)**. p (jednostronne) = **1,164·10⁻⁸**, dwustronne =
**1,599·10⁻⁸** — **przechodzi korektę Bonferroniego** (0,00625/8) z dużym marginesem, o cztery rzędy wielkości
mocniej niż w pomiarze 3 (tam p=0,0025).

**(d) To samo, tylko na planszach gdzie H0 daje grywalność < 0,9** — **52 z 693** (7,5%, udział wyższy niż w
pomiarze 3, gdzie było 18/431=4,2% — więcej trudnych/pełnych plansz w nowych sesjach, zgodnie z uwagą o
zapełnieniu wyżej). Obserwowane **52/52 (100%)** wobec oczekiwanych **39,91 (76,7%)** — różnica ok. 23 punkty
procentowe, w tym samym kierunku i rzędzie co w pomiarach 2–3. p (jednostronne) = **3,583·10⁻⁷**, dwustronne =
**4,571·10⁻⁷** — **przechodzi korektę Bonferroniego** (próg 0,00625) po raz pierwszy w tej serii pomiarów.

**Moc testu (d), poprawionym `power_normal_approx`** (#198 — `alpha` już nie jest po cichu ignorowany, próg
liczony `norm_ppf(1 - alpha)` naprawdę zależny od podanego `alpha`):

| α | moc dla obserwowanego efektu (delta = (52−39,91)/52 = 0,233) |
|---|---|
| 0,05 (nieskorygowane) | 0,9995 |
| 0,00625 (Bonferroni/8) | **0,939** |

Test (d) ma teraz moc 0,939 przy progu skorygowanym za wielokrotne testowanie — **wystarczającą** (próg
zwyczajowy 0,80), pierwszy raz w tej serii pomiarów. W pomiarze 3 ten sam test miał moc 0,065 przy mniejszej
próbie (18 trudnych plansz) i mniejszym obserwowanym efekcie; wzrost próby trudnych plansz do 52 (razem ze
wzrostem samego efektu, 0,204→0,233) wystarczył, żeby przekroczyć próg mocy bez ekstrapolacji „ile potrzeba” —
w przeciwieństwie do pomiarów 2–3, ten pomiar **nie wymaga** już oddzielnej tabeli k-krotności do rozstrzygnięcia.

### Test (a): tylko pary spoza próby kalibracyjnej (367 par, 1101 klocków, z `cb91077`+`4a1796f`+`4fb5ed9`)

H0 = skalibrowany `generator.py` (`PIECE_TYPE_WEIGHTS`). Liczony wyłącznie na 367 nowych parach (poza próbą
326 par, na której wyliczono wagi w #186) — nie kołowy z tego samego powodu co w pomiarze 3.

**Chi-kwadrat typów:** χ² = 114,302, df = 14, **p = 8,160·10⁻¹⁸**. **Chi-kwadrat orientacji:** χ² = 170,757,
df = 40, **p = 4,352·10⁻¹⁸**. Oba przechodzą korektę Bonferroniego (0,00625) z ogromnym marginesem — **silniej
niż w pomiarze 3** (tam p≈0,0031/typy — o 15 rzędów wielkości bliżej progu niż tutaj), czyli sygnał
niezgodności skalibrowanych wag typów z nową próbą **rośnie**, nie zanika, wraz z liczbą par spoza kalibracji.
Obserwowane liczności na 367 tackach (1101 klocków) wobec oczekiwanych pod skalibrowanym H0:

| typ | obs. | oczek. (H0 skalibrowane) | stosunek |
|---|---:|---:|---:|
| L | 188 | 158,73 | 1,18× |
| beam4 | 110 | 151,98 | 0,72× |
| rect23 | 112 | 130,59 | 0,86× |
| square2 | 79 | 112,58 | 0,70× |
| T | 72 | 100,19 | 0,72× |
| S | 86 | 88,94 | 0,97× |
| beam3 | 69 | 63,04 | 1,09× |
| beam5 | 90 | 65,29 | 1,38× |
| beam2 | 65 | 67,55 | 0,96× |
| square3 | 67 | 59,67 | 1,12× |
| corner3 | 35 | 37,15 | 0,94× |
| corner5 | 63 | 36,02 | 1,75× |
| 1x1 | 34 | 14,63 | 2,32× |
| diag2 | 19 | 7,88 | 2,41× |
| diag3 | 12 | 6,75 | 1,78× |

Kierunek jest częściowo spójny z pomiarem 3 (`beam5`, `1x1`, `diag2` wciąż wyraźnie nad oczekiwaniami; `T`,
`square2` wciąż pod), ale `corner5` i `diag3` — blisko oczekiwań w pomiarze 3 — są tu wyraźnie nad, a `beam4`,
które w pomiarze 3 było lekko pod (0,85×), pogłębia to odchylenie (0,72×). To nie wygląda już wyłącznie na
szum próby wielkości 105 tacek z pomiaru 3 — przy 367 tackach (3,5× więcej) odchylenia w większości utrzymują
kierunek albo rosną, nie zanikają w stronę zgodności z H0, co sugeruje że same wagi typów z #186 potrzebują
przekalibrowania na szerszej próbie (osobna decyzja od pytania Z-6 o świadomość planszy — patrz `## Cel`
tego biletu).

### Liczba par i moc

693 par łącznie (367 spoza kalibracji), 150 z zapełnieniem ≥ 40%. Test (d) ma teraz moc 0,939 przy
obserwowanym efekcie i skorygowanym progu — **wystarczającą**, bez potrzeby ekstrapolacji na kolejne pomiary
tylko dla tego testu.

### Werdykt (pomiar 4)

**Rozstrzygnięte, w stronę „generator (przynajmniej efektywnie) uwzględnia stan planszy”.** Testy (c) i (d) —
grywalność całej tacki wobec H0 liczonego już ze skalibrowanymi wagami typów (odporne na zarzut kołowości
testu (a)) — **oba przechodzą korektę Bonferroniego** z bardzo małymi p-wartościami (1,16·10⁻⁸ i 3,58·10⁻⁷),
w tym samym kierunku co w pomiarach 2–3 (obserwacja > H0, apka daje grywalne tacki częściej niż losowy model
bez wiedzy o planszy). Kluczowa różnica względem pomiaru 3: test (d), dotąd niedomocowany (moc 0,065 przy
431 parach), ma teraz moc **0,939** przy progu skorygowanym — więc jego istotność nie jest już wynikiem
przypadku przy niskiej mocy, tylko wiarygodnym rozstrzygnięciem. Jednocześnie test (a), liczony na 367 świeżych
parach, odrzuca dosłowne `PIECE_TYPE_WEIGHTS` jeszcze mocniej niż w pomiarze 3 (p spadło z ~0,003 do ~8·10⁻¹⁸)
— wagi typów z #186 prawdopodobnie wymagają przekalibrowania na szerszej próbie, niezależnie od pytania Z-6,
które ten pomiar właśnie rozstrzyga. Decyzja o ewentualnej zmianie `generator.py` (warunkowy na stan planszy,
i/lub przekalibrowane wagi typów) należy do orchestratora — ten bilet **zaraportował, nie naprawił**.

## Odkrycia

- `tools.analiza_z6.power_normal_approx` (bez zmian w tym zadaniu, plik poza budżetem #191) ignoruje
  parametr `alpha` przy liczeniu progu odrzucenia — `z_alpha` jest zakodowany na sztywno jako wartość dla
  α=0,05 (`1.6448536269514722`), więc `power_normal_approx(probs, alpha=0.00625, delta=d)` po cichu zwraca
  moc dla α=0,05, nie dla α=0,00625. Skutek: każde dotychczasowe wywołanie tej funkcji z niedomyślnym `alpha`
  (w tym `power_grid` w `tools/z6_testy.py`, wywoływane tylko z domyślnym 0,05 więc niezależnie poprawne, ale
  API na to nie chroni) dałoby błędny wynik. W tym pomiarze moc dla α Bonferroniego policzona ręcznie obok
  (`norm_ppf` z tego samego modułu jest poprawny, tylko nieużyty w `power_normal_approx`).
- `bridge/runs/cb91077/pomiar.json` (#190), pole `partie[1]` (partia 2, kawałki 3–7), jest wewnętrznie
  sprzeczne: opis kawałka 3 mówi wprost, że `chunk3_moves.jsonl` został nadpisany i utracony (tylko
  `chunk3.log` konsoli ocalał), ale opis partii 2 mimo to twierdzi "wszystkie kawałki ... mają zachowany
  chunkN_moves.jsonl" / `trajektoria_bez_dziur: tak`. Plik faktycznie nie istnieje na dysku (sprawdzone
  `ls bridge/runs/cb91077/*.jsonl`) — partia 2 NIE jest "całą partią bez dziur" w sensie replayu ruch po
  ruchu (brakuje ruchów 12–29 kawałka 3, ok. 18 ruchów na starcie partii). Dlatego w
  `docs/punktacja-apka-vs-wzor.md` (sekcja niżej) użyto z tej sesji tylko partii 3 (kawałki 7–12), jedynej
  faktycznie kompletnej.
