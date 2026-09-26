# Budżet wyuczonej oceny: episody, wagi, alternatywy dla TD, bez GPU

Badanie do [#120](../../issues/120). Punkt startu: [`przeszukanie-z-wyuczona-ocena.md`](przeszukanie-z-wyuczona-ocena.md)
z [#94](../../issues/94) (metody: N-tuple/TD po afterstate, expectimax, MCTS, naprowadzanie w
stylu AlphaZero) i [`kierunek-algorytmiczny.md`](kierunek-algorytmiczny.md) (koszty CE/CBMPI na
klasycznym Tetrisie). Tu liczę **budżet**: ile epizodów, ile wag, ile CPU — pod nasze ograniczenia
(brak GPU, ≤3600 s/polecenie, `c=2`, plansza 8×8, tacka 3 klocków bez rotacji). **Nie polecam
wdrożenia** — to materiał dla orchestratora.

## Znaczniki

`[D]` — kod repo z Budżetu (`scoring.py`, `features.py`), przeczytany samodzielnie w całości.
`[K]` — liczba, którą przeliczyłem sam z podanych danych (arytmetyka jawna). `[Z]` — twierdzenie
z zewnątrz, niezweryfikowane przeze mnie bezpośrednio w pierwotnym tekście (streszczenie
wyszukiwarki albo wyciąg narzędzia fetch — **żadnego PDF nie udało się odczytać jako czysty
tekst w tej sesji**, tak jak w #94: próby `ppsn2012_RL-CFour.pdf`, `ThillCIG2014.pdf`,
`arxiv.org/pdf/2111.11090` zwróciły tylko strukturę binarną). Cytat wyglądający jak dosłowny
fragment artykułu i tak jest `[Z]`, jeśli przeszedł przez streszczające narzędzie, zgodnie z
konwencją #89/#94.

---

## 1. Czy rachunek `c=2` z issue jest poprawny

Issue liczy: 8 wierszy + 8 kolumn jako łaty ośmiokomórkowe → `16 patchy × 2^8 stanów = 4096 wag`.

**Sprawdzenie** `[K]`: `2^8 = 256`; `16 × 256 = 4096`. Rachunek jest arytmetycznie poprawny.

**Co to znaczy w zestawieniu z literaturą 2048** `[K]`, dane wejściowe `[Z]` (sekcja Cytaty):
sieć bazowa Jaśkowskiego "3333-4242" to 4 łaty po 6 komórek, `c=16`: `4 × 16^6 = 67 108 864` wag.
Gdyby policzyć **tę samą liczbę i wielkość łat** (4 łaty × 6 komórek) przy naszym `c=2`:
`4 × 2^6 = 256` wag — różnica to czynnik `67 108 864 / 256 = 262 144`, czyli `log10(262 144) ≈ 5,42`,
**około pięciu i pół rzędu wielkości**, nie sześciu jak w tekście issue, ale tego samego rzędu
(issue porównywał całą sieć 4096-wagową do 2048, nie łatę-do-łaty; przy porównaniu "różne sieci,
różna liczba/wielkość łat" różnica faktycznie dochodzi do ~16 384× = 4,2 rzędu dla wariantu z
issue vs. sieci bazowej Jaśkowskiego, patrz niżej). **Wniosek liczbowy, poprawiający issue**:
rząd wielkości oszczędności jest właściwy (**4–5,5 rzędu wielkości**, nie dokładnie sześć), a
źródłem oszczędności jest wyłącznie wykładnik `c` w `c^k` — rozmiar planszy (64 komórki u nas vs
16 w 2048) **nie wchodzi do tego wzoru wprost**, wchodzi tylko przez to, ile łat potrzeba, żeby ją
pokryć (sekcja 3).

**Co robi to z potrzebną liczbą epizodów — odpowiedź krótka: nic bezpośrednio**, bo (sekcja 2)
nie znalazłem w literaturze wzoru łączącego rozmiar sieci z liczbą epizodów; mniejsza sieć nie
implikuje wprost mniej epizodów.

---

## 2. Liczba epizodów jako funkcja liczby parametrów

**Odpowiedź wprost: nie znalazłem w literaturze N-tuple/TD żadnej publikowanej, ilościowej
zależności "liczba wag → liczba potrzebnych epizodów" dla konkretnej gry.** To, co znalazłem,
to punkty empiryczne z różnych prac, potraktowane jako z góry ustalony **budżet obliczeniowy**,
nie jako wielkość wyprowadzona z rozmiaru sieci:

| praca | plansza / `c` | wags | epizody/gry treningowe | wynik |
|---|---|---|---|---|
| Szubert & Jaśkowski, TD(0) na 2048 `[Z]` | 4×4, `c=16` | ~23 mln | 1 mln | 100 178 śr. |
| Wu i in., 2048 `[Z]` | 4×4, `c=16` | 67 mln | 5 mln | 142 727 śr. |
| Jaśkowski i in., *Delayed TC*, 2048 `[Z]` (już w #94) | 4×4, `c=16` | do 1,3 mld (multi-stage) | 10⁷ (budżet **stały**, `10^10` akcji, niezależny od wariantu sieci) | 311k–609k w zależności od głębokości przeszukania |
| Jaśkowski, Szubert, Liskowski, GECCO 2015, *SZ-Tetris* `[Z]` | 20×10, `c=2` (tylko klocki S/Z) | >4 mln | 4 mln | 294,8±1,4 linii |
| Thill, Koch, Konen, PPSN 2012, *Connect-4* `[Z]` | 7×6, `c=3` | >500 tys. (~650 tys.) | „kilka milionów" gier (liczba niedokładna — źródło nieczytelne jako PDF w tej sesji) | pokonuje optymalny Minimax |

**Ustalenie kluczowe** `[K]`, z połączenia wierszy tabeli: w pracy *Delayed TC* (2048) budżet
treningu **10⁷ epizodów jest stały i niezależny od wariantu sieci** — testowano nim sieci od
kilkudziesięciu milionów do 1,3 miliarda wag **tym samym budżetem epizodów**, różniąc jedynie
wynik końcowy i czas per epizod (bo większa sieć = wolniejsza aktualizacja). To wprost odpowiada
na pytanie kryterium: **`10⁷` w 2048 nie bierze się z rozmiaru sieci — bierze się z przyjętego
budżetu obliczeniowego (dni maszynowe), ustalonego przez autorów niezależnie od architektury**.
Zależność, jaka istnieje, jest odwrotna do intuicji "większa sieć = więcej epizodów": większa
sieć przy tym samym budżecie epizodów daje better wynik (67 mln wag/5 mln epizodów → 142 727,
w porównaniu do 23 mln wag/1 mln epizodów → 100 178), ale **oba wag i epizody rosły w tych dwóch
pracach jednocześnie** (różne prace, różne protokoły) — nie da się z tych dwóch punktów wydzielić
czystej zależności "epizody jako funkcja samych wag przy stałej jakości wyniku".

**Drugi mocny argument przeciw prostej zależności** `[K]`: SZ-Tetris (plansza **binarna**, `c=2`,
jak u nas, >4 mln wag) osiąga mocny wynik przy **4 mln** epizodów — tego samego rzędu wielkości
co 2048 (1–5 mln), **mimo** że SZ-Tetris ma 4 mln wag, a najmniejsza sieć 2048 w tabeli ma 23 mln
(prawie 6× więcej). Gdyby liczba epizodów skalowała się wprost z liczbą wag, SZ-Tetris
potrzebowałaby wyraźnie mniej niż 2048 — nie potrzebuje. To sugeruje, że **trudność gry
(rozgałęzienie, gęstość nagrody, długość epizodu) waży więcej niż sama liczba wag** — ale to jest
wniosek z dwóch nieporównywalnych protokołów (różne gry, różni autorzy), nie dowód.

**Teoria ogólna (poza N-tuple)** `[Z]`: literatura o TD z liniową aproksymacją funkcji (np.
Bhandari, Russo, Singal, *A Finite Time Analysis of TD Learning with Linear Function
Approximation*, COLT 2018/Operations Research 2021, https://arxiv.org/abs/1806.02450) podaje
formalne granice zbieżności zależne od wymiaru cech `d`, ale **nie udało mi się odczytać
dokładnej postaci wzoru** (PDF nieczytelny narzędziem w tej sesji, streszczenia wyszukiwarki nie
podają wykładnika `d`) — mam tylko potwierdzenie jakościowe: „sample complexity zależy od wymiaru
danych (d)", z sugerowaną poprawą rzędu `O(d)` względem pewnych metod bazowych, w kontraście do
LSTD, który jest **kwadratowy w `d`** za to zbieżny w mniejszej liczbie próbek/epizodów
(https://ietresearch.onlinelibrary.wiley.com/doi/full/10.1049/cit2.12202, ogólne charakterystyki
LSTD vs TD, nie z domeny gier planszowych). **To nie daje przeliczalnej liczby epizodów dla
naszego `d≈4096`** — tylko kierunek (liniowa albo gorsza zależność od `d` w standardowym TD;
LSTD wymaga mniej epizodów kosztem kwadratowego kosztu pamięci/czasu na aktualizację, czyli przy
`d=4096` to `~16,8 mln` operacji/aktualizację `[K]` (4096²), wciąż tanie na CPU per krok).

**Wniosek dla naszego budżetu** `[K]`+`[Z]`: nie da się **przeliczyć** `c=2` na godziny z istniejącej
literatury, bo nie ma w niej wzoru episody(parametry). Da się natomiast argumentować **hipotezą
niezweryfikowaną** `[Z]`, że skoro nasza sieć (4096–18 432 wag w wariantach sekcji 3) jest o
2–4 rzędy wielkości mniejsza niż SZ-Tetris (>4 mln, najbliższy analog `c=2`), i SZ-Tetris
potrzebowała 4 mln gier, to **nasza sieć prawdopodobnie potrzebuje wyraźnie mniej niż 4 mln gier
— ale "wyraźnie mniej" nie jest liczbą, jest kierunkiem**. Jedyny sposób, by zamienić to w liczbę,
to zmierzyć krzywą uczenia na naszym symulatorze wprost (zadanie-pomiar, nie research).

---

## 3. Konkretne warianty łat dla planszy 8×8, `c=2`

Nie znalazłem żadnej publikacji projektującej sieć N-tuple dla planszy 8×8 z usuwaniem linii
(patrz sekcja 4) — poniższe układy łat są **moją konstrukcją**, zbudowaną wg zasady z literatury
2048/SZ-Tetris (małe, nakładające się lub systematycznie kafelkujące okna, każde jako niezależna
tablica LUT o `2^k` wpisach) `[K]` (arytmetyka), nie przeniesieniem gotowych współrzędnych.

| wariant | kształt łaty | `k` (komórek/łatę) | liczba łat | wzór | wagi razem | pamięć (float64, 8 B/wpis) |
|---|---|---|---|---|---|---|
| A — z issue | 8 wierszy + 8 kolumn (proste, pełna szerokość/wysokość) | 8 | 16 | `16 × 2^8` | **4 096** | 32 KiB |
| B — małe kwadraty 2×2, kafelkowanie z zakładką 1 | kwadrat 2×2 | 4 | `7×7=49` (wszystkie pozycje 2×2 na 8×8) | `49 × 2^4` | **784** | 6,1 KiB |
| C — prostokąty 2×3/3×2, systematyczne | prostokąt 2×3 i 3×2 (obie orientacje) | 6 | `7×6 + 6×7 = 84` (wszystkie pozycje obu orientacji) | `84 × 2^6` | **5 376** | 42 KiB |
| D — kwadraty 3×3, systematyczne | kwadrat 3×3 | 9 | `6×6=36` (wszystkie pozycje) | `36 × 2^9` | **18 432** | 144 KiB |

**Sprawdzenie arytmetyki** `[K]`: wariant B — pozycji 2×2 na siatce 8×8 jest `(8-2+1)×(8-2+1)=7×7=49`;
`2^4=16`; `49×16=784`. Wariant C — pozycji 2×3 (2 wiersze, 3 kolumny) jest `(8-2+1)×(8-3+1)=7×6=42`,
tyle samo dla obrotu 3×2 (`6×7=42`), razem `84`; `2^6=64`; `84×64=5376`. Wariant D — pozycji 3×3 jest
`(8-3+1)×(8-3+1)=6×6=36`; `2^9=512`; `36×512=18432`.

**Dla porównania, sieci 2048 z #94** (`c=16`): najmniejsza w tabeli sekcji 2 to ~23 mln wag —
**wszystkie cztery warianty A–D razem to wciąż `<0,08%` tej liczby** `[K]` (`18432/23000000 ≈
0,08%`). Nawet najbogatszy wariant D mieści się w pamięci L2 typowego CPU (144 KiB), co eliminuje
pytanie o pamięć jako ograniczenie na naszym budżecie — **wąskim gardłem będzie liczba epizodów
potrzebna do wypełnienia tablic sensownymi wartościami, nie ich rozmiar** (patrz sekcja 2, bez
liczbowej odpowiedzi).

**Czego ten dobór łat nie rozstrzyga** (moja konstrukcja, nie zweryfikowana pomiarem): (a) czy
łaty proste na całą szerokość/wysokość (wariant A, kopiujące strukturę issue) lepiej wychwytują
cechy istotne dla usuwania linii (bo linia to dokładnie jeden wiersz/kolumna) niż małe kwadraty
(B/D), które lepiej wychwytują lokalne dziury/fragmentację — to jest hipoteza inżynierska
zgodna z tym, czego szuka `near_full_lines`/`largest_empty_rect` w `features.py` `[D]`, nie
ustalenie; (b) czy warto łączyć warianty (np. A+C jako jedna sieć, `4096+5376=9472` wag) — nikt
w literaturze 2048 nie ograniczał się do jednego kształtu łaty (sieć "3333-4242" miesza rozmiary),
więc to jest zgodne z praktyką, ale nie przeniesione z konkretnego źródła.

---

## 4. Publikowana uczona ocena dla gier z usuwaniem linii i binarnym zajęciem komórki

**Wynik wyszukiwania jest w większości negatywny — i to jest wynik, nie brak wysiłku.**

- **1010!, Block Blast, Woodoku**: nie znalazłem żadnej publikacji naukowej (arXiv, konferencja,
  czasopismo). Istnieje środowisko `gym-woodoku` (Gymnasium, plansza 9×9, tacka 3 klocków,
  czyszczenie bloków 3×3) `[Z]` https://github.com/helpingstar/gym-woodoku — samo środowisko,
  repo **nie zawiera wyników żadnego wytrenowanego agenta** (sprawdzone wprost w README).
  Repozytoria hobbystyczne dla Block Blast (`Botkraker/block-blast-AI`, `rshk941/block-blast-solver`,
  `snickrscodes/Block-Blast-AI` — już częściowo w `kierunek-algorytmiczny.md`) **nie są
  publikacjami naukowymi**, ale dwa z nich podają liczby, patrz sekcja 5 i 6.
- **Tetris bez spadania / z pełną widocznością (nie klasyczny Tetris)**: nie znalazłem.
- **Klasyczny Tetris z uczoną (nie ręczną) oceną liniową na cechach**: CE/CBMPI z
  `kierunek-algorytmiczny.md` (Gabillon i in., NeurIPS 2013) **to jest** uczona ocena liniowa
  (metoda ADP), już opisana tam z liczbami (256 mln–1,7 mld próbek) — nie powtarzam.
- **SZ-Tetris (plansza binarna `c=2`, tylko klocki S/Z, bez pełnego zestawu, ale usuwanie linii
  jest identyczną mechaniką co Tetris)**: **to jest najbliższy znaleziony analog naszego `c=2`**,
  patrz sekcja 2 — TD(0) na systematycznej sieci N-tuple, >4 mln wag, 4 mln gier, 294,8±1,4 linii,
  20× tańsze niż CMA-ES dający porównywalny wynik `[Z]` (opis w sekcji Cytaty).
  Źródło: Jaśkowski, Szubert, Liskowski, *High-Dimensional Function Approximation for
  Knowledge-Free RL: A Case Study in SZ-Tetris*, GECCO 2015,
  https://www.researchgate.net/publication/280043948 (treść przez streszczenie wyszukiwarki,
  PDF nieczytelny w tej sesji, stąd `[Z]` mimo że to jest dokładnie gra binarna z usuwaniem linii).

**Konkluzja tego kryterium** `[K]`: dla naszej dokładnej rodziny gier (siatka, tacka klocków bez
spadania, usuwanie linii, `c=2`) **nie istnieje** (albo nie jest publicznie indeksowana) żadna
naukowa publikacja z uczoną oceną. Najbliższy naukowo zweryfikowany analog to **SZ-Tetris**
(usuwanie linii + `c=2`, ale ze spadaniem i tylko dwoma typami klocków) — różni się od naszej gry
mechaniką spadania/grawitacji (u nas klocek trzeba oprzeć o istniejące komórki lub dno, ale nie
ma "opadania" w czasie ruchu) i brakiem tacki wielu klocków naraz, ale **dzieli z nami dokładnie
to, co issue pyta**: binarne zajęcie komórki i usuwanie linii jako jedyny mechanizm nagrody
poza samym postawieniem klocka.

---

## 5. Tańsze alternatywy dla TD — ocenione liczbowo

| alternatywa | źródło z liczbami | epizody | mieści się w kilku CPU-godzinach? |
|---|---|---|---|
| CE (cross-entropy) na cechach Dellacherie-Thiery, Tetris | `kierunek-algorytmiczny.md` (NeurIPS 2013) `[H]` (już ustalone tam) | 1,7 mld próbek do zbieżności (duża plansza) | **nie** przy tempie 10k kroków/s naszego symulatora (~47 CPU-h ekstrapolowane, nie zmierzone) |
| CBMPI (ADP w przestrzeni polityk), Tetris | jw. | 256 mln próbek | **na granicy** (~7 CPU-h ekstrapolowane) |
| TD(0) na sieci N-tuple, SZ-Tetris (`c=2`, usuwanie linii) | sekcja 2/4, GECCO 2015 `[Z]` | 4 mln gier | zależy od przepustowości naszego symulatora, nieznanej w tym zadaniu (poza budżetem) — **nie da się przeliczyć bez tej liczby** |
| VD-CMA-ES, SZ-Tetris, ta sama ocena co TD | jw. `[Z]` | 100 mln gier (20–25× więcej niż TD dla porównywalnego wyniku) | **droższa niż TD, nie tańsza** — to jest wynik przeciwny do intuicji "ewolucja jest prostsza więc tańsza"; w tej konkretnej publikacji TD **wygrywa** kosztowo z CMA-ES na tej samej reprezentacji |
| PPO (głęboka sieć + afterstate policy), Block Blast, plansza 8×8, tacka 3 klocków, 27 kształtów | `Botkraker/block-blast-AI` `[Z]` https://github.com/Botkraker/block-blast-AI | 40–50 mln **ruchów** (nie epizodów wprost; przy ~110 postawień/partię `[D]` z issue, `40 000 000/110 ≈ 364 000` epizodów `[K]`, zgrubne przeliczenie) | nieznane bez zmierzonej przepustowości symulatora u nas — ale rząd wielkości (setki tysięcy epizodów) jest **dwa rzędy wielkości mniejszy** niż miliony epizodów n-tuple/TD w 2048/SZ-Tetris |
| Deep RL z małą siecią (LSTM + rozkładowa C51/QR-DQN), 2048 | https://arxiv.org/html/2507.05465v1 `[Z]` | **5000–9000 epizodów** | tak, jeśli przepustowość symulatora pozwala — ale wynik (5693–6536 śr.) jest **rząd wielkości niższy** niż nasycone sieci n-tuple (100k–600k w 2048), więc to jest "tańsze i słabsze", nie "tańsze i tak samo dobre" |
| Regresja liniowa (LSTD / MC-regresja) na cechach afterstate wobec zwrotu z partii | ogólna teoria, nie zmierzona w żadnej z gier tej rodziny `[Z]` https://ietresearch.onlinelibrary.wiley.com/doi/full/10.1049/cit2.12202 | nieznana liczbowo dla gier planszowych; jakościowo: **mniej epizodów niż TD, koszt kwadratowy w liczbie wag** (`d²` na aktualizację; przy `d≈4096` to `~16,8 mln` operacji/aktualizację `[K]`, wciąż tanio) | brak liczby epizodów w źródle — nie da się ocenić wprost, tylko kierunek |

**Najsilniejszy, zweryfikowany numerycznie wniosek tej sekcji** `[K]`: w jednej publikacji
(SZ-Tetris, GECCO 2015), na **tej samej reprezentacji cech (n-tuple)**, TD(0) pobił CMA-ES
kosztowo o czynnik 20–25× — to jest **przeciw-dowód** na intuicję "ewolucja różnicowa/CMA-ES jest
tańszą alternatywą dla TD"; w tym jednym zmierzonym przypadku jest odwrotnie. Drugi wniosek: **im
"głębsza"/mniej liniowa reprezentacja (PPO z siecią splotową, deep RL z LSTM), tym mniej epizodów
potrzeba do przyzwoitego (nie rekordowego) wyniku** — oba znalezione przykłady (Block Blast PPO,
2048 deep RL) potrzebowały o 1–2 rzędy wielkości mniej epizodów niż klasyczny N-tuple/TD, kosztem
gorszego wyniku końcowego względem nasyconych sieci n-tuple. **Żadna z tych liczb nie jest
bezpośrednio przenoszalna na nasz budżet** bez znajomości przepustowości naszego symulatora
(poza budżetem tego zadania).

---

## 6. Mnożnik nieograniczonego combo

**Bezpośredniej literatury naukowej o uczeniu oceny w grze z nagrodą proporcjonalną do
nieprzerwanej serii nie znalazłem** — zapytania o „combo multiplier reinforcement learning value
function" i „streak reward state augmentation" nie zwróciły żadnego wyniku specyficznego dla tego
mechanizmu nagrody; ogólne prace o „state augmentation" dotyczą czego innego (odporności na
perturbacje stanu, nie kodowania licznika combo).

**Jedyny konkretny, zweryfikowany (choć nie naukowy) precedens** `[Z]`: `Botkraker/block-blast-AI`
koduje combo jako **osobną, piątą siatkę 8×8** wejścia do sieci — "Every turn the game becomes
five 8x8 grids: the board, one grid per piece in hand, and one holding the current combo streak."
https://github.com/Botkraker/block-blast-AI. To potwierdza **jakościowo**, że przynajmniej jeden
projekt uznał combo za część stanu wartościowanego (nie tylko część nagrody) — dokładnie to, o co
pyta kryterium ("czy wymaga combo jako części stanu"). README **nie podaje**, czy autor to
przetestował z wyłączonym grid combo (ablacja), więc nie mam dowodu, że to jest *konieczne*, tylko
że jeden autor tak zaprojektował system i osiągnął wynik 4,9× lepszy od zachłannej heurystyki w
swoim środowisku (**liczby niebezpośrednio porównywalne z naszą linią bazową** — inny zestaw
kształtów klocków ["27 fixed shapes" vs nasze `PIECE_POOL`, nieporównane w tym zadaniu], nieznana
zgodność wzoru punktacji z `scoring.py` `[D]`).

**Nasz wzór nagrody** `[D]`, z `scoring.py`: `punkty = combo_po_inkrementacji * B(l)`, `B(l)=0` dla
`l=0`, `10` dla `l=1`, `10·l·(l-1)` dla `l≥2`; combo rośnie bez ograniczenia górnego, dopóki
gracz czyści linię co najwyżej co `COMBO_COUNTER_BASE=3` postawienia bez czyszczenia. To znaczy,
że **wartość pojedynczego ruchu (czyszczącego linię) jest nieograniczona i zależy od historii
partii** (ile razy z rzędu gracz czyścił), nie tylko od aktualnego stanu planszy — struktura
identyczna do tego, co n-tuple/TD w 2048 i SZ-Tetris **nie muszą** obsługiwać (tam nagroda zależy
wyłącznie od bieżącego ruchu na bieżącej planszy, bez mnożnika zależnego od historii). **To jest
strukturalna różnica, nie zmierzona nigdzie w znalezionej literaturze** — n-tuple/TD w cytowanych
źródłach uczy się `V(s)` jako funkcji samej planszy; u nas, jeśli `combo` nie wejdzie do `s`
(np. jako dodatkowa "łata" albo osobna cecha numeryczna dodana do sumy LUT-ów), to `V` nie może
odróżnić planszy osiągniętej przy combo=0 od tej samej planszy przy combo=5, mimo że **wartość
oczekiwana kolejnego ruchu czyszczącego linię różni się o czynnik `combo`** — to jest silny,
strukturalny argument (mój wniosek, nie cytat) za tym, że `combo` **musi** wejść do stanu
wartościowanego, zgodnie z tym, co `Botkraker/block-blast-AI` faktycznie zrobił, ale bez
opublikowanego pomiaru "ile się traci, gdyby combo pominąć" ani u nas, ani w cytowanym repo.

---

## Cytaty

> Sieć "3333-4242": "4×16⁶=67,108,864 parameters"; sieć "421-4343": "5×16⁷=1,342,177,280 weights".
Źródło: https://ar5iv.labs.arxiv.org/html/1604.05085 (już cytowane w #94, powtórzone tu dla
porównania arytmetycznego w sekcji 1)

