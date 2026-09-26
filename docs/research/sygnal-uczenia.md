# Sygnał uczenia dla gier z usuwaniem linii: wynik czy przeżycie

Badanie do [#131](../../issues/131). Punkt startu: [#119](../../issues/119) (przeżycie jest
wiążącym ograniczeniem — 110,5 postawień wobec 4 369–179 057 potrzebnych do 10 mln) i
[#120](../../issues/120)/`docs/research/budzet-wyuczonej-oceny.md` (budżety epizodów N-tuple/TD,
żeby nie powtarzać tej kwerendy).

## Znaczniki

`[D]` — kod repo przeczytany samodzielnie w całości. `[K]` — liczba przeliczona samodzielnie z
podanych danych. `[Z]` — twierdzenie z zewnątrz, **zawsze** niezweryfikowane bezpośrednio w
pierwotnym tekście w tej sesji: **żaden PDF cytowany niżej nie otworzył się jako czysty tekst**
(próby: `1905.01652`, `1709.06009`, `1907.10827`, `BodoiaPuranik...pdf` — wszystkie zwróciły
strumień binarny `FlateDecode`), więc wszystko poza sekcją „Nasz obecny sygnał" przeszło przez
`WebSearch` albo przez `WebFetch` na wersji `ar5iv`/HTML, która sama streszcza treść narzędziem
sumaryzującym — zgodnie z konwencją #89/#94/#120, cytat wyglądający jak dosłowny fragment i tak
zostaje `[Z]`, nie `[D]`, jeśli przeszedł przez takie narzędzie. `arxiv.org/pdf/2111.11090`
(„Optimistic TD Learning for 2048") **nie był ponownie pobierany** — zgodnie z instrukcją z
`## Kontekst` issue, użyto o nim wyłącznie wyniku `WebSearch`.

---

## Nasz obecny sygnał (kontekst, nie wynik badania)

`[D]`, z `git show origin/task/123:docs/ntuple.md` sekcja „Kształt nagrody użyty w TD": TD(0) po
stanach następczych, `target = gain_t + V(afterstate_t)`, gdzie `gain_t` to dokładnie
`scoring.clear_points`/`placement_points` (ten sam wzór co polityka zachłanna). Po ostatnim
postawieniu partii jedna dodatkowa aktualizacja z `target = 0`. **`combo`/`combo_counter` nie
wchodzą do stanu wartościowanego przez sieć** — nazwane wprost w kodzie jako znane, nierozwiązane
ograniczenie, odsyłające do sekcji 6 `budzet-wyuczonej-oceny.md`. To jest dokładnie ten sygnał, o
którego alternatywę pyta issue #131 (nie o ten sam sygnał ponownie).

---

## (a) Czy ktoś porównał pomiarem: wynik kontra długość epizodu

**Wynik negatywny, wprost.** Dla żadnej z trzech gier (klasyczny Tetris, SZ-Tetris, 2048) nie
znalazłem publikacji, która **mierzy** trening na sygnale wynikowym (score/lines cleared)
przeciwko treningowi na sygnale przeżycia (liczba ruchów/postawień) na tym samym środowisku i tej
samej metodzie.

Najbliższe, co znalazłem `[Z]`: przegląd *The Game of Tetris in Machine Learning* (Algorta &
Şimşek, arXiv:1905.01652) stwierdza, że **prawie wszystkie** implementacje RL/ADP dla klasycznego
Tetrisa używają tego samego sygnału — jednego punktu za każdą wyczyszczoną linię — i **żadna nie
definiuje ani nie testuje alternatywy** (przeżycie, liczba postawionych klocków, nagroda
terminalna) w ramach tej samej metody. Wybór jest opisany jako **konwencja dziedziczona z
oryginalnej gry**, nie jako wynik eksperymentu porównawczego.

Dla 2048 `[Z]` znalazłem pokrewne, ale **inne** napięcie, niż pyta (a): TD/n-tuple maksymalizuje
średni wynik, ale to **osłabia dążenie do osiągnięcia dużych kafelków** (inny cel niż przeżycie —
2048 nie ma naturalnego „przeżycia" w sensie liczby ruchów, bo plansza rzadko się zapełnia przy
dobrej grze). To nie jest odpowiedź na pytanie (a), tylko sąsiedni wynik z tej samej rodziny metod,
zanotowany, żeby nie pomylić go z szukanym porównaniem.

Jedyny **anegdotyczny** (nie naukowy, nie zmierzony formalnie) sygnał w tym kierunku `[Z]`: blog
Rex L, *Reinforcement Learning on Tetris* (medium.com, PDF/HTML niedostępny bezpośrednio — 403,
treść tylko przez podsumowanie wyszukiwarki) opisuje agenta, który nauczył się przeżycia bardzo
szybko (do ~2,5 h treningu), ale był „zły w punktowaniu na krok" i czyścił zbyt często 1–3 linie
zamiast czekać na Tetris (4 linie) — czyli **agent zoptymalizowany pod przeżycie/częste czyszczenie
ma inną politykę niż zoptymalizowany pod wynik**, zgodnie z intuicją issue, ale bez kontrolowanego
porównania liczbowego obu wariantów na tym samym seedzie/budżecie.

**Konkluzja (a)**: brak zmierzonego porównania w literaturze naukowej dla tej dokładnej rodziny
gier — to samo w sobie jest odpowiedzią, zgodnie z tym, czego oczekuje kryterium akceptacji.

---

## (b) Jaki sygnał stosują najlepsze znane agenty i czy uzasadniają go pomiarem czy konwencją

| gra / metoda | sygnał | uzasadnienie |
|---|---|---|
| Klasyczny Tetris, większość prac (CE, CBMPI, Dellacherie-Thiery, TD) `[Z]` | jeden punkt za każdą wyczyszczoną linię (`lines cleared`), sumowany do końca gry (game over = zapełnienie planszy) | **konwencja** — przegląd Algorta & Şimşek wprost: „most implementations… use the original scoring function"; brak porównania z alternatywą |
| SZ-Tetris, 2048 (n-tuple/TD, GECCO 2015 i cała rodzina Jaśkowski/Szubert) `[Z]`, już w `budzet-wyuczonej-oceny.md` | punktacja gry wprost (linie/scalenia kafelków), bez modyfikacji | **konwencja** — żadna z odnalezionych prac tej rodziny nie uzasadnia wyboru pomiarem alternatywy; raportowany jest tylko wynik końcowy (linie/punkty), nie porównanie sygnałów |
| DQN na Atari (ogólnie, nie linia-usuwanie) `[Z]` | surowy wynik gry, **obcięty do `{-1,0,+1}`** | częściowo **pomiar** — Pop-Art (niżej, sekcja c) pokazuje, że obcięcie zmienia politykę względem nieobciętego wyniku na części gier, ale oryginalna decyzja o obcięciu (Mnih i in. 2015) była **inżynierską konwencją** (ujednolicenie skali między grami), nie wynikiem porównania „obcinać czy nie" |
| Klasyczny Tetris/Atari, „utrata życia = koniec epizodu" (trening) `[Z]` | terminal sztucznie wcześniej niż faktyczny koniec gry | **spór metodologiczny, zmierzony pośrednio**: *Revisiting the Arcade Learning Environment* (Machado i in. 2018, JAIR) pokazuje, że wybór granicy epizodu (utrata życia vs. faktyczny koniec gry) **mierzalnie zmienia** wyniki i ranking agentów, i rekomenduje trenowanie/ewaluację na faktycznym końcu gry — to jest najbliższy znaleziony przypadek „zmierzono, co się zmienia", ale dotyczy **granicy epizodu**, nie wprost wyboru „wynik vs. przeżycie" jako sygnału nagrody |
| Hobbystyczne repo dla Block Blast (`Botkraker/block-blast-AI`, już w `budzet-wyuczonej-oceny.md` sekcja 6) `[Z]` | wynik gry (z comba jako częścią **stanu**, nie modyfikacją nagrody) | **konwencja/projekt autora**, bez ablacji |

**Konkluzja (b)**: rozróżnienie z pytania jest ostre — **nie znalazłem ani jednego przypadku**, w
którym autorzy wybrali sygnał nagrody dla gry z usuwaniem linii **na podstawie zmierzonego
porównania z alternatywą**. Najbliższe do „pomiaru" jest zjawisko pochodne (granica epizodu w
ALE, obcinanie nagrody w Pop-Art) — oba pokazują **mierzalny wpływ wyboru sygnału na wynik**, ale
żadne nie jest samo w sobie eksperymentem „wynik kontra przeżycie".

