# Przeszukanie z wyuczoną oceną w grach kaflowych: 2048, N-tuple, expectimax, MCTS

Badanie do [#94](../../issues/94). Pytanie: co w grach kaflowych ze stochastycznym dopływem
klocków dowozi krotności powyżej ręcznych cech + liniowych wag + płytkiego przeszukania — ile to
kosztuje na CPU, i **w jakiej proporcji** skok bierze się z uczonej oceny, a w jakiej z
głębszego przeszukania. **Nie proponuję wdrożenia** — to jest materiał dla orchestratora.

## Znaczniki

`[D]` — kod repo z Budżetu, przeczytany samodzielnie w całości. `[Z]` — twierdzenie z zewnątrz.
Tak jak w [`ocena-zaszumionych-kandydatow.md`](ocena-zaszumionych-kandydatow.md): **żadnego**
źródła zewnętrznego nie przeczytałem jako surowy PDF — narzędzie do PDF-ów w tej sesji zwracało
tylko strukturę binarną, nie tekst (próby: 2212.11087, 327912401 na ResearchGate — obie
nieudane). Wszystkie ustalenia zewnętrzne pochodzą albo z wyciągu HTML strony arXiv
(`arxiv.org/html/...`) przetworzonego przez narzędzie streszczające, albo z podsumowania
wyszukiwarki — **stąd `[Z]`, nie `[D]`, nawet gdy cytat wygląda jak dosłowny fragment artykułu**,
zgodnie z konwencją przyjętą w cytowanym raporcie #89. `[K]` — liczba, którą przeliczyłem sam z
podanych danych (arytmetyka jawna).

---

## 1. N-tuple networks + TD po stanach następczych (afterstate) w 2048

**Co to jest** `[Z]`: sieć n-tuple dzieli planszę na nakładające się "łaty" (tuples) po `k`
komórek; każda łata ma tablicę odnośnikową (LUT) o `c^k` wpisach (`c` = liczba możliwych wartości
kafla na komórce), indeksowaną bezpośrednio wzorcem wartości na tych komórkach. Suma wpisów ze
wszystkich łat to ocena stanu — funkcja **liniowa** względem tych binarnych/kategorycznych cech,
tak jak `features.py` u nas, tylko z cechami dobieranymi automatycznie (każda kombinacja wartości
na łacie to osobna waga) zamiast sześciu ręcznie zaprojektowanych cech. Trenowana metodą TD(0) na
**stanach następczych** (afterstate — stan planszy zaraz po ruchu gracza, przed dociągnięciem
losowego kafla), co eliminuje potrzebę modelowania rozkładu losowego dociągu w celu nauki
wartości. Źródło: Jaśkowski, *Mastering 2048 with Delayed Temporal Coherence Learning...*,
arXiv:1604.05085, wyciąg HTML: https://ar5iv.labs.arxiv.org/html/1604.05085. `[Z]`

**Co konkretnie kupuje — liczbami**:
- Sieć bazowa "3333-4242" (osiem łat po 4-6 komórek): `4×16⁶ = 67 108 864` wag. Sieć
  "421-4343": `5×16⁷ = 1 342 177 280` wag — **rząd wielkości miliardów parametrów liniowych**.
  `[Z]`
- Rozszerzenie "multi-stage" (osobny zestaw wag na etap gry) mnoży to przez `2⁴ = 16`. `[Z]`
- Wynik (ta sama praca, ten sam agent, różne budżety przeszukania na tej samej wyuczonej
  ocenie): **1-ply średnio 311 426 pkt**, **3-ply średnio 511 759 pkt** (+64% za dwa dodatkowe
  ply), przy limicie **1000 ms/ruch** (iteracyjne pogłębianie) **609 104 pkt** (+96% względem
  1-ply). `[Z]`
- Prędkość: **258 371 ruchów/s przy 1-ply**, **1464 ruchów/s przy 3-ply** — spadek o czynnik
  **~176×** za dwa dodatkowe ply. `[Z]`
- Trening: budżet **10¹⁰ akcji ≈ 10⁷ epizodów**. Pojedynczy przebieg treningu: **1-7 dni**
  w zależności od wariantu algorytmu; wariant "delayed-TC(0.5)" **0,39±0,01 dnia** vs standardowy
  TC **1,16±0,03 dnia**; najlepsza konfiguracja (z redundantnym kodowaniem) **5,47 dnia**.
  Równoległość bez blokad (lock-free) daje **24× przyspieszenie** treningu. `[Z]`

**Założenia**: (1) dostęp do stanu następczego (afterstate) przed dociągiem losowym — u 2048 to
tanie, bo ruch gracza jest deterministyczny i odwracalny w symulacji; (2) plansza da się pokryć
niewielką liczbą małych, nakładających się łat tak, by suma ich LUT-ów miała sens jako
przybliżenie wartości — działa dla 4×4, bo `c^k` przy `k≤7`, `c≈16` jest jeszcze policzalne w
pamięci (rząd `10⁷`-`10⁹` wpisów). `[Z]`

**Kiedy zawodzi**: (a) przy większej planszy albo większym `c` (więcej możliwych wartości kafla)
`c^k` rośnie wykładniczo — u nas `c` to liczba stanów pojedynczej komórki (2: pusta/zajęta w
najprostszym ujęciu, ale patrz sekcja "Co się przenosi"), więc formuła sama w sobie nie zawodzi
liczbowo, tylko **liczba potrzebnych łat**, żeby pokryć planszę 8×8 zamiast 4×4, rośnie — to jest
wniosek strukturalny, nie zmierzony, patrz "Czego nie wiem"; (b) trening wymaga milionów
epizodów (10⁷) — przy naszym budżecie dziesiątek minut CPU i przepustowości symulatora
(nieznana mi z tego zadania — poza budżetem) to może być nieosiągalne bez drastycznego
skrócenia. `[Z]`+`[K]` (wniosek z rzędów wielkości, nie z pomiaru u nas).

---

## 2. Expectimax z węzłami losowymi i jego skalowanie z głębokością

**Co to jest** `[Z]`: drzewo przeszukania na przemian z węzłami MAX (ruch gracza) i węzłami CHANCE
(losowy dociąg kafla, wartość = suma po możliwych dociągach ważona ich prawdopodobieństwem).
W 2048 chance node ma rozgałęzienie rzędu **liczby pustych pól × liczby możliwych wartości nowego
kafla (zwykle 2: "2" z p=0,9, "4" z p=0,1)** — koszt eksploracji rośnie wykładniczo z głębokością,
bo każdy MAX-ply dodaje mnożnik przez rozgałęzienie chance node. Źródło (ewaluacja handcrafted +
expectimax, bez uczenia): https://github.com/EndlessReform/macroxue-expectimax-2048. `[Z]`

**Co konkretnie kupuje — liczbami** (ocena **ręczna**, nieuczona; sprzęt: Intel Xeon 2,3 GHz):

| głębokość (ply) | czas/ruch | ruchy/s | pamięć | śr. wynik (1000 gier) | 32768 | 65536 |
|---|---|---|---|---|---|---|
| 5 | 3 s | 6461 | 5 GB | 660 650 | 74,8% | 2,7% |
| 8 | 1453 s | 17 | 27 GB | 711 769 | 80,5% | 3,5% |

`[Z]`, tamto źródło. **Wniosek z tabeli** `[K]`: pogłębienie 5→8 ply przy **stałej, ręcznej**
ocenie kupuje tylko **×1,077** wyniku, za cenę **~484× więcej czasu na ruch** i **~5,4× więcej
pamięci** — silnie malejące zwroty z samego przeszukania, gdy ocena liści się nie zmienia.

**Założenia**: (1) rozkład dociągu jest znany i mały (2 wartości kafla) — u nas rozkład tacki to
~15 kanonicznych kształtów `[D]` (patrz `kierunek-algorytmiczny.md`, Z-5), **rząd wielkości
większy** niż w 2048, więc chance node u nas byłby drożej rozgałęziony na jednostkę głębi; (2) da
się przycinać drzewo (transpozycje, symetrie) — 2048 ma silne symetrie planszy (obrót/odbicie),
które redukują liczbę unikalnych stanów do rozpatrzenia. `[Z]`

**Kiedy zawodzi**: (a) koszt rośnie wykładniczo z głębokością i rozgałęzieniem chance node —
tabela wyżej pokazuje to wprost (484× czasu za 3 dodatkowe ply); (b) zwroty maleją szybciej niż
koszt rośnie, gdy ocena liści jest słaba (tabela wyżej: ocena ręczna, +7,7% za 484× czasu) —
przeciwieństwo tego, co dzieje się, gdy poprawia się ocenę zamiast głębi (sekcja 3 i 4). `[Z]`+`[K]`.

---

## 3. MCTS z węzłami losowymi (gry jednoosobowe ze stochastyką)

**Co to jest** `[Z]`: standardowy MCTS rozszerzony o węzły losowe — w fazie selekcji węzeł MAX
wybiera dziecko przez UCB, węzeł CHANCE próbkuje dziecko zgodnie z rozkładem prawdopodobieństwa
(zamiast rozwijać wszystkie możliwości jak expectimax). Źródło ogólnego mechanizmu:
https://arxiv.org/html/1907.06508 (General Board Game Playing, sekcja o MCTS dla 2048). `[Z]`

**Co konkretnie kupuje — liczbami**, ten sam artykuł, tabela III/IV (50 gier ewaluacyjnych,
ten sam symulator dla wszystkich wierszy):

| metoda | śr. wynik | ruchy/s |
|---|---|---|
| MCTS (czysty, bez uczonej oceny) | 34 700 ± 4 100 | — |
| MC (Monte Carlo, bez drzewa) | 51 500 ± 6 300 | — |
| MCTS-Expectimax (MCTSE, hybryda) | 57 000 ± 6 400 | — |
| TD-n-tuple, **0-ply** (sama uczona ocena, brak przeszukania) | 131 000 ± 8 800 | 94 000 |
| TD-n-tuple, 2-ply | 174 000 ± 6 600 | 5 000 |
| TD-n-tuple, 4-ply | 196 000 ± 6 500 | — |

`[Z]`, https://arxiv.org/html/1907.06508 (wynik TD-n-tuple w tej pracy — po **200 000** gier
treningowych, dużo mniej niż 10⁷ epizodów w sekcji 1 — to inny, słabiej wytrenowany agent, więc
liczby 131k/174k/196k **nie są bezpośrednio porównywalne** z 311k/511k/609k z sekcji 1;
porównywalne są **wewnątrz tej samej tabeli**, bo ten sam sprzęt/protokół).

