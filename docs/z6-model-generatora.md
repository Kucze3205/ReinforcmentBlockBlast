# Z-6: modele generatora świadomego planszy dopasowane do 693 par (#211)

Bilet: [#211](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/211) · poprzedza: `docs/z6-tacka-a-plansza.md`
sekcja „Pomiar 4" (#206) — rozstrzygnęła, że apka daje tacki grywalne częściej niż `generator.py` ślepy na planszę
(testy (c)/(d), p ≈ 1,2·10⁻⁸ i 3,6·10⁻⁷), i że skalibrowane wagi typów (#186) same odrzucają test (a) na 367
świeżych parach (p ≈ 8·10⁻¹⁸) — sygnał, że same wagi też wymagają przekalibrowania, niezależnie od pytania o
świadomość planszy. Skrypt: `tools/z6_model.py`. **To pomiar, nie wdrożenie**: `generator.py`, `pieces.py`,
`game.py`, `scoring.py`, `policies.py`, `ntuple*`, `bench/*`, `docs/data/z6-pary.json` nietknięte —
`reward_shape_changed: no`. O ewentualnej zmianie `generator.py` decyduje cykl 24.

## Dane i podział uczące/testowe

693 pary z `docs/data/z6-pary.json` (ten sam plik co pomiar 4, bez ponownej ekstrakcji). Podział deterministyczny
przez hasz `id` pary (`hashlib.sha1(id).hexdigest()[:8]` jako int, `mod 5`; reszta 0 → testowe, ~20%) —
`tools/z6_model.is_test_id`, jedyne miejsce prawdy, zapisane w kodzie, nie tylko w tym dokumencie. Wynik na tym
uruchomieniu: **539 uczących / 154 testowych**. Podział jest niezależny od źródła (`bridge/runs/*`) i od
przynależności do próby kalibracyjnej wag #186 — w przeciwieństwie do pomiaru 4, tu nie ma problemu kołowości,
bo M0 nie jest dopasowywany do niczego (to stały punkt odniesienia), a M1/M2 są oceniane na ODŁOŻONEJ próbie
testowej, którą widzą dopiero przy ewaluacji.

150/693 par ma zapełnienie planszy ≥ 40% ("trudne"), z obserwowaną grywalnością całej tacki (`tray_playable`,
ta sama funkcja co testy (c)/(d)) **100% (150/150)** — zgodnie z testem (c) pomiaru 4 na całej próbie 693 par.

## Model: jeden wzór, M0/M1 to M2 z p=0

Wszystkie trzy modele są szczególnymi przypadkami jednego wzoru na log-wiarygodność pojedynczej pary
plansza+tacka. Niech:

- `w` — wagi typów (wektor 15 prawdopodobieństw sumujących się do 1); orientacja w obrębie typu zostaje 1/n,
  niezmieniona we wszystkich trzech modelach (jak w #186 — kalibrowanie orientacji to osobne zadanie, poza
  budżetem tego biletu).
- `q(T)` — prawdopodobieństwo POJEDYNCZEGO niezależnego rzutu trzech klocków dającego dokładnie tackę `T`, pod
  wagami `w`: iloczyn po 3 slotach `w[typ]/n_poz(typ)`. Nie zależy od planszy — to CAŁY model M0/M1.
- `π` — P(świeży niezależny rzut tacki jest grywalny — `tray_playable` zwraca `True` — na TEJ planszy) pod
  wagami `w`.
- `p`, `k` — parametry M2: jeśli rzut nie jest grywalny, z prawdopodobieństwem `p` losuj od nowa (świeży,
  niezależny rzut), do `k` prób łącznie; po `k`-tej próbie przyjmij to, co wypadło, nawet jeśli niegrywalne.
- `S(p,k,π) = Σ_{m=0}^{k-1} ((1-π)p)^m` — suma geometryczna (liczba "efektywnych" prób do zatrzymania).

Z niezależności rzutów (iid, proces bez pamięci) rozkład tacki WARUNKOWY na "grywalna"/"niegrywalna" jest taki
sam, niezależnie od tego, na której próbie proces się zatrzymał — jedyna zmiana to WAGA każdej z tych dwóch
klas zdarzeń. Stąd czynnik `π` skraca się w liczniku i mianowniku, dając zamknięty wzór:

```
log L(T | plansza) = log q(T) + log S(p,k,π)                              gdy T grywalna
log L(T | plansza) = log q(T) − log(1−π) + log(1 − π·S(p,k,π))            gdy T niegrywalna
```

Przy `p=0`: `S=1` zawsze, drugi wzór upraszcza się do `log q(T)` (bo `−log(1−π)+log(1−π)=0`) — **M0 i M1 to
M2 z `p=0`, niezależnie od planszy**, sprawdzone jako własność w `tests/test_z6_model.py`
(`TestLoglikReducesToM1AtPZero`). To jedyny sposób, w jaki `π` (a więc plansza) wpływa na M0/M1: wcale.

`π(w)` liczone importance samplingiem, nie ponownym DFS przy każdej iteracji dopasowania: dla każdej planszy
losujemy RAZ (seed stały, `IMPORTANCE_SEED=211`) 400 trójek póz jednostajnie z 41 (niezależnie od `w`) i
zapisujemy `tray_playable` (funkcja z `tools/z6_testy.py` — ta sama, co testy (c)/(d), zgodnie z issue #211:
"nie pisz nowej") każdej próbki. Dla DOWOLNEGO `w` (w tym w trakcie optymalizacji) `π(w)` to ważona średnia
tych samych próbek (waga = iloraz gęstości `w` do jednostajnej) — jeden przebieg DFS na próbkę, nie jeden na
iterację optymalizacji.

## Dopasowanie

- **M0** — `PIECE_TYPE_WEIGHTS` z dzisiejszego `generator.py`, znormalizowane. Bez dopasowania (0 parametrów
  do wdrożenia ponad to, co już jest w kodzie).
- **M1** — MLE w zamkniętej formie na części uczącej: `waga_typu ∝ (liczba_obserwacji + 0,5)` (wygładzanie
  Laplace'a, żeby typy o zerowej liczbie obserwacji w podziale uczącym — `diag2`/`diag3` mają tylko kilkanaście
  obserwacji łącznie — nie dawały `log(0)` na teście). 14 wolnych parametrów (15 wag sumujących się do 1).
- **M2** — wagi typów i `p` dopasowane RAZEM numerycznie: współrzędnościowy wschodzący złoty podział (naprzemian
  1-wymiarowe wyszukiwanie złotego podziału po `p`, potem po każdej z 15 wag z ufnością multiplikatywną
  ×0,3–×3, kilka rund), inicjalizacja wagami M1. `k` wybrany siatką po `{1,2,3,5}` maksymalizującą
  wiarygodność UCZĄCĄ (nie testową — `k` to hiperparametr wybrany bez podglądania testu). To NIE jest
  zamknięta MLE — przybliżony numeryczny optimum, udokumentowana metoda w `tools/z6_model.py`
  (`fit_m2_given_k`). 15 wolnych parametrów (14 wag + `p`; `k` to wybór dyskretny, nie ciągły parametr).

## Wyniki (jeden przebieg `python3 tools/z6_model.py`, w pełni deterministyczny)

| model | n. parametrów | k | p | log-wiar. ucząca | log-wiar. testowa | różnica vs M0 (SE) | przewidywana grywalność na trudnych (obs. 1,000) |
|---|---:|---:|---:|---:|---:|---:|---:|
| M0 | 0 | — | 0 | −5651,74 | −1615,04 | 0,00 (—) | 0,9114 |
| M1 | 14 | — | 0 | −5624,75 | −1616,44 | −1,40 (SE 4,61) | 0,9114 |
| M2 | 15 | 5 | 1,0000 | −5611,25 | **−1613,36** | **+1,68 (SE 4,92)** | **0,9976** |

SE różnicy: odchylenie standardowe log-wiarygodności PAROWANEJ różnicy na 154 parach testowych
(`d_i = log L_M(i) − log L_M0(i)`, `SE(Σd_i) = sd(d_i)·√n`) — to przybliżony test parowany na próbie
testowej, alternatywa dla testu ilorazu wiarygodności (który wymagałby zagnieżdżonych modeli ocenianych NA
TYCH SAMYCH danych uczących, a tu porównanie jest celowo poza próbą).

**Log-wiarygodność testowa nie rozróżnia modeli — różnice (±1–2 naty) są dużo mniejsze niż SE (~5 natów).**
M1 wypada nieznacznie GORZEJ niż M0 na teście mimo lepszej wiarygodności uczącej (typowy obraz przy
przekalibrowaniu na innym podziale niż ten, na którym powstały `PIECE_TYPE_WEIGHTS` — różnica nieistotna).
M2 wypada nieznacznie lepiej, też nieistotnie w sensie tej różnicy.

**Kolumna grywalności na trudnych planszach rozróżnia modele znacznie ostrzej.** M0 i M1 (bez świadomości
planszy, `p=0`) przewidują identyczną grywalność ~91,1% na 150 trudnych planszach (zapełnienie ≥ 40%) —
wagi typów same nie zmieniają tego, bo obie te miary liczą `π(w)`, a przeważenie typów w stronę częstszych
nie podnosi istotnie łącznej grywalności tacki. **Obserwowane 100,0%** — dokładnie zgodne z testem (c)/(d)
pomiaru 4. M2 z dopasowanym procesem odrzucania przewiduje **99,76%** — o rząd wielkości bliżej obserwacji niż
M0/M1, mimo że jego log-wiarygodność testowa nie jest statystycznie odróżnialna od M0. To pokazuje, że
log-wiarygodność testowa (zdominowana przez liczne łatwe plansze, gdzie każdy model przewiduje wysokie `π`
poprawnie) jest mniej czuła na WŁAŚNIE ten efekt niż bezpośrednia miara grywalności na trudnych planszach —
spójne z tym, dlaczego pomiar 4 potrzebował osobnych testów (c)/(d) stratyfikowanych po trudności, zamiast
polegać na teście (a)/(b).

## Wniosek: który model do `generator.py`

**Żaden z trzech modeli nie jest gotowy do wdrożenia bez zastrzeżeń, ale M2 jest jedynym, który odtwarza
kierunek i skalę efektu z pomiaru 4** (grywalność na trudnych planszach 99,76% dopasowanego modelu vs 100,0%
obserwowane, kontra 91,1% modeli bez świadomości planszy). Ostrzeżenie: dopasowany `p=1,0000` i `k=5` (górna
granica siatki hiperparametrów) — optymalizator "chce" jeszcze więcej prób odrzucenia niż przetestowano, więc
**`p=1, k=5` to dolna granica tego, ile odrzucania potrzeba, nie ustalona wartość** — patrz `## Odkrycia`.
Jedna liczba parametrów do wdrożenia, GDYBY orchestrator zdecydował się na M2: **15** (14 wag typów + `p`;
`k` to wybór dyskretny algorytmu, nie liczbowy parametr wagowy) — więcej niż dzisiejsze 0 (M0 to stałe wagi w
kodzie) i więcej niż M1 (14), ale wciąż rząd wielkości mniejszy niż pełny model warunkowy na całej planszy.
Decyzja o wdrożeniu (i o tym, czy dociągnąć `k`/`p` do właściwego optimum poza granicą siatki użytą tutaj)
należy do cyklu 24 — ten bilet **zaraportował, nie naprawił**.

## Kryterium 3: szacunek skutku dla benchmarku

20 partii `lookahead-ntuple:ntuple/survival-ad-70k.json` (dowolne wagi z `ntuple/`, ten sam silnik co
`tools/collect_states.py`, bez zapisu pliku), sufit 240 postawień/partię. Plansze próbkowane w chwili
odświeżenia tacki (`placements` wielokrotność 3 — ten sam moment, co pary w `docs/data/z6-pary.json`): **1203
plansze**. Na każdej: 150 symulowanych rzutów tacki pod M0 i pod M2 (z jego procesem odrzucania, `p=1,0000`,
`k=5`), sprawdzenie `tray_playable`:

| wielkość | wartość |
|---|---:|
| plansz | 1203 |
| rzutów/planszę | 150 |
| **odsetek nieukładalnych tacek, M0** | **0,308%** (556/180450) |
| **odsetek nieukładalnych tacek, M2 (najlepszy)** | **0,0017%** (3/180450) |

**Wdrożenie M2 zmniejszyłoby odsetek nieukładalnych tacek na planszach z realnych partii przeszukiwania
ok. 185× (0,308% → 0,0017%)** — na 1203 próbkowanych planszach z 20 partii to różnica między ~3,7 a ~0,02
nieukładalnej tacki na każde 1203 odświeżenia. Bezwzględna skala jest mała (nieukładalna tacka to i tak rzadkie
zdarzenie nawet pod M0 na planszach spotykanych przez dobre przeszukiwanie — inaczej niż na "trudnych" planszach
z próby mostu, gdzie apka gra dłużej i trafia trudniejsze stany), ale kierunek i rząd wielkości są spójne z
tabelą wyżej: M2 prawie eliminuje nieukładalne tacki, gdziekolwiek by ich szukać.

## Odkrycia

- Dopasowane `p=1,0000` i `k=5` w M2 leżą na GÓRNEJ granicy przeszukanej siatki hiperparametrów
  (`P_GRID=[0,1]` obejmuje 1,0 jako punkt końcowy, `K_CANDIDATES=(1,2,3,5)` kończy się na 5) — optymalizator
  konsekwentnie wybiera "więcej odrzucania" niż udostępniono. To sugeruje, że rzeczywisty proces generujący
  dane może potrzebować odrzucania silniejszego niż model z ograniczoną liczbą prób w ogóle przewiduje
  (np. odrzucanie "twarde": zawsze redraw aż do sukcesu, bez `p<1` i bez sufitu `k`) — model wart zmierzenia w
  kolejnym zadaniu, jeśli orchestrator zdecyduje się rozwijać kierunek M2, zamiast poszerzać obecną siatkę
  (co przy tej metodzie dopasowania jest tanie — `fit_m2_given_k` przyjmuje `k` jako parametr).
- Optymalizacja wag M2 to współrzędnościowe wyszukiwanie złotego podziału z zaufaniem multiplikatywnym
  (nie zamknięta MLE, nie gradient) — szybkie i deterministyczne, ale nie ma gwarancji zbieżności do globalnego
  optimum. Nie zweryfikowano wielostartowo (różne inicjalizacje); jeśli powierzchnia wiarygodności ma więcej
  niż jedno lokalne maksimum, zgłoszone `w`/`p` dla M2 mogą nie być globalnym MLE.

## Zmiana w kodzie (#211)

`tools/z6_model.py` (nowy plik) + `tests/test_z6_model.py`. `generator.py`, `pieces.py`, `game.py`,
`scoring.py`, `policies.py`, `ntuple*`, `bench/*`, `docs/data/z6-pary.json` — nietknięte, tylko odczyt (import)
tam, gdzie kryterium 3 wymagało uruchomienia partii `lookahead-ntuple` (`benchmark.build_policy`, `game.Game`).

`reward_shape_changed: no` — to pomiar; nie zmienia `game.step`, punktacji ani żadnej wartości, którą agent
optymalizuje.

---

## #217: poszerzona siatka `k`, wariant „do skutku", decyzja o wagach, wdrożenie

Bilet: [#217](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/217). Kontynuacja pomiaru wyżej —
**#211 zostawiło `p=1,0000` i `k=5` na górnej granicy siatki** (`P_GRID=[0,1]`, `K_CANDIDATES=(1,2,3,5)`),
z jawną notatką w `## Odkrycia`, że dane chcą więcej odrzucania niż siatka dopuszczała. #217 poszerza siatkę i
faktycznie wdraża wynik w `generator.py` (w przeciwieństwie do #211, które było **tylko pomiarem**).

### Poszerzenie siatki i wariant „do skutku"

`K_CANDIDATES` w `tools/z6_model.py` poszerzone do `(1, 2, 3, 5, 10, 20, 50, K_DO_SKUTKU=1000)`. Wariant „do
skutku" (losuj, aż tacka będzie grywalna, z awaryjnym limitem prób) **nie wymaga osobnego wzoru** — w tym
samym modelu `S(p,k,π) = Σ_{m=0}^{k-1}((1−π)p)^m` to po prostu `k` tak duże (`1000`), że na żadnej z 693
obserwowanych plansz nie jest w praktyce osiągane (limit działa wyłącznie jako zapora przeciw nieskończonej
pętli na planszy, na której naprawdę nie ma grywalnej tacki). `p` zostaje w `[0,1]`, dopasowywane siatką +
złotym podziałem jak dotąd.

### Kryterium 2: wagi M0 kontra wagi dopasowane razem z `p`,`k`

Dodano `fit_m2_simple` (`tools/z6_model.py`): M2 z wagami typów **zamrożonymi na `PIECE_TYPE_WEIGHTS`** (M0),
dopasowywane jest wyłącznie `p` (siatka `K_CANDIDATES` × złoty podział po `p`) — w przeciwieństwie do
dotychczasowego M2 (tu: **M2-fit**), które dopasowuje wagi i `p` RAZEM. Nazwane **M2-simple**.

### Wyniki (`python3 tools/z6_model.py`, deterministyczne, ~6 min 52 s na tej maszynie)

| model | n. parametrów | k | p | log-wiar. ucząca | log-wiar. testowa | różnica vs M0 (SE) | przewidywana grywalność na trudnych (obs. 1,000) |
|---|---:|---:|---:|---:|---:|---:|---:|
| M0 | 0 | — | 0 | −5651,74 | −1615,04 | 0,00 (—) | 0,9114 |
| M1 | 14 | — | 0 | −5624,75 | −1616,44 | −1,40 (SE 4,61) | 0,9114 |
| M2-simple (wagi M0) | 1 | 1000 („do skutku") | 1,0000 | −5638,53 | **−1611,22** | **+3,82 (SE 1,65)** | **1,0000** |
| M2-fit (wagi dopasowane) | 15 | 1000 („do skutku") | 1,0000 | −5610,95 | −1613,30 | +1,74 (SE 4,93) | 1,0000 |

Oba warianty M2 zbiegają do **`k=1000` (górna nowa granica siatki -> „do skutku") i `p=1,0000`** — spójne z
sygnałem z #211, że proces chce nieograniczonego odrzucania, nie skończonej liczby prób. Podniesienie granicy
siatki z 5 do 1000 nie napotkało nowego sufitu pośredniego — optymalizator idzie od razu na sam koniec
poszerzonej siatki, co jest zgodne z odkryciem #211 i potwierdza, że model **rzeczywiście chce „do skutku"**,
nie jakiejś pośredniej wartości `k` między 5 a 1000.

### Decyzja kryterium 2: M2-simple (wagi M0, bez zmian)

`M2-fit` vs `M2-simple` na teście: różnica log-wiarygodności = **−2,09 (SE 4,57)** — M2-fit **NIE** wygrywa o
więcej niż 1 SE (wygrywa 0 z 4: różnica jest nawet ujemna). Zgodnie z regułą wyboru z `## Cel` #217
(„wdrażasz prostszy, chyba że dopasowane wygrywają o > 1 SE") **wdrożony jest M2-simple: `PIECE_TYPE_WEIGHTS`
bez zmian + odrzucanie „do skutku"**. Potwierdza to wniosek #211 `docs/z6-model-generatora.md` (ten plik) i
`docs/z6-tacka-a-plansza.md`: **wagi typów to szum, różnicę robi samo odrzucanie planszowe** — nie trzeba
przeliczać `PIECE_TYPE_WEIGHTS`, tylko dodać warstwę odrzucania nad istniejącym losowaniem.

### Kryterium 3 (zaktualizowane): skutek dla benchmarku pod wybranym modelem

Ta sama metoda co w #211 (20 partii `lookahead-ntuple:ntuple/survival-ad-70k.json`, sufit 240 postawień,
1203 próbkowane plansze, 150 rzutów/planszę), teraz z wybranym M2-simple (`p=1,0000`, `k=1000`):

| wielkość | wartość |
|---|---:|
| **odsetek nieukładalnych tacek, M0** | **0,3037%** (548/180450) |
| **odsetek nieukładalnych tacek, M2-simple (wybrany)** | **0,0000%** (0/180450) |

Na próbce 1203 plansz z realnych partii przeszukiwania `lookahead-ntuple`, odrzucanie „do skutku" **nie
wylosowało ani jednej nieukładalnej tacki** (0/180450 rzutów) — różnica jest jakościowa (eliminacja), nie
tylko ilościowa poprawa, bo `p=1` nigdy nie akceptuje niegrywalnej tacki, dopóki limit 1000 prób nie zostanie
wyczerpany (na tej próbce nigdy).

### Wdrożenie w `generator.py`

Skoro wybrany model to `PIECE_TYPE_WEIGHTS` bez zmian + `p=1,0000` (zawsze redraw) + `k=1000` (limit
awaryjny), wdrożenie sprowadza się do: losuj tackę jak dotychczas (`_next_piece` × 3); jeśli `tray_playable`
(z `board.py`, ta sama funkcja co #211/testy (c)/(d)) na BIEŻĄCEJ planszy zwraca `False`, losuj ponownie, aż
do 1000 razy; po 1000 nieudanych próbach przyjmij ostatni losowany zestaw (awaryjny limit — patrz `Generator`
niżej). `None` z `tray_playable` (limit węzłów DFS wyczerpany, `board.TRAY_PLAYABLE_NODE_BUDGET`) traktowany
jak `False` (redraw) — brak rozstrzygnięcia nie jest dowodem grywalności.

**Generator pozostaje ślepy na planszę, gdy nikt mu jej nie poda** — `Generator.__init__`/`next_pieces` mają
dziś (przed #217) sygnaturę bez planszy, a `game.py`/`policies.py` są w tym bilecie NIETKNIĘTE (patrz
`## Kryteria akceptacji` #217), więc `next_pieces()` wywoływane bez planszy (jak dziś w `game.py`,
`policies.py`) **zachowuje się DOKŁADNIE jak dotąd, bit w bit** — świadomość planszy jest **opt-in** przez
nowy, opcjonalny parametr (`Generator(seed, board=...)` / `generator.board = ...`), nieużywany przez żadne
dzisiejsze wywołanie w kodzie produkcyjnym. To NIE jest obejście zakazu dotykania `game.py` — to jest
dokładnie granica tego bloku pracy: #217 przygotowuje i mierzy generator świadomy planszy jako bibliotekę,
wpięcie go w pętlę `Game`/`benchmark.py` na stałe to osobna decyzja (zmieniłaby odcisk benchmarku przez
`game.py`, nie tylko `generator.py`, i wymaga własnego pomiaru). Koszt sprawdzania grywalności i sam
przełącznik `legacy` — patrz `docs/generator-swiadomy-planszy.md`.

`reward_shape_changed: no` — generator nie zmienia `game.step` ani punktacji; zmienia się DYNAMIKA środowiska
(rozkład tacek zależny od planszy zamiast stałego), nie sama nagroda.