---

## (c) Kształt nagrody o dużej rozpiętości w TD po stanach następczych: skalowanie, obcinanie, normalizacja

**Trzy niezależne wątki, żaden nie jest zmierzony na grze z naszą dokładną strukturą nagrody
(nieograniczony mnożnik comba zależny od historii):**

1. **Pop-Art** (van Hasselt & Guez, *Learning values across many orders of magnitude*, NIPS 2016,
   arXiv:1602.07714) `[Z]`: adaptacyjna normalizacja celu TD (`μ`, `σ` liczone wykładniczą średnią
   kroczącą z `Y_t`, `Y_t²`), z jednoczesną korektą wag ostatniej warstwy, żeby normalizacja nie
   zniekształcała już wyuczonej reprezentacji. **Zmierzone na Atari** (Double DQN, 57 gier):
   nieobcięta nagroda + Pop-Art wygrywa z obciętą na 32/57 gier (mediana +0,4%, średnia +34%), ale
   **zmienia politykę jakościowo** — np. Video Pinball spada z 309 942 do 56 287, Centipede rośnie
   z 5 409 do 49 066. To jest **bezpośredni precedens metody** na problem "nagroda o dużej
   rozpiętości psuje uczenie ze stałą skalą kroku", ale na architekturze głębokiej sieci, nie na
   liniowym TD po stanach następczych typu n-tuple.