**Co dokładnie mówi ta tabela o pytaniu z issue** `[K]`: **czysty MCTS bez uczonej oceny
(34 700-57 000) przegrywa nawet z uczoną oceną bez żadnego przeszukania (131 000, 0-ply)** —
czynnik **×2,3 do ×3,8** na korzyść samej oceny. Dopiero potem przeszukanie na tej ocenie dokłada
dalej: 0-ply→4-ply to ×1,50. Cytat wprost o przyczynie słabości czystego MCTS: „all further
simulations will start from that state, and this leads to a severely limited exploration of the
game tree" `[Z]`.

**Założenia**: (1) MCTS potrzebuje funkcji rolloutu albo oceny liścia — czysty MCTS bez uczonej
oceny (jak w tabeli) używa losowych rolloutów, stąd słaby wynik; (2) w grach o dużym
rozgałęzieniu na turę (patrz `kierunek-algorytmiczny.md`, Tetris Link ~162) czyste próbkowanie
MCTS `[H]` (już ustalone w tamtym raporcie, cytowane stamtąd) traci sens powyżej progu
rozgałęzienia rzędu kilkudziesięciu.

**Kiedy zawodzi**: (a) MCTS bez silnego naprowadzania (oceny albo polityki) jest słaby właśnie w
grach z dużym rozgałęzieniem i płytką, informatywną strukturą nagrody — 2048 to potwierdza
liczbowo (tabela wyżej), Tetris Link to potwierdza jakościowo `[H]` (już w
`kierunek-algorytmiczny.md`); (b) hybrydy MCTS+expectimax (MCTSE) łagodzą to częściowo (2× lepiej
niż czysty MCTS: 57 000 vs 34 700 wg jednego eksperymentu w tej samej tabeli — źródło nie podaje
p-wartości tej różnicy), ale wciąż nie dorównują nawet oceny bez przeszukania. `[Z]`

