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
