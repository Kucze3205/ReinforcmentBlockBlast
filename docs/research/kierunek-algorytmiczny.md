# Kierunek algorytmiczny: przeszukiwanie czy uczenie

Badanie do [#54](../../issues/54). Pytanie: jakie podejście algorytmiczne (przeszukiwanie
z heurystyką, RL, ewolucja wag) ma sens dla gry 8×8 z tacką trzech klocków, biorąc pod uwagę,
że musi się to liczyć na zwykłym runnerze GitHub Actions, bez GPU, w jobie o ograniczonym czasie.
**Decyzji o kierunku ten dokument nie podejmuje** — to jest materiał do decyzji, którą podejmie
orchestrator.

## Znaczniki mocy

Zgodnie z kryteriami akceptacji issue: `[H]` — ustalenie oparte na źródle pierwotnym, które
przeczytałem samodzielnie w całości (kod repo z Budżetu, artykuł naukowy pobrany i przeczytany
jako PDF, oficjalna dokumentacja). `[Z]` — twierdzenie, którego nie zweryfikowałem samodzielnie
(blog, README repo, streszczenie wyszukiwarki) — zawsze z linkiem i jednym zdaniem o tym, czego
źródło dotyczy.

Z Budżetu przeczytałem: `policies.py`, `game.py`, `docs/calibration-assumptions.md`. Nie
przeglądałem innych plików repo.

---

## (a) Co ludzie faktycznie uruchamiają na tej rodzinie gier

### Klasyczny Tetris (spadające klocki, gra kończy się na wysokości planszy)

Rodzina wyników jest dobrze udokumentowana, bo Tetris był poligonem ADP/RL od lat 90.

| metoda | wynik (linie) | koszt obliczeniowy | źródło |
|---|---|---|---|
| Dellacherie, 6 cech, wagi ręczne, **brak uczenia, brak przeszukiwania w czasie gry (1-ply)** | ~5 000 000 | zero treningu; ewaluacja 1-ply jest tania (rząd µs–ms na ruch) | `[H]` — przywołane w treści artykułu NeurIPS 2013 poniżej |
| Bertsekas/Tsitsiklis, wartość aproksymowana, 2 cechy | 30–40 | mały (lata 90., pojedyncza maszyna) | `[H]` (cytowane w tym samym artykule) |
| CE (cross-entropy) z cechami Dellacherie-Thiery (9 cech) | ~35 000 000 (duża plansza 10×20) | **65 000 000 próbek/iterację** (mała plansza), zbieżność po ~8 iteracjach przy dużej planszy = **1 700 000 000 wywołań generatora gry** do zbieżności | `[H]` — Gabillon, Ghavamzadeh, Scherrer, *Approximate Dynamic Programming Finally Performs Well in the Game of Tetris*, NeurIPS 2013, przeczytany PDF: https://mohammadghavamzadeh.github.io/PUBLICATIONS/nips13-tetris.pdf |
| CBMPI (ADP w przestrzeni polityk) z tymi samymi cechami | **51 000 000** (rekord w artykule, duża plansza) | **256 000 000 próbek** do zbieżności (~1/6 tego co CE) | `[H]`, to samo źródło |
| DQN / C51 / PPO na Atari Tetris (obraz z ekranu, nie stan planszy) | heurystyka wygrywa konsekwentnie z każdą z tych metod, tak wynikiem jak i kosztem | artykuł stwierdza wprost, że nowoczesne metody RL „struggle to master Tetris within reasonable computational limits”; nie miałem dostępu do pełnego tekstu z dokładną liczbą klatek/GPU-godzin | `[Z]` — Expert Systems with Applications 2025, tylko abstrakt/streszczenie: https://www.sciencedirect.com/science/article/pii/S0957417425008735 |