---

## 4. Czwarta rodzina: naprowadzanie przeszukania siecią (policy/value w stylu AlphaZero)

Wybrana jako czwarta rodzina, bo bezpośrednio odpowiada na pytanie kryteriów akceptacji o
przycinanie wiązki uczoną oceną.

**Co to jest** `[Z]`: sieć polityki (policy) zawęża rozgałęzienie w węźle MAX do kilku
najbardziej obiecujących ruchów (redukcja *szerokości*), sieć wartości (value) zastępuje losowe
rollouty jako ocena liścia (redukcja *głębokości* potrzebnej do oszacowania wartości) — obie
zastosowane po raz pierwszy razem w AlphaGo (Silver i in. 2016), potem AlphaGo Zero. Źródło:
https://www.emergentmind.com/topics/alphazero-based-system. `[Z]`

**Co dokładnie kupuje**: literatura o AlphaZero (Go/Szachy/Shogi) potwierdza ten podział ról
jakościowo, ale **żadne ze znalezionych źródeł nie podaje liczbowego rozbicia zysku między
"węższa polityka" a "lepsza ocena liścia" w osobności** — to jest dokładnie ten sam typ pytania,
co pytanie główne issue (×4,89 vs ×1,21), tylko dla innej architektury, i literatura go tu nie
rozstrzyga liczbowo w znalezionych źródłach. `[Z]`

