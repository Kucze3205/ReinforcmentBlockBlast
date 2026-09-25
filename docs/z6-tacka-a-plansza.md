# Z-6: czy tacka trzech klocków zależy od stanu planszy

Bilet: #78 · dane: `bridge/runs/d550db3/pomiar.json` (33 pary „plansza → tacka”,
zebrane przez most z prawdziwego Block Blasta, #60) · założenie w
`docs/calibration-assumptions.md` (Z-6) · skrypt: `tools/analiza_z6.py`

## Werdykt

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

## Co to znaczy dla generatora

`generator.py` i `pieces.py` **nie zostały ruszone** — to zadanie tylko
raportuje. Obecne dane nie dają podstawy do przepisania generatora na
warunkowy: jeden test jest strukturalnie ślepy w tej próbie, drugi daje
sygnał, który nie przeżywa korekty za wielokrotne testowanie. Decyzja
o kolejnym pomiarze (dłuższy przebieg mostu, z naciskiem na pełniejsze
plansze) należy do orchestratora.