**Ocena wykonalności na Actions bez GPU:** Dellacherie (1-ply, wagi gotowe) jest trywialnie
wykonalny — to czysta heurystyka, zero treningu. CE i CBMPI **nie wymagają GPU** (cechy liniowe,
regresja/CMA-ES), ale wymagają setek milionów do ~2 miliardów wywołań symulatora gry — rząd
wielkości porównywalny do własnego pomiaru repo z #40: symulator bez sieci robi ~10 000 kroków/s
`[H]` (liczba z treści issue #54, zmierzona w #40, nie przeze mnie). Przy tym tempie 256 000 000
próbek CBMPI to ~7 CPU-godzin, a 1 700 000 000 próbek CE to ~47 CPU-godzin — **rzędu wielkości
mieszczącego się w limicie pojedynczego joba Actions (6 h) tylko dla CBMPI, a dla CE już nie**,
pod warunkiem że symulator naszej gry ma podobną przepustowość do symulatora Tetrisa z artykułu
(**tego nie zmierzyłem — to ekstrapolacja, nie pomiar**, bo Tetris i nasza gra różnią się
przestrzenią akcji i kosztem sprawdzenia planszy). Trening samą metodą CE/CBMPI dałoby się
też podzielić na wiele krótszych jobów równoległych (macierz Actions), co zmienia rachunek.

### Genetic algorithm na klasycznym Tetrisie (niezależne źródło, prostsze cechy)

4 cechy (wysokość zagregowana, liczba linii, dziury, nierówność), wagi z algorytmu genetycznego:
populacja 1000, 100 gier/ocenę, ~2 tygodnie działania, wynik 2 183 277 wyczyszczonych linii.
`[Z]` — blog Code My Road, nie podaje sprzętu ani czy równolegle:
https://codemyroad.wordpress.com/2013/04/14/tetris-ai-the-near-perfect-player/
**Ocena wykonalności:** 2 tygodnie ciągłego działania nie mieści się w pojedynczym jobie Actions;
wymagałoby rozbicia na wiele krótkich jobów albo istotnego przyspieszenia oceny.

### Tetris Link (planszowa odmiana, inna mechanika punktacji — łączenie grup, nie linie)

Branching factor do 162 ruchów/turę (bez rotacji klocka to i tak dużo, bo orientacje + pozycje).
Wyniki turnieju: **heurystyka (ręcznie dostrojona) wygrywa ze wszystkim** — z MCTS (nawet
zoptymalizowanym, RAVE/PoolRAVE) i z RL (PPO2, self-play). MCTS z losowymi rolloutami przy 12
wątkach odwiedza **16 258 węzłów/s** na CPU (Rust), ale przegrywa 0% z dostrojoną heurystyką —
zbyt mało trafień na drzewo o takim rozgałęzieniu bez silnego naprowadzania. MCTS naprowadzane
samą heurystyką odwiedza tylko **10 węzłów/s** (za wolno, by było praktyczne). RL (PPO2)
trenowane self-play osiąga lokalne optimum po ~1,5 mln kroków i potem się pogarsza; wygrywa
z losowym MCTS, przegrywa z każdą heurystyką. Osobny eksperyment na Hex pokazuje próg: MCTS
wygrywa do 90% przy rozgałęzieniu <49, i spada do ~0% gdy rozgałęzienie rośnie.
`[H]` — Müller-Brockhausen, Preuss, Plaat, *A New Challenge: Approaching Tetris Link with AI*,
arXiv:2004.00377, przeczytany PDF w całości.
**Ocena wykonalności:** cała eksploracja (heurystyka, MCTS, RL) była zrobiona na zwykłym CPU
(implementacja w Rust dla szybkości, JS do wizualizacji) — nic tu nie wymagało GPU ani klastra;
trening RL to rząd 1,5–3,6 mln kroków, więc prawdopodobnie godziny, nie dni, choć artykuł nie
podaje wallclock wprost.

### 1010! i Block Blast (nasza rodzina: siatka, tacka klocków bez spadania, brak rotacji)

Brak literatury naukowej — wyłącznie repozytoria hobbystyczne, żadne nie publikuje
zmierzonych wyników w formie porównywalnej z artykułami akademickimi:

| repo | podejście | wynik podany w README |
|---|---|---|
| `punoqun/1010-` | MCTS + własne heurystyki | brak liczb, brak opisu budżetu przeszukiwania `[Z]` https://github.com/punoqun/1010- |
| `radmin1337/Block-Blast-Solver` | DFS + heurystyka | brak liczb `[Z]` https://github.com/radmin1337/Block-Blast-Solver |
| `JacksonW98/block-blast-bot` | pełne przeszukanie permutacji 3 klocków (6 kolejności) + heurystyka (combo, miejsce, bliskość czyszczenia linii), planowanie tylko w obrębie bieżącej tacki | brak liczb `[Z]` https://github.com/JacksonW98/block-blast-bot |
| `rshk941/block-blast-solver` | wyczerpujące przeszukanie bieżącej tacki (permutacje × pozycje) + wyuczona sieć wartości (MLP 128-128-1, TD z target network) | autor wprost: „does not yet reliably outperform a skilled human player” `[Z]` https://github.com/rshk941/block-blast-solver |
| `snickrscodes/Block-Blast-AI` | sieć policy/value (PyTorch) + beam search naprowadzany polityką, silnik bitboard w C++ | brak liczb w README `[Z]` https://github.com/snickrscodes/Block-Blast-AI |
| `Botkraker/block-blast-AI`, `RisticDjordje/BlockBlast-Game-AI-Agent` | PPO / DQN / DQN+action masking | brak liczb `[Z]` |

**Ustalenie, nie ocena:** żadne z tych źródeł nie publikuje wyniku w formie, którą dałoby się
odnieść do linii bazowej tego repo (`docs/calibration-assumptions.md`: zachłanna = 704,79 średnio,
300 seedów, ε=0). To jest luka, nie brak chęci szukania — po prostu nikt publicznie tego nie
zmierzył w porównywalny sposób. Cechą wspólną wszystkich silniejszych podejść w tej rodzinie
(`JacksonW98`, `rshk941`) jest **wyczerpujące przeszukanie bieżącej tacki** (permutacje
3 klocków × pozycje) — to się różni od przeszukiwania "w głąb" po turach, patrz (b).

---

## (b) Ile w przód opłaca się patrzeć

### Rozróżnienie kluczowe dla tego pytania

Trzeba rozdzielić dwa różne sensy słowa „głębiej”:

1. **W obrębie znanej tacki** (u nas: 3 klocki widoczne naraz, bez losowości). To jest
   przeszukiwanie deterministyczne i skończone — bez węzłów losowych. `game.py:92-94` pokazuje,
   że tacka jest dobierana na nowo dopiero gdy `round_placement == 3`, czyli **wszystkie trzy
   miejsca w tacce są znane jednocześnie, zanim trzeba zagrać którekolwiek** `[H]` (przeczytany
   kod). To odpowiada temu, co robią `JacksonW98/block-blast-bot` i `rshk941/block-blast-solver`
   (przeszukanie 6 permutacji × pozycje) — koszt jest z góry ograniczony i nie rośnie z głębokością
   gry, bo nie ma tu żadnej niepewności do rozstrzygnięcia.

2. **Poza bieżącą tacką, w kolejną** — a kolejna tacka jest losowana i **nieznana aż do
   wyczerpania obecnej** `[H]` (kod: `self.pieces = self.generator.next_pieces()` wykonuje się
   dopiero po trzecim postawieniu). `docs/calibration-assumptions.md` (Z-6) zaznacza wprost, że
   nie wiadomo nawet, czy rozkład losowania kolejnej tacki jest w ogóle niezależny od stanu
   planszy — symulator zakłada niezależność, ale to założenie modelowe, nie pomiar. Każde
   przeszukiwanie o krok głębiej niż bieżąca tacka wymaga węzła losowego (chance node) nad
   rozkładem ~15 kanonicznych kształtów (41 orientacji, `docs/calibration-assumptions.md`, Z-5) —
   to jest z natury drogie i to jest różnica względem gier z widoczną kolejką.

### Gry z widoczną kolejką kolejnych klocków (klasyczny/nowoczesny Tetris)

W klasycznym Tetrisie (odmiana badana w pracy NeurIPS 2013 wyżej) gracz zna **tylko bieżący
klocek**, nie następny — a mimo to najlepsze wyniki w literaturze (35–51 mln linii) są osiągane
**decyzją 1-ply w czasie gry**: cała „głębokość” jest zainwestowana offline, w koszt trenowania
wag ewaluatora (setki milionów prób), nie w przeszukiwanie w czasie rzeczywistym `[H]`, ten sam
artykuł. Osobne, popularne warianty (np. kontroler Fahey'a) wykorzystują dodatkowo **znajomość
następnego klocka** (widoczną w nowoczesnych wariantach Tetrisa) do wyboru lepszego ułożenia
bieżącego — to jest przeszukiwanie 2-ply nad **znanym**, nie losowym, następnym elementem, więc
bez węzła losowego. `[Z]` — ogólny opis podejścia „two-piece lookahead”, bez konkretnych liczb
o przewadze nad 1-ply: https://github.com/Ceto-Kim/tetris-heuristic-player (nie zweryfikowałem
kodu ani wyników tego repo, tylko nazwę podejścia).

**Wniosek z tej gałęzi literatury:** gdy następny element jest znany, koszt dodatkowego ply jest
niski (brak węzła losowego) i część projektów go wykorzystuje, ale **nie znalazłem żadnego
publikowanego pomiaru ilościowego**, ile dokładnie zyskuje 2-ply nad dobrym 1-ply w tej rodzinie
gier — to idzie do sekcji „czego nie ustalono”.

### Gry ze stochastycznym, nieznanym kolejnym elementem (2048, nasza gra, Tetris z ukrytą kolejką)

To jest sytuacja bliższa naszej. Dowody z literatury o graniu w takie gry przeszukiwaniem:

- **2048 (kafle losowane po każdym ruchu, znana tylko dystrybucja, nie wartość)**: rozwiązania
  typu expectimax są używane do głębokości ~5, ale **koszt rośnie wykładniczo z rozgałęzieniem
  węzłów losowych** — przy typowej planszy to setki tysięcy węzłów na ruch, mniej pod koniec gry
  (mniej pustych pól = mniejsze rozgałęzienie chance node). `[Z]` — ogólna charakterystyka
  z przeglądu tematu (nie zmierzyłem sam): https://www.baeldung.com/cs/expectimax-search,
  przykład konkretnego rzędu wielkości węzłów: https://ilovecalcs.com/solvers/2048-solver
- **Tetris Link (branching factor do 162, bez losowości kolejki, ale z bardzo dużym
  rozgałęzieniem per turę)**: MCTS z **losowymi** rolloutami (16 258 węzłów/s na CPU, 12 wątków)
  przegrywa 0% z prostą, ręcznie dostrojoną heurystyką — zbyt duże rozgałęzienie, by płytkie
  próbkowanie cokolwiek ustaliło bez naprowadzania. Osobny eksperyment na planszach Hex pokazuje
  wyraźny próg: MCTS wygrywa do 90% dopóki rozgałęzienie < 49, i spada do ~0% powyżej tego progu.
  `[H]`, ten sam artykuł co w (a): arXiv:2004.00377.
- **Nasza gra**: rozgałęzienie *w obrębie jednej znanej tacki* to 3 klocki (bez rotacji) razy
  liczba legalnych pozycji na planszy 8×8 dla każdego — nie zmierzyłem tej liczby (nie
  uruchamiałem kodu, budżet tego nie obejmował), ale strukturalnie to jest tego samego rzędu co
  branching factor pojedynczej tury w Tetris Link (~162), czyli **powyżej progu, przy którym
  w cytowanym eksperymencie na Hex czyste losowe próbkowanie MCTS przestawało działać**. To jest
  ekstrapolacja strukturalna, nie pomiar na naszym symulatorze — nazywam to wprost hipotezą do
  sprawdzenia, nie faktem.

**Gdzie leży punkt „głębiej się nie opłaca” w tej rodzinie, wg zebranych źródeł:** dokładnie na
granicy bieżącej, w pełni znanej tacki. Każdy krok w głąb *poza* nią kosztuje węzeł losowy nad
nieznanym rozkładem kształtów, a dowody z gier o podobnym lub mniejszym rozgałęzieniu (2048, Hex,
Tetris Link) pokazują, że przeszukiwanie bez bardzo dobrego naprowadzania (silna heurystyka albo
wyuczona sieć) gwałtownie traci na wartości powyżej progu rozgałęzienia rzędu kilkudziesięciu.
Żadne znalezione źródło nie mierzy tego konkretnie dla gry z tacką 3 klocków i planszą 8×8 —
to jest luka wprost do sekcji „czego nie ustalono”.

---

## (c) Funkcje oceny planszy

### Zestawy z klasycznego Tetrisa (publikowane, z konkretnymi wagami)

**Cechy Dellacherie-Thiery (9 cech), wagi wyuczone metodą CBMPI** `[H]` — z tabeli w artykule
NeurIPS 2013 (kolumny: mała plansza 10×10 / duża 10×20):

| cecha | waga (10×10) | waga (10×20) |
|---|---|---|
| landing height (wysokość osadzenia) | -2.18 | -2.68 |
| eroded piece cells | 2.42 | 1.38 |
| row transitions | -2.17 | -2.41 |
| column transitions | -3.31 | -6.32 |
| holes (dziury) | 0.95 | 2.03 |
| board wells (studnie) | -2.22 | -2.71 |
| hole depth | -0.81 | -0.43 |
| rows with holes | -9.65 | -9.48 |
| pattern diversity | 1.27 | 0.89 |

Oryginalne 6 cech Dellacherie (bez 3 dodatkowych) z wagami dobranymi ręcznie (nie uczonymi) dają
~5 000 000 linii `[H]`, ten sam artykuł, cytujący Fahey 2003.

**Prostszy, powszechnie cytowany zestaw 4 cech** (wysokość zagregowana, liczba linii do
wyczyszczenia, dziury, nierówność/bumpiness), wagi z algorytmu genetycznego: `a=-0.510066`,
`b=0.760666`, `c=-0.35663`, `d=-0.184483` `[Z]` — blog, dokładność/replikowalność nieznana:
https://codemyroad.wordpress.com/2013/04/14/tetris-ai-the-near-perfect-player/

### Cechy specyficzne dla gier z planszą bez spadania (1010!, Block Blast)

Tu literatura jest dużo słabsza. Repozytoria hobbystyczne **opisują** cechy słownie, ale **żadne
z odwiedzonych nie publikuje konkretnego, liczbowego zestawu wag**:

- „miejsce postawienia, utrzymanie combo, ilość wolnej przestrzeni, bliskość zamknięcia linii”
  `[Z]` — https://github.com/JacksonW98/block-blast-bot (opis słowny w README, bez liczb)
- „wykorzystanie przestrzeni planszy, potencjał czyszczenia linii, unikanie izolowanych komórek”
  `[Z]` — https://github.com/punoqun/1010- (opis słowny, bez liczb)

**Największy pusty prostokąt** jako cecha oceny planszy: znalazłem to wyłącznie jako klasyczny
problem geometrii obliczeniowej (algorytmy do jego liczenia), **nie jako opublikowaną cechę
w żadnym silniku gry z tej rodziny** — nie mam źródła łączącego to konkretnie z Block Blast/1010!/
Woodoku. To idzie do „czego nie ustalono”.
`[Z]` — samo istnienie problemu geometrycznego, nie jego użycie w tej rodzinie gier:
https://en.wikipedia.org/wiki/Largest_empty_rectangle

**Dopasowanie do pozostałych klocków w tacce** (feature uwzględniająca, czy zostawiony kształt
planszy pasuje do tego, co jeszcze zostało do rozegrania w bieżącej rundzie): nie znalazłem
żadnego publikowanego, konkretnego sformułowania tej cechy z wagą — tylko ogólne wzmianki
słowne w README wyżej. Idzie do „czego nie ustalono”.

### Inna rodzina, dla kontrastu (Tetris Link — punktacja przez łączenie grup, nie linie)

4 cechy: liczba łączliwych krawędzi, rozmiar grup, wynik gracza, liczba zablokowanych krawędzi
przeciwnika, wagi dostrajane ręcznie i przez Optuna `[H]`, arXiv:2004.00377. **Uwaga o
przenaszalności:** ta gra nie czyści linii — punktuje łączenie grup klocków tego samego koloru.
Cechy „dziury” i „liczba zablokowanych krawędzi” są koncepcyjnie bliskie „dziurom” z Tetrisa, ale
mechanika nagrody jest fundamentalnie inna, więc konkretne wagi się nie przenoszą — tylko
kategoria cechy (kara za fragmentację planszy) jest wspólna. To jest dokładnie ten typ pomyłki,
przed którym ostrzega `docs/calibration-assumptions.md`: wynik z innej gry o innych regułach nie
jest walutą wymienialną na wynik w naszej.

---

## Czego nie udało się ustalić

- Ile dokładnie zyskuje przeszukiwanie 2-ply (ze znanym następnym elementem) nad dobrym 1-ply
  w rodzinie gier typu Tetris — nie znalazłem publikowanego pomiaru liczbowego, tylko opisy
  podejścia.
- Jaki jest realny branching factor naszej gry (3 klocki bez rotacji × legalne pozycje na
  planszy 8×8) — nie zmierzyłem go, bo budżet tego zadania nie obejmował uruchamiania kodu.
  Bez tej liczby porównanie z progiem „~49” z eksperymentu na Hex jest tylko strukturalną
  hipotezą, nie ustaleniem.
- Czy przepustowość naszego symulatora (10 000 kroków/s bez sieci, liczba z #40) jest
  porównywalna z przepustowością symulatora Tetrisa użytego w artykule CBMPI/CE — bez tego
  przeliczenie „256 mln próbek = ~7 CPU-godzin” jest ekstrapolacją, nie pomiarem.
- Czy jakikolwiek projekt hobbystyczny dla Block Blast/1010! rzeczywiście przebija heurystykę
  zachłanną w sposób porównywalny metodologicznie (ten sam rozkład klocków, ten sam wzór
  punktacji) — żadne odwiedzone README nie publikuje wyniku w formie, którą dałoby się odnieść
  do linii bazowej z `docs/calibration-assumptions.md`.
- Konkretny, opublikowany zestaw wag łączący cechy „największy pusty prostokąt” i „dopasowanie
  do pozostałych klocków w tacce” w jakimkolwiek silniku tej rodziny gier — nie znalazłem takiego
  źródła, tylko ogólne opisy słowne bez liczb.
- Dokładne koszty obliczeniowe (liczba klatek treningu, GPU/CPU-godziny) porównania RL vs
  heurystyka na Atari Tetris z Expert Systems with Applications 2025 — miałem dostęp tylko do
  abstraktu/streszczenia, nie do pełnego tekstu.
- Czy rozkład losowania kolejnej tacki w prawdziwej grze (i w naszym symulatorze) zależy od stanu
  planszy — `docs/calibration-assumptions.md` (Z-6) już zaznacza to jako otwarte pytanie; ono
  bezpośrednio decyduje, jak bardzo kosztowny/wartościowy byłby węzeł losowy przy przeszukiwaniu
  poza bieżącą tacką, więc jest istotne i dla tego badania, nie tylko dla kalibracji.

**Czy odpowiedziałem na pytanie z issue:** tak w zakresie (a) i (c) — zebrałem publicznie
dostępne, zweryfikowane przeze mnie wyniki i koszty dla klasycznego Tetrisa i pokrewnych gier
planszowych, oraz jasno oznaczyłem brak analogicznych, mierzalnych publikacji dla samego
Block Blast/1010!. W (b) odpowiedziałem częściowo: ustaliłem jakościowo, gdzie przebiega granica
(koniec znanej tacki) i dlaczego przeszukiwanie za nią jest z natury drogie (węzeł losowy nad
nieznanym rozkładem kształtów), ale nie ma w literaturze ilościowego pomiaru „o ile dokładnie
opłaca się patrzeć głębiej” dla gry o strukturze identycznej z naszą — to zostaje bez odpowiedzi
liczbowej, tylko z jakościowym kierunkiem.