**Założenia i kiedy zawodzi**: wymaga sieci polityki wyuczonej niezależnie od (lub wspólnie z)
oceną wartości — dodatkowy koszt treningu i architektury, którego żadna z rodzin 1-3 nie wymaga
(N-tuple TD i expectimax handcrafted używają tylko oceny wartości/stanu, nie polityki). Nie
znalazłem źródła opisującego to zastosowane wprost do gry z tacką/dopływem klocków (2048,
1010!, Block Blast) — luka, patrz "Czego nie wiem".

---

## Jak te wyniki rozkładają się między ocenę a przeszukanie

To jest odpowiednik naszego ×4,89 (przeszukanie tacki, bez strojenia) / ×1,21 (strojenie wag CEM
na wierzchu przeszukania) z [#87](../../issues/87) — najważniejsza sekcja raportu.

**W 2048, w obrębie jednej, spójnej tabeli (sekcja 3, ten sam protokół, ten sam sprzęt)**
`[Z]`+`[K]`:
- **Ocena sama, bez przeszukania (0-ply TD-n-tuple) → best MCTS bez uczonej oceny**: ×2,3-3,8
  na korzyść samej oceny (131 000 vs 34 700-57 000).
- **Przeszukanie na wierzchu tej samej uczonej oceny (0-ply → 4-ply)**: ×1,50 (131 000 → 196 000).

**Wniosek liczbowy** `[K]`: w tej konkretnej tabeli **ocena kupuje więcej niż przeszukanie** —
odwrotna proporcja niż u nas w #87, gdzie przeszukanie (×4,89) zdecydowanie zdominowało strojenie
oceny (×1,21). Ale to porównanie ma dwie istotne zastrzeżenia:
1. **Punkt odniesienia jest inny.** U nas bazą jest "ręczne cechy, bez przeszukania" (762,5).
   W 2048 najbliższym analogiem bazy byłby "MCTS bez uczonej oceny" (34 700-57 000) — a MCTS to
   nie jest to samo co "ręczna ocena bez przeszukania" (to jest przeszukanie *z* domyślnym,
   nieuczonym rolloutem, nie ocena statyczna). Nie znalazłem w tej samej tabeli wyniku
   "ocena ręczna (bez sieci), 0-ply" dla 2048, więc nie da się odtworzyć dokładnie tej samej
   struktury porównania (ręczna-ocena-bez-przeszukania jako wspólny mianownik) z jednego źródła.
2. **Druga tabela (sekcja 2, macroxue), z ręczną oceną i głębokim expectimax**, pokazuje
   coś przeciwnego jakościowo do sekcji 3: pogłębienie 5→8 ply na *stałej* ręcznej ocenie kupuje
   tylko ×1,077 — czyli gdy ocena jest ustalona i nieuczona, przeszukanie ma bardzo malejące
   zwroty, zgodnie z intuicją z #87 (przeszukanie działa najlepiej, gdy jest *czym* rozróżniać
   kandydatów, czyli gdy ocena już coś sensownego mówi).

**Synteza (własny wniosek z połączenia trzech źródeł, nie jednego)** `[K]`: obraz z literatury
2048 jest spójny z ideą, że **oba dźwignie działają, ale nie zamiennie** — ocena (uczona lub
ręczna) ustala, "jak dobre jest patrzenie głębiej", a głębokość mnoży to, co ocena już widzi.
Ilość, o jaką każda z dźwigni pomaga, zależy silnie od tego, jak dobra jest *druga* dźwignia w
danym momencie — dokładnie ten sam wzorzec jakościowy, co obserwacja z #87 (przeszukanie kupiło
dużo, bo baza — ręczna ocena bez przeszukania — była daleka od optymalnej; strojenie kupiło mało
na wierzchu przeszukania, bo przeszukanie już częściowo kompensowało słabe wagi). **Nie znalazłem
źródła, które rozkłada to na czynniki liczbowo tak precyzyjnie jak nasze #87** (jedna spójna
tabela z trzema porównywalnymi punktami: bez-przeszukania/z-przeszukaniem/z-przeszukaniem-i-
strojeniem) — to jest luka, patrz "Czego nie wiem".