2. **Obcinanie gradientu TD zależne od czasu, dla nagród o ciężkich ogonach** (*Provably Robust
   Temporal Difference Learning for Heavy-Tailed Rewards*, arXiv:2306.11455) `[Z]`: mechanizm
   jest jednowierszowy — obcina normę gradientu do promienia `b_t = (u_t)^{1/(1+p)}`, malejącego
   w czasie wg harmonogramu; `p` opisuje, ile momentów rozkładu nagrody jest skończonych. Autorzy
   **testują wyłącznie na syntetycznych MRP** (losowy proces 256 stanów, wymiar 128, szum
   Pareto(1, 1.2); okrężny błądzenie losowe) — **żadnej gry**. Zbieżność przy `p=1` (skończona
   wariancja) odtwarza klasyczne granice TD; przy cięższym ogonie tempo jest wolniejsze, ale
   dowiedzione. Mnożnik comba bez górnego ograniczenia w naszej grze jest strukturalnie właśnie
   takim rozkładem ciężkoogonowym (pojedyncze postawienie potrafi być warte dwa rzędy wielkości
   więcej — to dokładnie sformułowanie z issue), więc metoda **pasuje teoretycznie**, ale nie ma
   za sobą ani jednego pomiaru na grze.
3. **Sama rodzina n-tuple/TD dla 2048/SZ-Tetris (najbliższy analog naszej metody) nie stosuje ani
   nie omawia jawnie skalowania/obcinania/normalizacji nagrody** `[Z]` — przeszukanie nie znalazło
   takiej wzmianki mimo że 2048 ma również nagrodę o rosnącej z grą rozpiętości (scalenia kafelków
   od 4 do >100 000). *Optimistic Temporal Difference Learning for 2048* (arXiv:2111.11090, **nie
   pobierany ponownie**, tylko `WebSearch`) rozwiązuje **inny** problem tej samej rodziny —
   niedostateczną eksplorację — optymistyczną inicjalizacją **wag**, nie nagrody; to nie jest
   metoda na rozpiętość nagrody, tylko bywa mylona z nią, bo obie dotyczą „dużych wartości w
   TD po stanach następczych". Przegląd Tetrisa (Algorta & Şimşek) **wprost nazywa** problem
   pokrewny naszemu („scoring function, gdzie czyszczenie wielu linii naraz daje dodatkowe punkty,
   silnie zmienia, jakie polityki wypadają dobrze… dla takiej funkcji liniowa funkcja oceny może
   nie być najlepszym wyborem") **ale nie testuje żadnego rozwiązania** (obcinania, normalizacji)
   — zostawia to jako obserwację, nie wynik.

**Konkluzja (c)**: metody istnieją i są zmierzone (Pop-Art na Atari, dynamiczne obcinanie na
syntetycznych MRP), ale **żadna nie jest zmierzona ani na liniowym TD po stanach następczych typu
n-tuple, ani na grze z usuwaniem linii, ani na nagrodzie z mnożnikiem zależnym od historii
partii jak nasze combo**. To jest luka, nie brak wysiłku wyszukiwania.

---

## (d) Uczenie z dwóch sygnałów naraz (wynik i przeżycie), prościej niż pełne MORL — czy zmierzone na grze z usuwaniem linii

Znalezione metody, żadna nie testowana na grze z usuwaniem linii — zestawione od najprostszej:

- **Kara terminalna (stała ujemna nagroda przy końcu partii)** `[Z]`: praktyka udokumentowana w
  hobbystycznych projektach — Choe, *Scaffolding to Superhuman: How Curriculum Learning Solved
  2048 and Tetris* (blog, GPU RTX 4090, 115 tys. epizodów/75 min dla 2048): `Game Over: -1.0`
  obok nagrody za scalenia; projekt Snake-DQN (`YU-0814/snake-dqn`, GitHub) przeszukuje siatkę
  kar za śmierć `{-10,-12,-14}` łącznie z karą za krok, najlepszy wynik przy `-14`/`-0,25` —
  **to jest pomiar (grid search), ale hobbystyczny, nie publikacja naukowa, i nie na grze z
  usuwaniem linii**.
- **Kształtowanie nagrody oparte na potencjale** (Ng, Harada, Russell 1999, klasyk; zastosowania
  we współczesnych pracach, np. *Potential-based Reward Shaping in Sokoban*, arXiv:2109.05022)
  `[Z]`: `F(s,s') = γΦ(s') − Φ(s)` — jedyna z tu zebranych metod, która jest **dowiedziona
  teoretycznie** (nie tylko zmierzona empirycznie) jako niezmieniająca optymalnej polityki. Można
  zakodować „przeżycie" jako potencjał (np. malejący z liczbą zajętych komórek), bez zmiany tego,
  czego polityka faktycznie się uczy. Sokoban jest grą planszową z podobną strukturą (dyskretna
  siatka, akcje nieodwracalne) — **nie jest to jednak gra z usuwaniem linii**.
- **Głowa pomocnicza przewidująca bliskość końca epizodu** — *Terminal Prediction as an Auxiliary
  Task for Deep RL* (Kartal, Hernandez-Leal, Taylor, 2019, arXiv:1907.10827) `[Z]`: architektura
  A3C + jedna dodatkowa głowa, cel `y_i=i/N` (znormalizowana pozycja w epizodzie, `N` = średnia
  krocząca długości epizodu z ostatnich 100), strata `L = L_A3C + 0,5·L_TP` (MSE). **Zmierzone**
  na Atari (Pong, Breakout, CrazyClimber, Q*bert, BeamRider, SpaceInvaders), BipedalWalker i
  Pommerman: „nie gorzej niż A3C w żadnej grze, lepiej w Q*bert i CrazyClimber", szybsza zbieżność
  w Pommerman. **Żadna z testowanych gier nie jest grą z usuwaniem linii.**
- **Dwie głowy wartości z osobnymi współczynnikami dyskontowania, sumowane** (Random Network
  Distillation, Burda i in., ICLR 2019, arXiv:1810.12894) `[Z]`: `V = V_E + V_I`, gdzie strumienie
  mają różną strukturę czasową (epizodyczna vs. nieepizodyczna) i różny dyskont (autorzy zalecają
  `0,999` dla zewnętrznej, `0,99` dla wewnętrznej). To jest architektonicznie **dokładnie** to, o
  co pyta (d) — jeden strumień „wynik", drugi mógłby być „przeżycie" zamiast ciekawości — ale
  oryginalna praca łączy wynik z **nagrodą wewnętrzną (eksploracja)**, nie z przeżyciem wprost, i
  jest **zmierzona na Atari (Montezuma's Revenge i in.), nie na grze z usuwaniem linii**.
- **Dekompozycja nagrody na komponenty, osobna funkcja wartości na komponent** (Hybrid Reward
  Architecture, van Seijen i in., NeurIPS 2017) `[Z]`: zmierzone na Ms. Pac-Man (wynik
  nadludzki), ~1800 uogólnionych funkcji wartości, po jednej na obiekt gry (duszek, owoc,
  pigułka). Wymaga naturalnego podziału nagrody na obiekty/podcele — w naszej grze odpowiednikiem
  mogłoby być rozbicie `gain` na `clear_points`/`placement_points` (już rozdzielone w `scoring.py`
  `[D]`) plus osobny komponent za przeżycie, ale **nikt tego nie zrobił ani nie zmierzył** dla gry
  z usuwaniem linii.
- **Skalaryzacja liniowa (`nagroda = wynik + λ·przeżycie`)** `[Z]`: najprostsza z możliwych,
  opisana jako powszechna właśnie ze względu na prostotę (np. Van Moffaert i in., JMLR 2014, i
  przegląd technik MORL), ale ma udokumentowaną wadę: **dociera tylko do wypukłej części frontu
  Pareto** — metody nieliniowe (np. skalaryzacja Czebyszewa) w benchmarku *Deep Sea Treasure*
  znajdują 8 polityk optymalnych wobec 2 dla wariantu liniowego. To jest **zmierzone**, ale na
  benchmarku nawigacyjnym, nie na grze z usuwaniem linii.

**Konkluzja (d)**: metody prostsze niż pełne wielokryterialne RL **istnieją i część z nich jest
zmierzona** (kara terminalna — pomiarowo w hobbystycznym Snake; głowa pomocnicza — pomiarowo na
Atari/Pommerman; dwie głowy z osobnym dyskontem — pomiarowo na Atari; skalaryzacja liniowa —
pomiarowo, ale ze zmierzoną wadą, na benchmarku nawigacyjnym). **Żadna nie została zmierzona na
grze z usuwaniem linii ani na sygnale dokładnie „wynik + przeżycie"** — to jest wynik negatywny
analogiczny do (a), tyle że dla samej metody łączenia sygnałów, nie dla samego porównania.
Kształtowanie oparte na potencjale wyróżnia się tym, że jest **dowiedzione**, a nie tylko
zmierzone — jedyna z sześciu metod z gwarancją teoretyczną niezmieniania optymalnej polityki.

---

## (e) Co z powyższego jest wykonalne na CPU runnera bez GPU, 3600 s/polecenie, wznawialny stan

Punkt odniesienia `[D]`: `tools/train_ntuple.py` już dziś realizuje dokładnie ten wzorzec — jedno
wywołanie = jeden odcinek, stan (`ntuple-state.json`) i wagi (`ntuple-weights.json`) zapisywane po
każdym odcinku, wznowienie z asercją identyczności parametrów, zweryfikowane testem, że wznowiony
przebieg daje te same wagi/seedy co nieprzerwany. Każda z metod niżej musi zmieścić się w tym
wzorcu: koszt na krok liniowy w liczbie wag (rząd `10³–10⁴` z sekcji 3 `budzet-wyuczonej-oceny.md`),
bez sieci neuronowej trenowanej wstecznpropagacją.

**Tanie, mieszczą się bez zastrzeżeń** (koszt dodatkowy `O(1)` na krok, zero nowych wag albo
liczba wag niezmieniona, stan trywialnie serializowalny do JSON):

- **Kara terminalna** (stała dodana do `target=0` przy końcu partii) `[K]` — jedna stała liczbowa,
  zero nowego stanu.
- **Skalaryzacja liniowa** (`gain + λ·sygnał_przeżycia`) `[K]` — jedna stała `λ`, żadnej zmiany
  architektury.
- **Kształtowanie oparte na potencjale** z potencjałem liczonym z cech już dostępnych w
  `features.py` (np. liczba pustych komórek/legalnych ruchów) `[D]`+`[K]` — jedno odejmowanie na
  krok, zero nowych wag, i jedyna opcja z gwarancją niezmieniania optymalnej polityki (sekcja d).
- **Normalizacja celu TD w stylu Pop-Art** (bieżąca średnia/wariancja `target`, korekta ostatniej
  „warstwy" — u nas to jedna skalarna suma ważona łat, więc korekta to jedno przeskalowanie) `[K]`
  — dwie dodatkowe liczby w stanie (`μ`, `σ`), trywialnie wznawialne.
- **Dynamiczne obcinanie błędu TD** wg harmonogramu z sekcji (c) `[K]` — jedna liczba w stanie
  (numer iteracji, z którego liczy się promień obcięcia), trywialnie wznawialne.

**Wykonalne, ale podwaja koszt liniowy** (nadal bez GPU, nadal `O(liczba wag)` na krok, nie
`O(liczba wag sieci głębokiej)`):

- **Druga, równoległa tablica wag ucząca się „przeżycia" zamiast wyniku** (odpowiednik głowy
  pomocniczej/dwóch strumieni wartości z sekcji d, przeniesiony na architekturę liniową zamiast
  sieci głębokiej) `[K]` — dla najbogatszego wariantu łat z `budzet-wyuczonej-oceny.md` (wariant D,
  18 432 wag) druga tablica to wciąż **144 KiB**, nieistotne dla CPU i dla budżetu 3600 s/polecenie;
  wymaga drugiego pliku wag w stanie, ale schemat zapisu/wznowienia jest identyczny do istniejącego.

**Nie mieszczą się bez zmiany skali, albo nie da się ocenić bez dodatkowej liczby**:

- **Głowa pomocnicza Kartala (Terminal Prediction) i dwie głowy RND w oryginalnej postaci** `[Z]`
  — obie mierzone na sieciach głębokich (A3C/CNN) trenowanych przez wiele milionów klatek,
  typowo na GPU; **sama idea** (dodatkowy cel, dodatkowa strata) jest tania, ale **te konkretne
  wyniki liczbowe cytowane w sekcji (d) nie przenoszą się** na liniowe TD bez ponownego pomiaru —
  nikt nie zmierzył tej architektury na sieci n-tuple.
- **Hybrid Reward Architecture w oryginalnej skali** (~1800 uogólnionych funkcji wartości) `[Z]`
  — zaprojektowana dla bogatego stanu pikselowego Ms. Pac-Man; nasza gra nie ma naturalnego
  rozbicia na tyle obiektów, więc liczba komponentów byłaby rzędu pojedynczych (np. 2–3:
  `clear_points`, `placement_points`, przeżycie) — **taniej niż oryginał, ale to inna, nie
  zmierzona przez nikogo konfiguracja**.
- **Pełne wielokryterialne RL z eksploracją frontu Pareto** (skalaryzacja nieliniowa, wielokrotne
  przebiegi po siatce wag) `[K]` — mnoży nierozwiązany problem budżetu epizodów (#120: brak wzoru
  epizody(parametry), rzędy `10⁶–10⁷` w cytowanej literaturze n-tuple/TD) przez liczbę punktów
  siatki wag ocenianych; przy jednym poleceniu ≤3600 s i nieznanej przepustowości naszego
  symulatora (ustalone jako brakujące w #120) **nie da się ocenić, czy mieści się w budżecie, bez
  tej jednej brakującej liczby** — nie jest to negacja wykonalności, tylko brak danych do
  rozstrzygnięcia.

---

## Cytaty

> Most implementations of Tetris by researchers use the original scoring function, where a single
> point is allocated to each cleared line.
Źródło: streszczenie `WebFetch` (ar5iv) nad https://arxiv.org/abs/1905.01652 (Algorta & Şimşek,
*The Game of Tetris in Machine Learning*)

> The scoring function where clearing multiple lines at once gives extra points makes a big
> difference in what policies score well. For this scoring function, it is likely that a linear
> evaluation function is not the best choice.
Źródło: jw.

> On 32 out of 57 games performance is at least as good as clipped Double DQN and the median
> (+0.4%) and mean (+34%) differences are positive.
Źródło: streszczenie `WebFetch` (ar5iv) nad https://arxiv.org/abs/1602.07714 (van Hasselt & Guez,
Pop-Art, NIPS 2016)

> Θ_k(t+1) = Π_{B₂(0,ρ)}{Θ_k(t) + η_t·g_t^(k)(Θ_k(t))·𝟙{‖g_t^(k)(Θ_k(t))‖₂ ≤ b_t}}, z
> b_t=(u_t)^{1/(1+p)}
Źródło: streszczenie `WebFetch` nad https://arxiv.org/html/2306.11455 (Robust TD Learning for
Heavy-Tailed Rewards)

