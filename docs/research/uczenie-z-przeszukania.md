# Uczenie oceny N-tuple z przeszukania: TD na trajektoriach wiązki, TreeStrap, destylacja

Badanie do [#208](../../issues/208). Punkt startu: [`przeszukanie-z-wyuczona-ocena.md`](przeszukanie-z-wyuczona-ocena.md)
(#94, rodziny metod: N-tuple/TD po afterstate, expectimax, MCTS, naprowadzanie AlphaZero) i
[`budzet-wyuczonej-oceny.md`](budzet-wyuczonej-oceny.md) (#120, budżet epizodów, sekcja 5 o
tańszych alternatywach dla TD). Ten raport idzie dalej: nie "jak przeszukiwać", tylko "jak uczyć
ocenę z przeszukania, gdy TD zachłanne stoi na plateau". **Nie proponuję wdrożenia** — materiał dla
orchestratora.

## Znaczniki

Zgodnie z issue: `[Z]` — zmierzone przez autorów źródła. `[O]` — opinia/heurystyka, niezmierzona.
Dodatkowo, tak jak w #94/#120: `[K]` — arytmetyka, którą przeliczyłem sam z podanych liczb. Żaden
PDF nie otworzył się jako czysty tekst w tej sesji (próby na oryginalne PDF-y NIPS/arXiv zwracały
strukturę binarną) — wszystkie ustalenia zewnętrzne pochodzą z wyciągów HTML (ar5iv, strony
projektów) albo streszczeń wyszukiwarki, więc **nawet cytat, który wygląda dosłownie, jest `[Z]`,
nie odczytem pierwotnego tekstu przeze mnie** — ta sama konwencja co #94/#120 (patrz `## Czego nie
wiem`).

Stan repo z issue (fakty, nie do weryfikacji przeze mnie w tej roli): TD po afterstate z sygnałem
przeżycia, ocena liścia N-tuple (`AD`/`ADC`, 52–136 łat po 6 komórek); trening zachłanny
~0,0095 s/odcinek/rdzeń → 100 tys. odcinków ≈ 17 min na jednym rdzeniu; plateau wag 200 tys.–800
tys. odcinków; polityka testowa `beam=128` po pierwszej tacce: przeżycie 395 → ~600 postawień przy
tych samych wagach, koszt ~0,4 s/partię; starty z późnej gry nie pomogły; runnery 4 rdzenie CPU,
bez GPU, limit 3600 s/polecenie, sesja 240 min.

---

## (a) Metody i czy ktoś zmierzył ich zysk nad TD zachłannym na grze z losowym dopływem

### 1. TreeStrap / "bootstrapping from game tree search" (Veness, Silver, Uther, Blair, NIPS 2009)

**Co to jest** `[Z]`: zamiast uczyć ocenę liścia z wyniku *kolejnego* przeszukania w tym samym
punkcie gry (TD-Leaf), TreeStrap aktualizuje **każdy węzeł** przeszukanego drzewa w stronę wartości
wyliczonej przez to samo (głębokie) przeszukanie *w tym samym kroku* — cel uczenia to wynik
przeszukania, nie wynik następnego kroku gry. Różnica od TD-Leaf: (1) aktualizacja wszystkich
węzłów drzewa, nie tylko liścia głównej wariancji, (2) cel to głębokie przeszukanie *teraz*, nie
płytkie przeszukanie *później*.
Źródło: https://cgi.cse.unsw.edu.au/~blair/pubs/2009VenessSilverUtherBlairNIPS.pdf (metadane i
streszczenie), https://www.chessprogramming.org/Meep (liczby). `[Z]`

**Zmierzony zysk nad prostszym TD z przeszukania** `[Z]`, gra: szachy (Meep, funkcja liniowa na
1812 cechach, ~100 aktywnych na pozycję), ~16 000 gier turniejowych między wersjami:
- TreeStrap(αβ): **2157 ± 31 Elo**. TD-Leaf: **1068 ± 36 Elo**. Różnica ~1089 Elo — TreeStrap
  wystartowany z losowych wag osiągnął poziom mistrzowski, TD-Leaf tylko poziom słabego amatora.
- Cel treningowy pochodził z "co najmniej jednego pełnego ply przeszukania plus zmienna ilość
  przeszukania spokoju (quiescence)".
- **Nie znalazłem liczby gier ani czasu treningu** (ile epizodów/dni maszynowych potrzeba było,
  żeby dojść do 2157 Elo) — tylko liczbę gier *ewaluacyjnych* po treningu. To jest luka, patrz
  `## Czego nie wiem`.

**Kluczowe dla issue: to jest zysk mierzony w szachach, nie w grze z losowym dopływem elementów.**
Nie znalazłem publikacji stosującej TreeStrap do gry z tacką/płytkami/losowym dociągiem (2048,
Tetris, Block Blast) — luka.

### 2. Multi-stage TD + weight promotion + carousel shaping (Jaśkowski, *Delayed TC*, arXiv:1604.05085 — już częściowo w #94)

To nie jest metoda "z przeszukania" wprost, ale odpowiada na **dokładnie ten sam objaw z issue**
("plateau po setkach tysięcy odcinków, starty z późnej gry nie pomogły") w 2048, więc jest
najbliższym zmierzonym precedensem plateau-breakingu, mimo że nie używa TD z celów przeszukania.

**Co to jest** `[Z]`: gra dzielona na etapy (np. wg tego, czy pojawił się już kafel 512); każdy
etap ma **osobną** sieć N-tuple. *Weight promotion*: wagi nowego etapu inicjalizowane kopią wag
etapu poprzedniego (zamiast uczenia od zera), bo "dla każdego etapu sieć musi uczyć się od zera",
co ogranicza zdolność uogólniania. *Carousel shaping*: problem osobny — "im lepszy agent na 1-ply,
tym gorszy na 3-ply", bo późniejsze etapy gry dostają mało próbek treningowych (mało epizodów tam
dociera); carousel shaping trzyma **ostatnie 1000 odwiedzonych stanów początkowych każdego etapu**
i zaczyna kolejne epizody treningowe losowo z tej puli — czyli **restart z późnej gry, ale z puli
stanów faktycznie osiągniętych przez bieżącą politykę, odświeżanej w locie**, a nie ze stałego
zbioru zapisanego raz. Źródło: https://ar5iv.labs.arxiv.org/html/1604.05085. `[Z]`

**Zmierzony zysk** `[Z]` (ten sam budżet akcji ~4×10¹⁰ dla porównań cząstkowych, różne warianty):
- multi-stage + weight promotion vs. pojedyncza sieć bazowa: **1-ply 267 544 vs 251 033 (+6,6%)**,
  **3-ply 400 124 vs 296 207 (+35,1%)**.
- dodanie carousel shaping (na wierzchu multi-stage + promotion, 2⁴ etapów): **1-ply 258 616**
  (lekki spadek), **3-ply 432 701 vs 400 124 (+8,2%)**.
- pełny zestaw (multi-stage + promotion + redundant encoding + carousel): **3-ply ~491 398**,
  czyli **~66% powyżej** pojedynczej sieci bazowej (296 207) na 3-ply. `[K]` z liczb `[Z]` wyżej.
- **Nie ma osobnej ablacji samego carousel shaping bez pozostałych technik** — efekt zmierzony
  tylko w kombinacji, zgodnie z odpowiedzią narzędzia fetch na wprost zadane pytanie.

**Ważne dla issue, znalezione wprost w tekście `[Z]`**: "This learning framework does not include
exploration, i.e., making non-greedy actions. Despite experimenting with ε-greedy, softmax, and
other custom exploration ideas, we found out that any non-greedy behavior significantly inhibits
the agent's ability to learn in the 2048 game." — autorzy **testowali** (nie tylko zakładali)
odejście od zachłannej polityki zachowania i **konkretnie stwierdzili pogorszenie**, choć **bez
liczb** (opis jakościowy, nie tabela). Przypisują to temu, że "sama gra 2048 [przez losowy dociąg]
dostarcza wystarczająco eksploracji". **Nie ma w tym źródle żadnej wzmianki o uczeniu z trajektorii
generowanych przez głębsze przeszukanie (n-ply) jako politykę zachowania** — cały trening jest na
1-ply zachłannej polityce względem uczonej wartości; głębsze przeszukanie pojawia się dopiero *po*
zakończeniu uczenia, tylko do gry testowej. `[Z]`

### 3. Expert Iteration / destylacja polityki (Anthony, Tian, Barber, NIPS 2017, "Thinking Fast and Slow")

**Co to jest** `[Z]`: pętla ekspert↔uczeń. Ekspert (przeszukanie drzewa, np. MCTS naprowadzane
bieżącą siecią) znajduje silniejsze ruchy z pojedynczej pozycji; uczeń (sieć) uogólnia te decyzje
na całą przestrzeń stanów i **zwrotnie** naprowadza kolejne przeszukanie eksperta (silniejsza sieć
→ lepsze przycinanie → silniejszy ekspert → lepsze dane treningowe → powtórz). To jest formalnie
destylacja polityki z przeszukania do sieci, iterowana. Pokonuje REINFORCE w Hex; finałowy agent
"tabula rasa" bije MoHex 1.0. Źródło: https://discovery.ucl.ac.uk/10038400/,
https://huggingface.co/papers/1705.08439. `[Z]`

**Zmierzony zysk nad czystym TD/RL bez eksperta**: w tym **konkretnym** eksperymencie (Hex) —
tak, wygrywa z REINFORCE `[Z]`, ale **nie ma tu N-tuple ani gry z losowym dopływem elementów** —
Hex jest deterministyczny, bez losowego zasilania. Nie znalazłem zastosowania Expert Iteration do
2048/gry kaflowej z losowym dopływem w znalezionych źródłach — luka.

**Koszt**: architektura zakłada głęboką sieć splotową jako ucznia i MCTS naprowadzany siecią jako
eksperta; źródła o pochodnych pracach (Policy Gradient Search) wprost stwierdzają "for their
experts, the GPU is the bottleneck rather than the CPU" `[Z]` — czyli **domyślny projekt tej
rodziny metod zakłada GPU**, co łamie nasze ograniczenie "bez GPU" wprost, choć sam **schemat**
(ekspert=przeszukanie, uczeń=dowolny aproksymator funkcji, w tym liniowy N-tuple) nie wymaga sieci
głębokiej z definicji — to jest mój wniosek strukturalny `[O]`, nie potwierdzony żadnym źródłem,
które zastosowało Expert Iteration z liniowym aproksymatorem.

**Skala kosztu tej rodziny metod (AlphaZero/AlphaGo Zero, najbliższy głośny krewny)** `[Z]`,
jako górna granica ostrzegawcza, nie do bezpośredniego przeliczenia: AlphaZero — trening szachów
~9 h na 5000 TPU pierwszej generacji do generowania partii + 16 TPU drugiej generacji do uczenia
sieci; Go ~13 dni na tym samym sprzęcie. AlphaGo Zero (eksperyment 72-godzinny) — 4,9 mln partii.
Źródło: https://deepmind.google/blog/alphazero-shedding-new-light-on-chess-shogi-and-go/,
https://en.wikipedia.org/wiki/AlphaZero. `[Z]` **Rząd wielkości sprzętu (tysiące TPU) jest o
kilka rzędów wielkości powyżej naszych 4 rdzeni CPU** `[K]` — sama rodzina metod (jako pełny,
iterowany schemat z odświeżanym ekspertem) nie mieści się w naszym budżecie sprzętowym, niezależnie
od liczby epizodów.

### 4. TD na trajektoriach polityki z przeszukania (behavior ≠ target), szukane wprost dla gier z losowym dopływem

**Nie znalazłem publikacji naukowej**, która trenuje N-tuple/TD na trajektoriach generowanych przez
politykę wiązki/n-ply (silniejszą niż zachłanna 1-ply) jako **zachowanie**, przy uczeniu wartości
zachłannej 1-ply jako **cel** (klasyczne off-policy w sensie RL, różne od TreeStrap, gdzie cel i
zachowanie pochodzą z tego samego przeszukania w tym samym kroku). Jedyny znaleziony precedens to
**hobbystyczne** repozytorium (nie publikacja naukowa, więc `[Z]` o niskiej wadze, jak
`Botkraker`/`rshk941` w #94/#120):
`LoganBradley787/2048-rl` — trenuje afterstate TD(0) na trajektoriach z "depth-1 choose search"
(tryb, w którym agent wybiera *także* dociąg kafla, nie tylko ruch) w trybie "cool"; po 4 h
treningu, w trybie cool osiągnął 1 299 016 pkt i kafel 65536; osobno zmierzony wynik przy
3-ply expectimax po treningu: 351 671 śr. (100 gier). **Autor nie podaje ablacji "zachłanne TD vs
TD z trajektorii przeszukania"** — nie da się z tego wyciągnąć, czy trajektorie z przeszukania
pomogły, zaszkodziły, czy nie miały znaczenia. Źródło: https://github.com/LoganBradley787/2048-rl. `[Z]`

**Ogólna teoria RL (nie z domeny gier kaflowych) o kosztach i mechanizmie tego podejścia** `[Z]`:
off-policy TD (uczenie wartości jednej polityki z danych zebranych inną) jest znanym, ogólnym
mechanizmem RL — pozwala uczyć się "z demonstracji eksperta", ale klasyczne metody off-policy TD
"often suffer from poor convergence and stability when handling complex problems", co motywuje
poprawki (np. Bellman residuals). Źródło: przegląd ogólny, nie z gier kaflowych,
https://doi.org/10.3390/math12223603. `[Z]` To jest **ogólne ostrzeżenie teoretyczne o
niestabilności**, nie zmierzony wynik dla żadnej gry z tej rodziny — luka.

---

## (b) Jak te metody radzą sobie z obciążeniem celu (maksimum po zaszumionej ocenie)

**To jest to samo zjawisko, co w `docs/przeszukanie-glebokie-diagnoza.md`** (sekcja "Przyczyna w
jednym zdaniu": maksimum po zaszumionych ocenach zawyża wybranego kandydata, siła rośnie z liczbą
alternatyw i z głębokością zagnieżdżonych `max`). To zjawisko ma nazwę w ogólnej literaturze RL:
**"winner's curse" / maximization bias** `[Z]` — z nierówności Jensena, maksimum po zbiorze
zaszumionych estymatorów systematycznie przecenia prawdziwą wartość, bo przypadkowo zawyżone
estymaty są faworyzowane niezależnie od ich wiarygodności. Źródło ogólne (nie z gier kaflowych):
https://arxiv.org/pdf/2210.05262, https://arxiv.org/html/2608.03069. `[Z]`

**Co robią poszczególne metody z tym zjawiskiem**:
- **TreeStrap** `[Z]`: **nie eliminuje** obciążenia z definicji metody — cel to wprost wynik
  maksimum (minimax/alfa-beta) po tej samej ocenie, którą się uczy; żadne ze znalezionych źródeł
  (streszczenia, brak dostępu do pełnego PDF) nie opisuje mechanizmu korekty obciążenia w samym
  algorytmie TreeStrap. Zmierzony sukces (2157 Elo) sugeruje, że **w praktyce** (szachy, funkcja
  liniowa, ~100 aktywnych cech/pozycję) obciążenie nie przeszkodziło dojściu do mocnej gry, ale
  **żadne źródło nie mierzy tego obciążenia osobno** — nie wiadomo, czy jest małe, czy duże a
  metoda odporna mimo obciążenia, czy po prostu nikt tego nie zmierzył. Luka.
- **Multi-stage TD + carousel shaping** `[Z]`: nie dotyczy tego zjawiska wprost, bo **cel uczenia
  w tej metodzie to zwykły cel TD(0) po afterstate (nagroda + wartość następnego afterstate)**, nie
  maksimum po przeszukaniu wielu kandydatów — ta rodzina metod **nie wprowadza** obciążenia z
  `max`, bo nie uczy się z celów przeszukania w ogóle (poza treningową polityką zachłanną 1-ply,
  która i tak jest `argmax` po **czterech** kierunkach w 2048, więc obciążenie tam jest, ale nie
  jest tematem tej pracy).
- **Expert Iteration** `[Z]`: **łagodzi pośrednio, nie usuwa**. Ekspert to MCTS, nie płytkie
  drzewo z jednym rozwinięciem — uśrednianie po wielu symulacjach (Monte Carlo) redukuje wariancję
  pojedynczego oszacowania węzła w porównaniu do jednorazowego minimax, co zmniejsza (ale nie
  zeruje) siłę obciążenia z maksimum; to jest **mój wniosek strukturalny** `[O]` z definicji MCTS
  (uśrednianie wielu próbek zamiast jednego przejścia), nie stwierdzenie znalezione wprost w
  cytowanych źródłach o Expert Iteration.
- **Ogólne korekty z literatury RL (nie z gier kaflowych/N-tuple)** `[Z]`: Double Q-learning
  (rozdzielenie wyboru argmax i oceny wybranego na dwa niezależne estymatory), Clipped Double
  Q-learning, Maxmin Q-learning (minimum z zespołu estymatorów zamiast maksimum) — wszystkie
  redukują obciążenie kosztem podwojenia (albo zwielokrotnienia) liczby utrzymywanych estymatorów.
  Źródło: https://arxiv.org/pdf/2210.05262 i przegląd ogólny cytowany wyżej. `[Z]` **To jest
  dokładnie ten sam mechanizm, co "Propozycja poprawki 1" w `przeszukanie-glebokie-diagnoza.md`**
  (rozdzielić próbki wyboru od próbek oceny) — literatura ogólna RL nazywa to "double estimator" i
  potwierdza go jako standardowe narzędzie na ten dokładny problem, niezależnie od domeny gry.
- **Żadne z pięciu źródeł nie mierzy obciążenia celu z przeszukania osobno w grze z losowym
  dopływem elementów** (2048, Tetris-podobne, Block Blast) — to jest luka wspólna dla całej
  literatury, jaką udało się znaleźć w tej sesji.

---

## (c) Koszt w odcinkach i w czasie CPU, przeliczony na nasze liczby

Założenia przeliczenia (z issue, `[D]`/podane w zadaniu, nie zweryfikowane przeze mnie w tej
roli): trening zachłanny 0,0095 s/odcinek/rdzeń, 4 rdzenie, sesja 240 min = 14 400 s, limit
3600 s/polecenie.

| metoda | jednostka kosztu w źródle | ile to u nas (przeliczenie `[K]`, przy założeniu że jeden "odcinek z przeszukania" kosztuje **tyle co koszt przeszukania**, nie 0,0095 s) | zmieści się w 240 min / 4 rdzenie? |
|---|---|---|---|
| TreeStrap (Meep, szachy) | nieznana liczba gier treningowych `[Z]` (tylko 16 000 gier *ewaluacyjnych* podano) | **nie da się przeliczyć** — brak liczby epizodów treningowych w znalezionych źródłach | nieznane wprost; ostrzegawczo: 16 000 gier ewaluacyjnych × "1 min/gra + 1 s/ruch" to już rzędu **setek godzin** samej ewaluacji, gdyby ktoś chciał odtworzyć protokół turniejowy 1:1 `[K]` (16 000 × ~1-2 min ≈ 267-533 h) — **poza budżetem jednej sesji 240 min** nawet gdyby liczyć tylko ewaluację |
| Multi-stage + carousel (2048, Jaśkowski) | 10¹⁰ akcji ≈ 10⁷ epizodów, 5,47 dnia na 24 rdzeniach `[Z]` | `[K]`: 5,47 dnia × 24 rdzenie = **131,3 rdzenio-dni** = **3 151 rdzenio-godzin**; na **4** rdzeniach to samo obliczenie zajęłoby `3151/4 ≈ 788 h ≈ 33 dni` — **o ~2 rzędy wielkości powyżej** limitu 240 min (4 h) jednej sesji | **nie** w pełnej skali z publikacji; tylko **ułamek** (np. jeden etap, mniejsza sieć) mógłby się zmieścić, ale ułamek nieznany bez pomiaru przepustowości naszego symulatora dla wersji z przeszukaniem w pętli treningowej |
| Expert Iteration / AlphaZero-rodzina | tysiące TPU × godziny/dni `[Z]` | **nieprzeliczalne na 4 rdzenie CPU w 240 min** — różnica rzędu `10³-10⁶`× sprzętu `[K]` z porównania TPU-godzin (sekcja a.3) do 4-rdzeniowej sesji 4-godzinnej | **nie**, cała rodzina w oryginalnej skali |
| TD na trajektoriach beam (hobbystyczne, `2048-rl`) | "4 h treningu" na niepodanym sprzęcie `[Z]`, bez liczby epizodów | **nieprzeliczalne** — brak liczby epizodów i specyfikacji sprzętu w źródle | nieznane; sama liczba godzin (4 h) mieści się w budżecie sesji **jeśli** sprzęt i przepustowość są porównywalne, czego nie da się sprawdzić bez uruchomienia |
| Nasz koszt referencyjny (`beam=128`, z issue) | ~0,4 s/partia, ~600 postawień/partia przy obecnych wagach `[D]` z issue | `[K]`: przy 4 rdzeniach równolegle, 240 min = 14 400 s → `14400×4/0.4 = 144 000` **partii** w całej sesji, gdyby **cały** budżet poszedł na granie (zero na trening) | punkt odniesienia, nie metoda z literatury |

**Wniosek liczbowy** `[K]`: **żadna** z trzech metod "z pierwszej linii" literatury (TreeStrap,
multi-stage 2048 pełną skalą, Expert Iteration) nie mieści się w budżecie jednej sesji 240 min na
4 rdzeniach **w swojej opublikowanej skali** — TreeStrap z braku danych o koszcie treningu (tylko
koszt ewaluacji, już rzędu setek godzin), multi-stage 2048 o ~2 rzędy wielkości za drogo (788 h vs
4 h), Expert Iteration o 3-6 rzędów wielkości za drogo (sprzęt). **Jedyna droga do zmieszczenia się
w budżecie to radykalne skalowanie w dół** (mniej epizodów, mniejsza sieć, tańsze przeszukanie
treningowe niż `beam=128`) — czego żadne z tych źródeł nie testowało wprost, bo testowały pełną,
najsilniejszą wersję swojej metody, nie wersję zredukowaną pod ograniczenie 4 CPU/240 min.

---

## (d) Ranking 2-3 wariantów wykonalnych w jednej sesji 240 min na 4 rdzeniach

Kolejność: od najtańszego/najmniej ryzykownego do najdroższego/najbardziej zgodnego z pełną
literaturą. Żaden wariant nie ma w literaturze zmierzonego kosztu **dokładnie** w naszej skali —
to są ekstrapolacje `[O]`, nie przewidywania z pomiaru.

**1. Mini-TreeStrap: aktualizacja TD na wszystkich węzłach jednego pełnego rozwinięcia bieżącej
   (znanej) tacki, nie tylko na liściu wybranym przez `argmax`.**
   Uzasadnienie z literatury: TreeStrap `[Z]` pokazuje **największy** zmierzony zysk nad
   TD-z-jednego-celu w tej samej rodzinie metod (2157 vs 1068 Elo, różnica ~1089 Elo) — ale w
   szachach, nie w grze z losowym dopływem; koszt per krok jest **znany strukturalnie** (tyle
   aktualizacji, ile węzłów w drzewie już i tak rozwiniętym przez `TrayPolicy` przy wyborze ruchu —
   zero dodatkowego przeszukania, tylko dodatkowe aktualizacje TD na już policzonych wartościach).
   To czyni ten wariant **jedynym z trzech, którego koszt CPU nie rośnie** względem obecnego
   `beam`/`lookahead`, bo nie dodaje przeszukania, tylko wykorzystuje istniejące pełniej.
   **Co zmierzyć, żeby wiedzieć, czy działa**: czy krzywa wag (norma zmiany wag na epokę, albo
   wynik zachłanny co N odcinków) rusza z plateau szybciej niż w obecnym TD-po-liściu-wybranym, przy
   tej samej liczbie odcinków.

**2. TD na trajektoriach grywanych `beam` (wąski, np. beam=8, nie beam=128) jako zachowanie, cel
   TD nadal zachłanny (1-tacka) — z podziałem próbek wyboru/oceny z `przeszukanie-glebokie-diagnoza.md`.**
   Uzasadnienie: to jest dokładnie pytanie z issue (behavior ≠ target), ale literatura **nie ma**
   zmierzonego wyniku dla gry z losowym dopływem — jest tylko ostrzeżenie z `[Z]` (2048: "any
   non-greedy behavior significantly inhibits learning", choć to dotyczy szumu eksploracyjnego, nie
   silniejszej polityki z przeszukania — **nie to samo zjawisko z definicji**, ale sąsiednie
   ryzyko) i ogólne ostrzeżenie teoretyczne o niestabilności off-policy TD. Koszt: generowanie
   trajektorii z `beam` małym jest droższe niż zachłanne o czynnik nieznany u nas (nie zmierzony w
   tym zadaniu), ale strukturalnie dużo tańsze niż `beam=128` (0,4 s/partia to już blisko granicy
   budżetu na dziesiątki tysięcy partii). **Co zmierzyć**: czy wagi wyuczone z trajektorii `beam`
   dają **wyższy wynik zachłanny** (bez przeszukania w ewaluacji) niż wagi z trajektorii czysto
   zachłannych, przy tej samej liczbie odcinków treningowych — to bezpośrednio testuje hipotezę
   issue, że przeszukanie "przenosi lepszą ocenę z nadwyżką".

**3. Multi-stage (2-3 etapy wg liczby postawień albo wg near_full_lines) z weight promotion, bez
   carousel shaping na start.**
   Uzasadnienie: zmierzony, ale w innej grze `[Z]`, zysk multi-stage+promotion sam w sobie
   (+6,6%/+35,1%) jest **mniejszy** niż pełny zestaw z carousel (+66%), więc to jest tańsza,
   częściowa wersja tej samej techniki — ale wymaga **utrzymania kilku sieci zamiast jednej**,
   czego literatura testowała dopiero przy 10⁷ epizodach (nasza sesja pozwala na znacznie mniej,
   patrz sekcja c) — **największe ryzyko tego wariantu to, że przy naszym dużo mniejszym budżecie
   epizodów, podział na etapy zmniejszy liczbę próbek na etap poniżej progu, przy którym cokolwiek
   się nauczy** (dokładnie problem, który carousel shaping miał rozwiązywać, a który tu celowo
   pomijamy dla taniości). **Co zmierzyć**: wynik zachłanny **per etap** (nie tylko średni wynik
   partii) — czy sieć drugiego etapu bije sieć jednoetapową *na stanach z drugiego etapu*, nawet
   jeśli ogólny wynik partii się nie zmienia (bo mało odcinków dotarło do etapu 2).

**Nie rekomenduję** (poza rankingiem, bo nie mieszczą się w budżecie sesji, patrz sekcja c):
pełnowymiarowy multi-stage+carousel 2048 (788 rdzenio-godzin), TreeStrap w skali szachowej (koszt
treningu nieznany, ale ewaluacja już poza budżetem), Expert Iteration/AlphaZero-rodzina (sprzęt
o rzędy wielkości za mały).

---

## Cytaty

> TreeStrap-based algorithms can learn a good set of weights starting from random weights in
> self-play chess, whereas TD-Leaf learning occurred only to the level of weak amateur play.
Źródło: streszczenie wyszukiwarki nad https://proceedings.neurips.cc/paper/2009/file/389bc7bb1e1c2a5e7e147703232a88f6-Paper.pdf

> TreeStrap(αβ) achieved "2157 ± 31" Elo compared to TD-Leaf's "1068 ± 36" Elo [...] approximately
> 16,000 games were played [...] "1 minute per game plus 1 second per move Fischer time" [...]
> "1812 features," with "approximately 100 features active in any given position" [...] target
> values came from "at least one ply of full-width search, plus a varying amount of quiescence
> search."
Źródło: https://www.chessprogramming.org/Meep (wyciąg narzędzia fetch)

> Multi-stage weight promotion: "for each stage, the n-tuple network must learn from scratch" [...]
> "generalization capabilities of the multi-stage function approximator are significantly limited."
> Carousel shaping: "the better an agent gets at 1-ply, the worse it scores at 3-ply" [...]
> "maintains the last 1000 visited initial states of each stage" [...] "starts each episode with a
> randomly selected initial state of the current stage."
Źródło: https://ar5iv.labs.arxiv.org/html/1604.05085 (wyciąg narzędzia fetch)

> Multi-stage + weight promotion vs. single-stage baseline (4×10¹⁰ actions): 1-ply 267,544 →
> baseline 251,033 (+6.6%); 3-ply 400,124 → baseline 296,207 (+35.1%). Carousel shaping (2⁴ stages
> + weight promotion): 3-ply 432,701 → prior 400,124 (+8.2%). Full ensemble: 3-ply ~491,398.
Źródło: jw. (wyciąg narzędzia fetch, liczby oznaczone tam jako pochodzące wprost z tekstu artykułu)

> "This learning framework does not include exploration, i.e., making non-greedy actions. Despite
> experimenting with ε-greedy, softmax, and other custom exploration ideas, we found out that any
> non-greedy behavior significantly inhibits the agent's ability to learn in the 2048 game."
Źródło: jw.

> Expert Iteration outperforms REINFORCE for training a neural network to play the board game Hex,
> and the final tree search agent, trained tabula rasa, defeats MoHex 1.0.
Źródło: streszczenie wyszukiwarki nad https://discovery.ucl.ac.uk/10038400/

> for their experts, the GPU is the bottleneck rather than the CPU
Źródło: streszczenie wyszukiwarki nad https://arxiv.org/html/1904.03646

> AlphaZero used 5,000 first-generation TPUs to generate self-play games and 16 second-generation
> TPUs to train the neural networks. Training lasted for approximately 9 hours in chess, 12 hours
> in shogi and 13 days in Go. [...] Over 72 hours, 4.9 million matches were played in one AlphaGo
> Zero experiment.
Źródło: https://deepmind.google/blog/alphazero-shedding-new-light-on-chess-shogi-and-go/,
https://en.wikipedia.org/wiki/AlphaZero (wyciąg narzędzia fetch)

> [LoganBradley787/2048-rl] training duration "4 hours on the choose game" [...] scored "1,299,016
> on the canonical game and built a 65536" [...] mean score at depth-3 expectimax "351,671 across
> 100 test games."
Źródło: https://github.com/LoganBradley787/2048-rl (repozytorium hobbystyczne, nie publikacja
naukowa — waga jak `Botkraker`/`rshk941` w #94/#120)

> When Q-values are uncertain, the maximization operator deterministically favors the largest
> estimate, regardless of its reliability [...] known as the "winner's curse" [...] Double
> Q-learning [...] decouple action-selection and action-evaluation when computing bootstrap
> targets.
Źródło: streszczenia wyszukiwarki nad https://arxiv.org/pdf/2210.05262, https://arxiv.org/html/2608.03069

---

## Czego nie wiem

- **Koszt treningowy TreeStrap w epizodach/godzinach maszynowych** — znalazłem tylko koszt
  ewaluacji (16 000 gier), nie koszt dojścia do wytrenowanych wag. Bez tego nie da się w ogóle
  ocenić, czy skrócona wersja TreeStrap zmieściłaby się w 240 min.
- **Czy ktokolwiek zastosował TreeStrap, Expert Iteration albo destylację polityki z wiązki do gry
  z losowym dopływem elementów (2048, Tetris-podobne, Block Blast)** — nie znalazłem ani jednej
  takiej publikacji; wszystkie zmierzone zyski tych metod pochodzą z gier deterministycznych
  (szachy, Hex). To jest największa luka względem pytania z issue, bo issue pyta wprost o grę z
  losowym dopływem.
- **Czy "any non-greedy behavior significantly inhibits learning" (2048, cytat wyżej) przenosi się
  na trajektorie z *silniejszej* polityki (przeszukanie), a nie tylko na szum eksploracyjny
  (ε-greedy/softmax)** — to są różne zjawiska (celowy szum vs systematycznie lepsza decyzja), a
  cytowane źródło testowało tylko pierwsze. Nie znalazłem testu drugiego.
- **Liczbowa ablacja samego carousel shaping** (bez multi-stage/promotion/redundant encoding
  równocześnie) — źródło łączy techniki, nie rozdziela ich efektu w pełni.
- **Czy obciążenie celu z `max` (TreeStrap, multi-stage z polityką zachłanną `argmax` po 4
  kierunkach) było kiedykolwiek zmierzone osobno** w którymkolwiek z cytowanych źródeł — żadne nie
  podaje takiej liczby; wnioski o mechanizmie obciążenia pochodzą z ogólnej teorii RL (Q-learning),
  nie z tych konkretnych prac o grach.
- **Przepustowość naszego symulatora dla wariantu z przeszukaniem w pętli treningowej** (ile
  odcinków/sekundę da się wygenerować, gdy każdy odcinek wymaga wywołania `beam`/`lookahead`, nie
  tylko zachłannej oceny) — poza budżetem tego zadania (nie uruchamiałem kodu); bez tej liczby
  żaden z trzech wariantów w rankingu (d) nie da się przełożyć z "zmieści się w 240 min" na
  konkretną liczbę odcinków, jaką faktycznie można wytrenować.
- **Pełna treść źródeł czytanych tylko przez wyciągi/streszczenia** (NIPS 2009 TreeStrap PDF,
  NIPS 2017 Expert Iteration PDF, arXiv:1604.05085 poza tym, co ar5iv wyciągnął) — żaden PDF nie
  otworzył się jako czysty tekst w tej sesji; wszystko oznaczone `[Z]`, zgodnie z konwencją #94/#120,
  mimo że część cytatów wygląda jak dosłowne fragmenty.
- **Czy schemat Expert Iteration działa z liniowym aproksymatorem (N-tuple) zamiast głębokiej
  sieci** — to jest mój wniosek strukturalny (`[O]`, sekcja a.3), nie potwierdzony żadnym
  znalezionym źródłem, które faktycznie tak zrobiło.

**Czy odpowiedziałem na pytanie z issue**: częściowo, z wyraźnie nazwaną, dominującą luką.
Opisałem cztery rodziny metod (TreeStrap, multi-stage+carousel 2048, Expert Iteration, TD na
trajektoriach z przeszukania) z liczbami zysku i kosztu tam, gdzie źródła je podają, i przeliczyłem
te koszty na nasz budżet (240 min, 4 rdzenie) — wniosek jest w większości negatywny: **żadna z
metod w swojej opublikowanej, pełnej skali się nie mieści**, o 2 do 6 rzędów wielkości za drogo.
Dla pytania (b), o obciążenie celu z maksimum po zaszumionej ocenie, znalazłem nazwę zjawiska i
standardowe korekty z ogólnej literatury RL (double estimator), ale **żadne źródło o tych
konkretnych metodach (TreeStrap/multi-stage/Expert Iteration) nie mierzy tego obciążenia w swojej
własnej grze** — to jest odpowiedź częściowa, złożona z dwóch osobnych ciał literatury (metody z
gier vs teoria RL), nie jedno źródło. Największa, jednoznaczna luka: **żadna z czterech rodzin
metod nie była nigdy (w znalezionych źródłach) zastosowana do gry z losowym dopływem elementów** —
wszystkie zmierzone zyski pochodzą z gier deterministycznych (szachy, Hex), więc przeniesienie na
naszą grę jest ekstrapolacją, nie faktem zmierzonym w tej samej rodzinie gier co nasza.