---

## Co się przenosi na naszą grę

- **Trzy klocki naraz (przestrzeń akcji jako iloczyn trzech ustawień)**: **łamie założenie**
  wprost. N-tuple TD i expectimax w 2048 rozgałęziają węzeł MAX na **4** ruchy (kierunki) —
  tanie do wyliczenia w pełni za każdym razem. U nas rozgałęzienie *w obrębie jednej znanej
  tacki* to iloczyn 3 klocków × legalne pozycje każdego na planszy 8×8 — strukturalnie bliższe
  branching factor Tetris Link (~162/turę, `[H]`, już ustalone w `kierunek-algorytmiczny.md`) niż
  4 ruchom 2048. Podejście "policz ocenę dla każdego z 4 dzieci" (rdzeń TD-n-tuple 0-ply i
  expectimax MAX-node w 2048) nie skaluje się wprost na setki kandydatów bez własnej redukcji
  (przycinanie/wiązka) — czego 2048 nie musiało robić na poziomie pojedynczego ruchu.
- **Plansza 8×8 zamiast 4×4**: **łamie założenie częściowo**. Formuła rozmiaru LUT-u `c^k` na
  łatę (sekcja 1) nie zależy od rozmiaru planszy wprost, ale **liczba łat potrzebnych do pokrycia
  planszy** rośnie z jej powierzchnią (64 komórki vs 16) — konkretne wzorce łat z artykułu
  Jaśkowskiego (4-6 komórek, dobrane pod 4×4) nie przenoszą się jako gotowe współrzędne; wymagałyby
  przeprojektowania. To jest wniosek strukturalny z samej definicji metody, nie zmierzony. `[K]`
- **Usuwanie całych linii zamiast łączenia kafli**: **łamie założenie oceny, nie metody**.
  N-tuple/TD i handcrafted-eval-expectimax to metody ogólne (liniowa funkcja cech state
  → wartość, trenowana/dostrajana pod dowolny sygnał nagrody) — mechanizm uczenia się przenosi,
  ale konkretne wagi i konkretne cechy (np. "eroded piece cells" z Dellacherie-Thiery, cytowane w
  `kierunek-algorytmiczny.md`) są specyficzne dla mechaniki łączenia/przesuwania kafli i nie mają
  odpowiednika przy usuwaniu linii. `features.py` u nas już zastępuje je własnymi cechami
  (`near_full_lines`, `largest_empty_rect` itd.) dobranymi pod tę mechanikę — to pokazuje, że
  ten problem jest już rozwiązany na poziomie *doboru cech*, niezależnie od tego, czy oceną
  pozostaną cechy ręczne czy N-tuple.
- **Stan losowy częściowo jawny (tacka znana na 3 ruchy, kolejna losowana dopiero po
  wyczerpaniu)**: **to jest różnica strukturalna korzystna dla nas, nie przeszkoda**. W 2048
  chance node pojawia się **po każdym pojedynczym ruchu** — każdy ply w głąb wymaga rozpatrzenia
  rozkładu losowego. U nas, zgodnie z ustaleniem z `kierunek-algorytmiczny.md` (`[H]`, przeczytany
  kod `game.py`), przeszukanie *w obrębie* bieżącej, w pełni znanej tacki jest **deterministyczne
  i skończone — bez żadnego węzła losowego przez 3 pełne plye**, a węzeł losowy pojawia się
  dopiero na granicy tacki. To odwraca ekonomię kosztu względem 2048: u nas "głębokie
  przeszukanie" (do 3 ply) jest tanie strukturalnie (brak chance node), a to, co jest drogie
  w 2048 na każdym kroku (chance node), u nas jest drogie tylko raz na 3 ruchy — więc wyniki o
  koszcie chance node z sekcji 2 (rozgałęzienie ~15 kształtów tacki, `[D]` z Z-5) **nie
  przenoszą się wprost jako "koszt na ply"**, tylko jako "koszt na granicę tacki", co jest
  rzadszym zdarzeniem niż w 2048.