> Every turn the game becomes five 8x8 grids: the board, one grid per piece in hand, and one
> holding the current combo streak.
Źródło: już cytowane w `budzet-wyuczonej-oceny.md`, https://github.com/Botkraker/block-blast-AI —
powtórzone tu jako kontekst dla (b)

> A3C-TP performed no worse than standard A3C in any tested games, and it outperformed A3C in
> Q*bert and CrazyClimber. ℒ_A3C-TP = ℒ_A3C + λ_TP·ℒ_TP, λ_TP = 0.5, y_i = i/N.
Źródło: streszczenie `WebFetch` (ar5iv) nad https://arxiv.org/abs/1907.10827 (Kartal i in.,
Terminal Prediction, 2019)

> The idea of combining two value heads can also be used to combine reward streams with different
> discount factors… the RND authors recommend setting the discount factor as 0.999 for extrinsic
> rewards and 0.99 for intrinsic rewards.
Źródło: streszczenie `WebSearch` nad https://arxiv.org/abs/1810.12894 (Burda i in., Random Network
Distillation, ICLR 2019)

> Linear combination can only find solutions in convex areas of the Pareto front… Chebyshev
> outperformed linear scalarization, finding 8 vs. 2 optimal policies in the Deep Sea Treasure
> world.
Źródło: streszczenie `WebSearch` nad ogólną literaturą MORL (Van Moffaert i in., JMLR 2014, i
przegląd technik skalaryzacji)