> Szubert and Jaśkowski employed TD(0) with 1 million training episodes to learn an
> afterstate-value function represented by a systematic n-tuple network. Their best function
> involved nearly 23 million parameters and scored 100,178 on average at 1-ply.
Źródło: streszczenie wyszukiwarki nad https://www.researchgate.net/publication/263198856

> Wu et al. later extended this work by employing TD(0) with 5 million training games to learn a
> larger systematic n-tuple system with 67 million parameters, scoring 142,727 on average.
Źródło: jw.

> a systematic n-tuple network involving more than 4 million parameters allowed the classical
> temporal difference learning algorithm to obtain similar average performance to VD-CMA-ES, but
> at 20 times lower computational expense [...] TD(0) learning achieved its results using
> 25-times smaller computational budget (4 million vs. 100 million games) [...] 294.8±1.4 lines
> on average
Źródło: streszczenie wyszukiwarki nad https://www.researchgate.net/publication/280043948
(GECCO 2015, Jaśkowski/Szubert/Liskowski, SZ-Tetris)

> the system requires a very rich initial feature set with more than half a million of weights
> and several millions of training games [...] Each board position will only activate 0.02%
> (≈2·70/650,000) of all active weights
Źródło: streszczenie wyszukiwarki nad https://www.gm.th-koeln.de/~konen/Publikationen/ppsn2012_RL-CFour.pdf
(Thill, Koch, Konen, PPSN 2012, Connect-4; PDF nieczytelny bezpośrednio w tej sesji)