---

## Czy da się zrobić naprowadzanie przeszukiwania (uczona ocena do przycinania wiązki)

**Literatura nie rozstrzyga tego wprost dla tej rodziny gier.** Znalazłem tylko:
- Ogólny wzorzec AlphaZero (sekcja 4): sieć wartości zastępuje rollout jako ocena liścia (to
  jest to, co już robimy — `TrayPolicy` liczy `features()` na kandydatach, nie robi rolloutów),
  sieć polityki zawęża *szerokość* rozgałęzienia — ale to wymaga osobnej sieci polityki, której
  żadna z rodzin 1-3 (N-tuple TD, expectimax, MCTS-w-2048) nie używa w cytowanych źródłach; N-tuple
  TD w 2048 nie przycina wiązki, bo nie musi — rozgałęzienie MAX-node to zawsze 4.
- Żadne z cytowanych źródeł o 2048/Tetris Link/Hex (patrz `kierunek-algorytmiczny.md`) nie
  testuje wprost "ta sama uczona ocena użyta do przycinania wiązki kandydatów zamiast do wyboru
  ruchu na końcu drzewa" — to jest inne zastosowanie tej samej funkcji (ranking do odsiania
  kandydatów *przed* pełną ewaluacją, a nie ocena liścia *po* pełnym rozwinięciu). Nie znalazłem
  źródła, które mierzy to rozróżnienie liczbowo w grze z dużym rozgałęzieniem na turę i tanią
  oceną kandydata (nasza sytuacja: `TrayPolicy` już i tak ocenia **wszystkich** kandydatów
  wiązką 8 — pytanie "przycinać uczoną oceną *przed* pełnym rozwinięciem" ma sens tylko, gdy
  rozwinięcie samo jest drogie, co u nas jeszcze nie jest ustalone jako wąskie gardło).

---

## Cytaty

> "Scores are averaged over 50 evaluation games. The results with TD-n-tuple were obtained after
> 200.000 training games."
Źródło: https://arxiv.org/html/1907.06508

> "all further simulations will start from that state, and this leads to a severely limited
> exploration of the game tree"
Źródło: https://arxiv.org/html/1907.06508

> "MCTS-Expectimax is twice as good as MCTS."
Źródło: https://arxiv.org/html/1907.06508

> Sieć "3333-4242": "4×16⁶=67,108,864 parameters"; sieć "421-4343": "5×16⁷=1,342,177,280
> weights".
Źródło: https://ar5iv.labs.arxiv.org/html/1604.05085

> "single 2048 learning run takes, depending on the algorithm, 1–7 days to complete";
> "delayed-TC(0.5) required 0.39±0.01 days versus 1.16±0.03 for standard TC".
Źródło: https://ar5iv.labs.arxiv.org/html/1604.05085

> "lock-free optimistic parallelism, reducing the learning time by a factor of 24".
Źródło: https://ar5iv.labs.arxiv.org/html/1604.05085

> Expectimax, ocena ręczna, depth 5 vs depth 8: czas/ruch "3 seconds" → "1453 seconds", średni
> wynik "660,650" → "711,769" (1000 gier, maj 2022).
Źródło: https://github.com/EndlessReform/macroxue-expectimax-2048/blob/master/README.md

> Sprzęt: "Intel Xeon 2.3GHz CPUs", pamięć "5GB minimum for small runs, 27GB for large runs".
Źródło: https://github.com/EndlessReform/macroxue-expectimax-2048/blob/master/README.md

> "A policy network narrows down move selection... a value network helps with leaf evaluation,
> reducing the number of costly rollouts."
Źródło: https://www.emergentmind.com/topics/alphazero-based-system

---

## Czego nie wiem

- **Czy istnieje jedna, spójna publikacja (ten sam protokół, sprzęt, budżet treningu) łącząca
  wszystkie trzy punkty na jednej skali dla 2048: (a) ręczna ocena bez przeszukania, (b) ta sama
  ocena + przeszukanie, (c) uczona ocena + to samo przeszukanie** — dokładny odpowiednik naszej
  tabeli z #87 (762,5 → 3727,0 → 4510,24). Nie znalazłem takiej pojedynczej tabeli — złożyłem
  obraz proporcji z **dwóch różnych** prac (sekcja 3: ocena vs MCTS; sekcja 2: głębokość na
  stałej ocenie ręcznej), co jest słabszym dowodem niż jedna spójna tabela. To jest liczba, która
  rozstrzygnęłaby sprawę wprost, gdyby istniała.
