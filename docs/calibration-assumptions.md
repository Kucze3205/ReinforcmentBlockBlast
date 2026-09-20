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

### Z-1 — punkt bazowy: 10 za linię czy 80 za linię *(rozstrzyga najtaniej)*

Symulator: `line_bonus(1) = 10`.
Sprzeczność między źródłami: 10 punktów za linię vs 10 za każdą **usuniętą komórkę**
(czyli 80 za linię). To ośmiokrotna różnica w całej skali punktowej.

**Pomiar:** postawić klocek czyszczący dokładnie **jedną** linię przy combo = 0
i odczytać przyrost wyniku. `10` albo `80` zamyka sprawę jednym ruchem.

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

### Z-4 — bonus za pustą planszę: 300 czy 360

Symulator: `FULL_CLEAR_BONUS = 300` (oba źródła referencyjne). Farma SEO podaje 360.

**Pomiar:** opróżnić planszę i odczytać przyrost. Rzadkie zdarzenie, więc pomiar
będzie kosztowny — ale wpływ na wynik jest mały, więc może poczekać.

### Z-5 — zbiór klocków: 41 poz *(największa niewiadoma)*

Symulator: 15 typów kanonicznych domkniętych na D4 → 41 orientacji, zgodnie ze
źródłem A. Klon BlockBlastPlay mówi o **34** kształtach we własnym buildzie.
Poprzednia pula repo miała 16 kształtów = 39% poz referencyjnych.

**Nikt publicznie nie zmierzył puli oryginału.** To nie jest spór między źródłami —
to wynik negatywny ([#2](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/2), §3.1).

**Pomiar:** most loguje każdą tackę. Po kilku tysiącach tacek zbiór unikalnych
kształtów jest zamknięty z dużą pewnością.

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