> [Snake DQN] researchers tested a grid over death penalties ranging from −10 to −14 combined with
> step penalties, finding that a death penalty of −14 with a step penalty of −0.25 was effective.
Źródło: streszczenie `WebSearch` nad https://github.com/YU-0814/snake-dqn

> [Choe, 2048] Invalid moves (-0.05) and Game Over (-1.0) […] final policy required 75 minutes of
> training achieving a 15MB model over 115k episodes [na RTX 4090]
Źródło: streszczenie `WebFetch` nad https://kywch.github.io/blog/2025/12/curriculum-learning-2048-tetris/

> [Rex L, blog] AI is bad at scoring efficiently (score per step), often does one, two or three
> lines completion too often, and struggles to achieve higher scores per 2000 pieces.
Źródło: streszczenie `WebSearch` nad https://rex-l.medium.com/reinforcement-learning-on-tetris-707f75716c37
(strona sama zwróciła 403 przy bezpośrednim `WebFetch`)

---

## Czego nie wiem

- **Czy istnieje kontrolowane porównanie „wynik vs. przeżycie" na tej samej metodzie i tym samym
  seedzie** dla dowolnej gry z usuwaniem linii — mimo wielu sformułowań zapytania, nie znalazłem
  takiego eksperymentu; to jest odpowiedź (a), zapisana tu jeszcze raz jako luka, nie tylko jako
  wynik.