- **Realny branching factor naszej gry** (3 klocki bez rotacji × legalne pozycje na planszy 8×8)
  — nie zmierzony w tym zadaniu (poza budżetem, nie uruchamiałem symulatora); bez niego
  porównanie z progiem rozgałęzienia z Hex/Tetris Link (`kierunek-algorytmiczny.md`) jest tylko
  strukturalną hipotezą.
- **Czy przepustowość naszego symulatora** (nieznana mi w tym zadaniu — poza budżetem) jest
  wystarczająca, by choćby ułamek 10⁷ epizodów treningu N-tuple TD (sekcja 1) zmieścił się w
  dziesiątkach minut CPU. Bez tej liczby nie da się ocenić, czy pełne podejście N-tuple/TD jest
  w ogóle wykonalne u nas, czy tylko jego mniejsza wersja (mniej/mniejsze łaty, krótszy trening).
- **Ile realnie kosztowałby węzeł losowy na granicy naszej tacki** (rozgałęzienie ~15 kanonicznych
  kształtów, `[D]` z Z-5 w `docs/calibration-assumptions.md`) w praktyce przeszukania jedną
  tackę głębiej — nie zmierzone, tylko oszacowane jako "rząd wielkości większe niż w 2048"
  (2 wartości kafla) w sekcji 2.
- **Czy rozkład losowania kolejnej tacki zależy od stanu planszy** — `docs/calibration-
  assumptions.md` (Z-6, już zaznaczone w `kierunek-algorytmiczny.md`) to otwarte pytanie, istotne
  dla tego, czy formalizm expectimax (który zakłada rozkład niezależny od historii) w ogóle
  stosuje się wprost do węzła losowego na granicy naszej tacki.
- **Dokładny wzorzec łat (tuples) dobrany pod planszę 8×8 z usuwaniem linii** — nie znalazłem
  żadnej publikacji, która projektuje N-tuple network dla gry z mechaniką usuwania linii (zamiast
  łączenia); to, co napisałem w "Co się przenosi", jest wnioskiem strukturalnym z definicji
  metody, nie z istniejącej implementacji.
- **Liczbowe rozbicie zysku z naprowadzania przeszukania (policy narrowing) na "szerokość" vs
  "głębokość"** dla żadnej gry z tej rodziny — nie znalazłem źródła mierzącego to osobno, ani
  dla 2048, ani dla gry z tackową mechaniką.
- **Pełna treść pierwotnych źródeł** (Jaśkowski arXiv:1604.05085, GBG arXiv:1907.06508,
  Karnin/Jamieson/Hyperband nie dotyczą tego zadania) — czytałem wyłącznie wyciągi HTML
  przetworzone przez narzędzie streszczające, nie oryginalny PDF/tekst w całości.

**Czy odpowiedziałem na pytanie z issue**: częściowo. Opisałem trzy obowiązkowe rodziny
(N-tuple/afterstate TD, expectimax z węzłami losowymi, MCTS z węzłami losowymi) plus czwartą
(naprowadzanie w stylu AlphaZero), każdą z liczbami kosztu CPU/pamięci/treningu z linkami. Dla
pytania **najważniejszego** (proporcja ocena/przeszukanie) znalazłem liczby wystarczające, by
pokazać **kierunek** (w jednej tabeli 2048 ocena bez przeszukania biła przeszukanie bez uczonej
oceny o ×2,3-3,8, a przeszukanie na wierzchu uczonej oceny dokładało dalej ×1,5) i wprost
napisałem, że **nie znalazłem jednej publikacji z tak czystym rozbiciem trzech punktów, jak nasze
#87** — złożyłem to z dwóch osobnych źródeł, co jest wnioskiem słabszym niż jedna spójna tabela.
Sekcję "Co się przenosi" i sekcję o naprowadzaniu przeszukania napisałem wprost wskazując, które
założenia 2048 łamie nasza gra (przestrzeń akcji, rozmiar planszy) i które odwracają się na naszą
korzyść (częściowo jawny stan losowy, tania głębia w obrębie znanej tacki) — ale bez pomiaru
branching factor i przepustowości symulatora u nas, część wniosków zostaje hipotezą strukturalną,
nie liczbą.
