# Kalibracja symulatora — czego NIE potwierdziliśmy

Bilet: [#17](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/17) · mapa: [#1](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/1)
Źródło ustaleń: [#2](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/2) oraz `docs/research/block-blast-rules.md` (gałąź `research/block-blast-rules`)

Symulator odwzorowuje teraz **najlepszą dostępną rekonstrukcję** reguł Block Blasta.
Rekonstrukcja to nie pomiar. Ten dokument wypisuje każde miejsce, w którym symulator
zgaduje, i mówi, **jakim pomiarem most do oryginału ma to rozstrzygnąć**.

Wydawca nie publikuje żadnej liczby o punktacji ani o generatorze ([#2](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/2), §1).
Nie istnieje ani jedna reguła punktacji, którą dałoby się nazwać potwierdzoną na oryginale.
Wszystko poniżej jest założeniem — różnią się tylko siłą przesłanek.

---

## Co jest solidne

| Reguła | Status | Podstawa |
|---|---|---|
| Plansza 8×8, tacka trzech klocków, brak rotacji, brak timera | **potwierdzone przez wydawcę** | blockblast.com, App Store |
| Wiersz **i** kolumna znikają | **potwierdzone przez wydawcę** | blockblast.com |
| Koniec gry, gdy nie da się postawić żadnego klocka | **potwierdzone przez wydawcę** | blockblast.com |
| `board.py` zgodny z referencją | zweryfikowane w kodzie | [#2](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/2), §4 — **nie ruszane w tym bilecie** |
| Wzór `combo · 10·ℓ·(ℓ−1)` | dwie niezależne reimplementacje, zbieżne co do cyfry | najmocniejsza przesłanka, jaką mamy |

---

## Założenia do zweryfikowania przez most

Uporządkowane wg stosunku „ile zmienia" do „ile kosztuje pomiar".

### Pomiar 1 z 3 (R10): 2026-09-21, Block Blast 10.7.5

Pierwszy przebieg mostu ([#18](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/18),
[run 35610307974](https://github.com/Kucze3205/ReinforcmentBlockBlast/actions/runs/35610307974),
`bridge-out/moves.jsonl`). Skalibrowany wzór przewidział **każdy** z 18 przyrostów
wyniku co do punktu, łącznie z 4 liniami w tutorialu (124 = 4 + 1·120) i wygaśnięciem
combo dokładnie w ruchu, który wskazuje licznik.

| Założenie | Wynik sesji 1 | Rozstrzygające ruchy |
|---|---|---|
| Z-1 | **10 za linię**, nie 80 | 1 linia przy combo 2/3/4 → bonus 20/30/40 |
| Z-2 | **combo += 1** (źródło A), nie += ℓ | 2 linie przy combo 0 → bonus 20, nie 40 |
| Z-3 | **licznik 3 + pozostałe w tacce** — przeżywa 3 postawienia przy pełnej tacce, ginie przy 4. bez czyszczenia | combo 4 wygasło w ruchu 12 |
| Z-7 | **punkty za postawienie = liczba komórek** | każdy ruch bez czyszczenia |

To jedna sesja. Z-9 wymaga jeszcze dwóch, w innych dniach — dopiero wtedy te
wiersze przechodzą do „solidne".

### Przeliczenie maszynowe tych samych logów: 2026-09-23 ([#30](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/30))

Sesja 1 porównywała przyrosty ręcznie. `tools/analyze_bridge.py` robi to teraz
z logu, ruch po ruchu, niosąc combo między ruchami — i na dwóch przebiegach
(35610307974, 35609533868) **skumulowany wynik symulatora zgadza się z licznikiem
apki co do jedności w 32 z 37 porównań**.

Wszystkie pięć wyjątków to ta sama rzecz: licznik w grze **dolicza się animacją**,
więc odczyt zrobiony za wcześnie zaniża wynik, a różnica wraca do zera przy
następnym ruchu. Żaden nie jest trwały. Stąd dwa zabezpieczenia w moście: wynik
wchodzi do warunku stabilizacji klatki, a spadek wyniku odrzucamy jako błąd OCR
(w Block Blaście wynik nie maleje).

**Wniosek: cała reszta wzoru jest zgodna z apką. Jedyne, co się rozjeżdżało, to
bonus za pustą planszę — patrz Z-4.**

### Z-1 — punkt bazowy: 10 za linię czy 80 za linię *(rozstrzyga najtaniej)*

Symulator: `line_bonus(1) = 10`.
Sprzeczność między źródłami: 10 punktów za linię vs 10 za każdą **usuniętą komórkę**
(czyli 80 za linię). To ośmiokrotna różnica w całej skali punktowej.

**Pomiar:** postawić klocek czyszczący dokładnie **jedną** linię przy combo = 0
i odczytać przyrost wyniku. `10` albo `80` zamyka sprawę jednym ruchem.

**Zmierzone: 10 — ale tylko do combo 5.** Patrz Z-10.

### Z-10 — `line_bonus` nie jest stałą, rośnie schodkami wraz z combo *(nowe, otwarte)*

Symulator: `line_bonus(1) = 10` zawsze, niezależnie od combo.
Apka: **10 przy combo 1–5, 15 przy 6–10, 20 przy 11–16.**

| combo | B(1) w apce | czystych odczytów |
|---|---|---|
| 1–5 | 10 | 33 |
| 6–10 | 15 | 13 |
| 11–16 | 20 | 10 |
| powyżej 16 | **niezmierzone** | — |

Zmierzone na przebiegach [35841098505](https://github.com/Kucze3205/ReinforcmentBlockBlast/actions/runs/35841098505)
i [35842812364](https://github.com/Kucze3205/ReinforcmentBlockBlast/actions/runs/35842812364).
Wewnątrz schodka nie ma ani jednego wyjątku; obie granice (5→6 i 10→11) mają
pomiary po obu stronach. Combo mnoży ten bonus tak jak dotąd (R-2) — schodek
zmienia **bazę**, nie mnożnik.

Dlaczego nikt tego nie widział wcześniej: **żaden przebieg mostu przed [#30](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/30)
nie przekroczył combo 4**, a pierwszy schodek zaczyna się przy 6. Cała zgodność
„co do punktu" z [#18](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/18)
była prawdziwa — i cała mieściła się w pierwszym schodku.

**Czego nie wiemy i dlaczego pomiar stoi:** gdzie kończy się trzeci schodek.
Reguła „co 5 combo o 5 więcej" przewiduje 25 przy combo 16, a zmierzone jest
czyste 20 — więc trzeci schodek jest szerszy albo ostatni. Powyżej combo 16
licznik w grze **animuje się dłużej, niż most czeka**: pojedyncze czyszczenie
daje tam 400–600 punktów, odczyty przestają być całkowitymi wielokrotnościami
combo i pomiar traci sens. Domknięcie wymaga czekania na ustabilizowanie licznika
proporcjonalnego do przyrostu, nie stałej liczby prób.

**Dlaczego to ma znaczenie mimo zamrożonej punktacji ([#20](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/20)):**
wysokie combo to reżim, w którym żyje silny bot, a nagroda agenta **jest przyrostem
wyniku** ([#23](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/23)).
Symulator zaniża tam grę nawet dwukrotnie, więc uczy bota, że długie serie czyszczeń
są warte mniej, niż są naprawdę.

### Z-2 — o ile rośnie combo po czyszczeniu

Symulator: `combo += 1` niezależnie od liczby wyczyszczonych linii (źródło A).
Źródło B: `combo += liczba_linii`.
Przy ℓ = 1 oba warianty dają to samo, więc rozbieżność ujawnia się dopiero przy
wielokrotnych czyszczeniach — i tam różnica w wyniku końcowym jest ogromna.

**Pomiar:** dwa razy z rzędu wyczyścić po 2 linie i porównać drugi przyrost.

### Z-3 — jak wygasa combo

Symulator: licznik startuje z 3, po czyszczeniu jest ustawiany na
`3 + liczba klocków pozostałych w tacce` (czyli 3/4/5), a combo ginie, gdy licznik
spadnie do 1. Praktycznie: combo przeżywa **dwa** postawienia bez czyszczenia
i ginie przy trzecim.

To interpretacja wyrażenia bitowego `3 + (b0!=b2) + (b1!=b2)` ze źródła A. Farmy SEO
twierdzą zgodnie coś przeciwnego: że combo ginie **natychmiast** po postawieniu bez
czyszczenia. Oba kody referencyjne przeczą farmom, a raporty graczy o „bugu z combo"
opisują mechanikę z licznikiem.

**Pomiar:** wyczyścić linię, potem postawić 1, 2 i 3 klocki bez czyszczenia,
za każdym razem czyszcząc ponownie i odczytując mnożnik.

### Z-4 — bonus za pustą planszę: ~~300 czy 360~~ **zmierzone: zera nie ma** *(zamknięte)*

Odpowiedź, której nie przewidywało żadne źródło: **0**. Oba źródła referencyjne
dawały 300, farma SEO 360, a apka nie płaci nic.

Rozstrzygnęły dwa pełne czyszczenia w przebiegu 35610307974 (ruchy 0 i 2). Przy
`FULL_CLEAR_BONUS = 300` skumulowany wynik symulatora wyprzedzał licznik apki
dokładnie o 300 na każde czyszczenie — najpierw o 300, potem o 600, i tak do końca
przebiegu. Przy zerze offset jest zerowy na każdym ustabilizowanym ruchu.

Pomiar okazał się darmowy: zdarzenie uchodziło za rzadkie, ale tutorial zaczyna
partię od planszy, którą pierwszy ruch czyści do końca, więc **każdy przebieg mostu
od świeżej instalacji dostaje je za darmo**.

Stałej nie ma już w kodzie ani gałęzi, która ją dodawała — zero nie jest wartością
do przestrojenia, tylko brakiem mechaniki. Linia bazowa zachłannej na 100 seedach
spadła o 1,6% (760,88 → 748,39), przeżycie o 0,2% — poniżej progu ±10% z
[#8](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/8), więc szereg
punktowy nie jest zerwany. Część spadku to zmiana wyborów zachłannej, która
przestała gonić pełne czyszczenie.

### Z-5 — zbiór klocków: 41 poz *(największa niewiadoma)*

Symulator: 15 typów kanonicznych domkniętych na D4 → 41 orientacji, zgodnie ze
źródłem A. Klon BlockBlastPlay mówi o **34** kształtach we własnym buildzie.
Poprzednia pula repo miała 16 kształtów = 39% poz referencyjnych.

**Nikt publicznie nie zmierzył puli oryginału.** To nie jest spór między źródłami —
to wynik negatywny ([#2](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/2), §3.1).

**Pomiar:** most loguje każdą tackę. Po kilku tysiącach tacek zbiór unikalnych
kształtów jest zamknięty z dużą pewnością.

**Stan po 414 dobraniach ([#30](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/30)):
pula się broni.** Widziane 39 z 41 poz, **zero kształtów spoza puli**. Dwie
niewidziane to `diag2-1` i `diag3-0` — a ich bliźniacze orientacje (`diag2-0`,
`diag3-1`) pojawiły się, więc brak nie jest brakiem typu. Wyjaśnia go Z-6:
przekątne są po prostu bardzo rzadkie, nie nieobecne. Wariant „34 kształty"
z BlockBlastPlay nie ma poparcia w pomiarze.

### Z-6 — rozkład doboru klocków

Symulator: niezależnie, 1/15 na typ kanoniczny, potem 1/n na orientację.
Bez świadomości planszy, bez gwarancji grywalności tacki.

To **założenie modelowe autora referencji**, wybrane dla wygody treningu RL
(stacjonarny MDP), nie pomiar. Klony przeglądarkowe, które chciały być grywalne,
wszystkie dorzucały świadomość planszy: ważenie kształtów wg zapełnienia i
sprawdzanie, czy tacka da się rozegrać.

**Pomiar:** ta sama seria tacek co w Z-5, ale analizowana warunkowo względem
zapełnienia planszy. Jeśli rozkład zależy od stanu planszy, **generator symulatora
trzeba przepisać na warunkowy**, a nie tylko przestroić.

**Zmierzone: 1/15 na typ jest obalone** ([#30](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/30),
414 dobrań z 6 przebiegów). χ² = 166,5 przy df = 14, p ≈ 3·10⁻²⁵ — to nie jest
wynik na granicy.

| typ | apka | symulator |
|---|---|---|
| L | 14,0% | 6,7% |
| beam2 | 13,8% | 6,7% |
| beam4 | 12,1% | 6,7% |
| beam3 | 11,6% | 6,7% |
| beam5 | 7,2% | 6,7% |
| S | 7,0% | 6,7% |
| square2 | 6,3% | 6,7% |
| rect23 | 5,8% | 6,7% |
| T | 5,1% | 6,7% |
| square3 | 4,8% | 6,7% |
| corner5 | 4,6% | 6,7% |
| corner3 | 4,3% | 6,7% |
| 1x1 | 1,7% | 6,7% |
| diag2 | 1,4% | 6,7% |
| **diag3** | **0,2%** | 6,7% |

Kierunek jest jednoznaczny: apka **oszczędza graczowi przekątnych**, które
zostawiają dziury nie do zapełnienia. Symulator daje je w 13,3% dobrań, apka
w 1,6% — osiem razy częściej, i to jest najlepsze dotychczasowe wyjaśnienie tego,
że **nasza gra jest trudniejsza od prawdziwej**: ta sama zachłanna przeżywa na
oryginale 57, 78 i 132 postawienia, a w symulatorze średnio 34,9 (mediana 32).
Trzy partie niezależnie: p ≈ 1·10⁻⁵.

**Czego pomiar jeszcze nie rozstrzyga — i dlaczego generator zostaje nietknięty:**
to rozkład **brzegowy**, zmierzony przy planszach, jakie produkuje zachłanna.
Pytanie „czy apka podgląda planszę przy losowaniu" jest wciąż otwarte, a jeśli
podgląda, wagi brzegowe są złym modelem i przestrojenie trzeba by powtórzyć.
Rzadkie typy mają zresztą po 1–7 obserwacji. Przestrojenie generatora zrywa
porównywalność całego benchmarku ([#8](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/8)),
więc robi się je **raz**, właściwym modelem — decyzja właściciela z 2026-09-23.

**Model wybrany i wdrożony ([#38](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/38)).**
744 unikalne tacki z logów (`tools/analyze_generator.py`). Trzy modele: ślepe wagi (A),
wagi + filtr grywalności (B), wagi na kubełek zapełnienia (C). AIC: A 15900,8 · **B 15727,1** · C 15818,5.
Filtr sam tłumaczy zależność od planszy, więc C (56 parametrów) przegrywa z B (14) o ~90.
Filtr nie tłumaczy nadwyżki tacek z powtórzonym typem (obs. 37,0% vs 23,1% w B; trzy te same 29 vs 6),
więc dochodzi jeden parametr: klocek po pierwszym kopiuje poprzedni z p = 0,09 (→ 36–38%, trzy te same ~21).
`generator.py`: WAGI + POWTORZENIE + przelosowanie do skutku (sufit 200 prób). Pozostaje nierozstrzygnięte,
czy apka przelosowuje czy waży, oraz czy poza w obrębie typu jest równa.

**Grywalność tacki — zmierzone** ([#37](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/37)).
Polityka `fill` zapychała planszę (śr. 36 z 64 pól, maks. 49), dwa przebiegi po
200 ruchów, 399 z 400 ruchów zgodnych z odczytem, **żadnej przegranej partii**.
Gra dobrała 67 tacek. Przy ślepym losowaniu na tych samych planszach:

| poziom | obserwowane | oczekiwane (symulator / kształty z biegu) | P(≤ obs) |
|---|---|---|---|
| żywa: nic się nie mieści | **0** | 3,5 / 6,5 | 0,03 / 0,001 |
| cała: nie wejdą wszystkie trzy | **0** | 21,3 / 27,3 | 6·10⁻¹⁰ / 1·10⁻¹² |

**Apka gwarantuje, że tacka da się postawić w całości** (silniejsza gwarancja,
która obejmuje żywą). Trzeci składnik rozbieżności z #30, obok wag i tacki jako
jednostki losowania: generator musi mieć **filtr grywalności** — odrzucać albo
przelosowywać tacki, których trzech klocków nie da się postawić po kolei
(`playability.all_fit`). Zastrzeżenia: plansze sięgały 49 pól, nie wiemy, jak
apka zachowuje się przy 55+; mechanizm (przelosowanie czy ważenie) pozostaje
nierozstrzygnięty — odróżnia je tylko rozkład typów przy dużym zapełnieniu.
Odtworzenie: `POLICY=fill` w moście, `python tools/analyze_fill.py moves.jsonl`.

### Z-7 — czy w ogóle są punkty za samo postawienie

Symulator: tak, `liczba komórek klocka` (źródło A). Źródło B nie nalicza ich wcale.

**Pomiar:** postawić klocek bez czyszczenia i odczytać przyrost. Zero albo liczba
komórek. Ten sam ruch, który mierzy Z-3, mierzy i to.

### Z-8 — sufit przy ℓ ≥ 7

Symulator: brak sufitu, `B(ℓ)` rośnie dalej. Źródła się różnią.
Zdarzenie na tyle rzadkie, że nie ma priorytetu.

---

## Z-9 — ryzyko, które unieważnia wszystkie pomiary naraz

Autor źródła A ostrzega, że punktacja realnej apki **nie jest stacjonarna**:
różne mnożniki między bliskimi wersjami, różne reżimy punktacji po restarcie gry,
zmiany widoczne nawet w obrębie jednej partii. Mechanizm nieznany; możliwa
konfiguracja serwerowa albo testy A/B.

**Jeżeli to prawda, kalibracja pod „stałe oryginału" traci sens w obecnej formie,
bo stałych nie ma.**

**Wymaganie blokujące dla mostu (R10 z [#2](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/2)):**
powtórzyć pomiary bazowe Z-1, Z-2, Z-3, Z-7 w **trzech sesjach w trzech różnych dniach
na tej samej wersji apki**. Rozjazd liczb = punktacja konfigurowana serwerowo.
Most musi logować wersję apki i sprzęgać „ruch → przyrost wyniku" w jednym rekordzie
na postawienie, inaczej pomiary z różnych dni będą niespójne bez wyjaśnienia.

---

## Konsekwencje kalibracji, o których trzeba wiedzieć

**Szereg punktowy się urwał.** Kalibracja zmieniła kształt funkcji wyniku, więc liczby
sprzed niej są nieporównywalne z liczbami po. `training_stats*.csv` opisują inną grę.
Dokładnie dlatego benchmark ([#8](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/8))
raportuje **przeżycie** obok punktów: przeżycie nie zależy od wzoru punktacji i biegnie dalej.

**Zmierzone od nowa, tym symulatorem** (300 seedów, ε = 0, sufit 2000):

| polityka | średnia | mediana | p10 | przeżycie |
|---|---|---|---|---|
| losowa | 59,15 | 46,0 | 31,0 | 11,9 |
| zachłanna (1 pół-ruch) | 704,79 | 486,0 | 160,0 | 34,99 |

Sesja [#8](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/8) zmierzyła politykę
zachłanną na **365** — już wtedy wzorem referencyjnym, ale na **starej, 16-kształtowej puli**.
Różnica 365 → 705 nie pochodzi więc z punktacji, tylko z puli klocków i z mechaniki combo
(R-3, R-4, R-6, R-8). Wzrost nie oznacza, że bot gra lepiej — oznacza, że gra w inną grę,
w której pogoń za combo wreszcie się opłaca. **Każda liczba punktowa sprzed tej zmiany jest
nieporównywalna z każdą liczbą po niej.**

**Stare wagi przestały się ładować.** Belka 1×5 nie mieści się w kodowaniu 4×4, więc
wejście `piece_mlp` urosło z 16 do 25. Benchmark wykrywa to sam i kończy `blocked` —
zgodnie z [#21](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/21), gdzie
„wagi istnieją, ale nie da się ich załadować" jest wskazane jako najrealniejsze
zagrożenie dla szeregu pomiarowego. Wagi i tak byłyby martwe merytorycznie: były
trenowane pod inną funkcję nagrody.

**Wynik wchodzi do sieci w skali logarytmicznej.** `score` kumuluje się teraz przez całą
partię i przy celu 10 mln osiągnąłby wartości, które zdominowałyby pozostałe cechy
wejścia `numeric`. Stąd `log1p(score)`.