- **Treść żadnego z czterech kluczowych PDF-ów nie została przeczytana bezpośrednio** (Algorta &
  Şimşek 1905.01652, Machado i in. 1709.06009, Kartal i in. 1907.10827, Bodoia & Puranik CS229) —
  wszystkie zwróciły binarny strumień `FlateDecode` zarówno przez bezpośredni `WebFetch`, jak i
  przez wersję `ar5iv`, więc wszystko z tych źródeł jest `[Z]`, nie `[D]`, także tam, gdzie brzmi
  jak dosłowny cytat.
- **Czy blog Rex L (jedyny znaleziony przypadek z liczbami bliskimi pytaniu (a)) opisuje faktyczny
  eksperyment kontrolowany, czy tylko obserwację jednego przebiegu** — strona zwróciła 403 przy
  bezpośrednim dostępie, mam tylko streszczenie wyszukiwarki nad streszczeniem narzędzia fetch
  (podwójna niepewność, oznaczona `[Z]`).
- **Czy Pop-Art albo dynamiczne obcinanie TD (sekcja c) faktycznie działają na liniowym TD po
  stanach następczych** (nie na głębokiej sieci) — obie metody testowane na innej klasie
  aproksymatora (Pop-Art: DQN głęboki; heavy-tailed TD: syntetyczny MRP, nie n-tuple). Przeniesienie
  na naszą architekturę jest **niezmierzone przez nikogo**.