> Every turn the game becomes five 8x8 grids: the board, one grid per piece in hand, and one
> holding the current combo streak.
Źródło: https://github.com/Botkraker/block-blast-AI

> [wyniki v3, PPO, afterstate policy] "1,436.8" mean score across 1,000 test games, "4.9x more
> than greedy" and "24x more than random" [...] "40 M moves"
Źródło: jw.

> [rshk941/block-blast-solver] "8x8 board" [...] 2-hidden-layer MLP "128 → 128 → 1" [...]
> TD bootstrapping with target network and Polyak averaging [...] "~800+ episodes" [...] "It does
> not yet reliably outperform a skilled human player."
Źródło: https://github.com/rshk941/block-blast-solver (już częściowo w `kierunek-algorytmiczny.md`,
tu z dodatkowymi liczbami architektury/epizodów)

> an 80% increase in training episodes yielded 130% improvement in max score [...] H-DQN, 9,000
> episodes: avg score 6,536.43, max score 41,828 [...] 5,000 episodes: avg score 5,693.67 [...]
> prior n-tuple approaches used "millions of episodes" versus this work's 5,000–9,000 episodes
Źródło: https://arxiv.org/html/2507.05465v1 (2048, architektura LSTM + rozkładowy DQN, 2025)

> LSTD [...] can be quadratic in the number of features [...] LSTD converged more quickly than TD
> since it reached the near-optimal solution [...] at the initial stage
Źródło: streszczenie wyszukiwarki nad https://ietresearch.onlinelibrary.wiley.com/doi/full/10.1049/cit2.12202

---

## Czego nie wiem

- **Nie ma wzoru episody(parametry) w literaturze N-tuple/TD** — to jest odpowiedź na kryterium 2,
  ale jest negatywna: przeszukałem wielokrotnie (różne sformułowania zapytań) i nie znalazłem
  żadnej publikacji, która wyprowadza budżet treningu z rozmiaru sieci; wszystkie znalezione
  budżety (10⁶, 5×10⁶, 10⁷, 4×10⁶) są opisane jako przyjęty limit obliczeniowy (dni maszynowe),
  nie jako wynik jakiegoś rachunku od `d`.
- **Przepustowość naszego symulatora** (kroki/s, partie/s) — poza budżetem tego zadania (nie
  uruchamiałem kodu); bez niej **żadna** z liczb epizodów/gier w tabelach sekcji 2 i 5 nie
  przekłada się na godziny CPU u nas. To jest pojedyncza najważniejsza brakująca liczba, żeby
  zamienić cokolwiek z tego raportu na plan.
- **Dokładny kształt/rozmiar łat w SZ-Tetris** (GECCO 2015) — wiem tylko ">4 mln parametrów",
  nie wiem `k` ani liczby łat, więc nie mogę bezpośrednio porównać gęstości pokrycia planszy z
  moimi wariantami A–D w sekcji 3 (czy SZ-Tetris pokrywa planszę gęściej/rzadziej niż moje
  propozycje) — PDF źródłowy nieczytelny w tej sesji, tylko nazwa pliku configu
  (`all-3x3_p1000_g100_CEM.properties`) sugeruje łaty 3×3 dla **innego** wariantu (CEM, nie TD).