- **Przepustowość naszego symulatora** (kroki/s) — ta sama luka co w #120, wciąż nierozwiązana;
  bez niej sekcja (e) nie może rozstrzygnąć, czy metody „wykonalne, ale podwaja koszt" faktycznie
  mieszczą się w 3600 s na polecenie, tylko że są tego samego rzędu kosztu co dziś działający
  `train_ntuple.py`.
- **Czy `combo` jako druga, osobna głowa wartości (zamiast wejścia do stanu, jak proponowano w
  sekcji 6 `budzet-wyuczonej-oceny.md`) rozwiązuje problem nazwany w `docs/ntuple.md`** — to jest
  moje własne połączenie dwóch odrębnych ustaleń (HRA/RND z sekcji d + ograniczenie z `ntuple.md`),
  **nie coś, co ktokolwiek zmierzył** dla tej dokładnej kombinacji.
- **Ile z sekcji (c)/(d) zmienia się, gdyby liczyć nie SGD/backprop, tylko dokładnie wzór TD(0) z
  `tools/train_ntuple.py`** (aktualizacja całej sumy aktywnych łat naraz, nie pojedynczego
  gradientu) — żadne z cytowanych źródeł nie używa tej dokładnej reguły aktualizacji, więc
  przeniesienie liczb (nie tylko idei) wymagałoby pomiaru, nie tylko lektury.

**Czy odpowiedziałem na pytanie z issue**: patrz `.session/report.md` (zdanie wymagane poza
`docs/research/`).