- **Czy warianty łat A–D (sekcja 3) faktycznie się uczą** dla naszej mechaniki (usuwanie linii,
  tacka 3 klocków) — to jest czysta konstrukcja arytmetyczna, zero pomiaru; żadna z nich nie była
  testowana nawet na cudzym kodzie tej dokładnej gry.
- **Realny koszt aktualizacji TD na naszym symulatorze** (czas na krok wliczając obliczenie
  wszystkich aktywnych łat dla danego stanu) — nie zmierzony; literatura podaje tylko koszty dla
  cudzych silników (2048, SZ-Tetris, Connect-4), niekoniecznie proporcjonalne do naszego.
  `features.py` jest już zoptymalizowane bitowo `[D]`, ale to jest inny zestaw obliczeń (sześć
  cech skalarnych) niż odczyt `k`-bitowego wzorca z `2^k`-elementowej tablicy LUT dla każdej łaty
  — kosztu tego drugiego nie mierzyłem.
- **Czy ablacja "combo jako część stanu" kiedykolwiek była zmierzona** (przez kogokolwiek, w
  jakiejkolwiek grze z nieograniczonym mnożnikiem serii) — nie znalazłem takiego eksperymentu;
  mój wniosek w sekcji 6, że combo musi wejść do stanu, jest **rozumowaniem strukturalnym z
  definicji funkcji nagrody**, nie wynikiem pomiaru.
- **Zgodność zasad `Botkraker/block-blast-AI` (27 kształtów klocków, nieznany wzór punktacji)
  z naszym `scoring.py`/`PIECE_POOL`** — nie sprawdzałem tego 1:1 w tym zadaniu (poza budżetem —
  nie porównywałem repo cudzego kodu z naszym `pieces.py`), więc wynik "1436,8 śr., 4,9× zachłanna"
  jest **niebezpośrednio porównywalny** z naszym rekordem (6171 pkt/110,5 postawień) — inna waluta,
  zgodnie z ostrzeżeniem z `docs/calibration-assumptions.md`.
- **Pełna treść źródeł czytanych tylko przez streszczenia** (SZ-Tetris GECCO 2015, Connect-4 PPSN
  2012/CIG 2014, Bhandari-Russo-Singal COLT 2018, deep RL 2048 2507.05465) — żaden PDF nie
  otworzył się jako czysty tekst w tej sesji; wszystko `[Z]`, nie `[D]`, mimo że część cytatów
  wygląda jak dosłowne fragmenty.

**Czy odpowiedziałem na pytanie z issue**: częściowo, z jedną istotną luką negatywną wskazaną
wprost. Sprawdziłem rachunek `c=2` (poprawny, rząd wielkości 4–5,5, nie dokładnie 6) i policzyłem
cztery konkretne warianty łat dla 8×8 (4096–18432 wag, własna konstrukcja, oznaczona jako taka).
Na pytanie najważniejsze — zależność epizody(parametry) — odpowiedź jest **negatywna i
udokumentowana**: literatura N-tuple/TD nie ma takiego wzoru, budżety treningu są przyjmowanym
limitem obliczeniowym, nie wyprowadzoną liczbą; SZ-Tetris (najbliższy analog `c=2`, usuwanie
linii) potrzebowała epizodów tego samego rzędu co 2048 mimo dużo mniejszej sieci, co **podważa**
prostą intuicję "mniej wag = mniej epizodów". Znalazłem jeden mocny, zmierzony kontrprzykład na
"CMA-ES jest tańsze od TD" (SZ-Tetris: TD 20-25× taniej niż CMA-ES na tej samej reprezentacji) i
dwa przykłady "tańsze, ale słabsze" (PPO na Block Blast, deep RL na 2048, oba o 1-2 rzędy
wielkości mniej epizodów niż nasycone sieci n-tuple, kosztem gorszego wyniku). Na pytanie o
literaturę dla naszej dokładnej rodziny gier (usuwanie linii + `c=2`) odpowiedź jest w większości
negatywna — zapisana wprost jako wynik, nie jako brak wysiłku. Na pytanie o combo: literatura
naukowa milczy całkowicie; mam jeden precedens hobbystyczny (`Botkraker`, combo jako osobna siatka
wejścia) i własne, nieprzetestowane rozumowanie strukturalne, czemu combo prawdopodobnie musi
wejść do stanu. **Największa niezałatana luka, bez której nic z tego nie zamienia się w godziny
CPU**: przepustowość naszego symulatora — to jest jednoznaczne zadanie-pomiar dla kogoś z dostępem
do uruchamiania kodu, nie do mnie w tej roli.
