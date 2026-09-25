# Jak tanio oceniać zaszumionych kandydatów w CEM: CRN, racing, successive halving

Badanie do [#89](../../issues/89). Pytanie: jak tanio i uczciwie porównywać zaszumionych
kandydatów w CEM/ES, gdy jedna ocena kandydata to kilka partii gry o dużej wariancji wyniku.
**Decyzji, co z tego wdrożyć w `tools/tune_weights.py`, ten dokument nie podejmuje** — to
materiał dla orchestratora cyklu 6.

## Znaczniki

`[D]` — kod repo z Budżetu, przeczytany samodzielnie w całości (`tools/tune_weights.py`,
`docs/strojenie-wag.md`, `bench/config.json`). `[Z]` — twierdzenie z zewnątrz. Żadnego z
cytowanych źródeł zewnętrznych nie przeczytałem jako pełny tekst pierwotny — narzędzie do
pobierania stron nie potrafiło sparsować PDF-ów (NeurIPS 1993, AISTATS 2016, JMLR 2018,
Annals of OR 2005, IEEE TEC 2009 — próby udokumentowane w historii sesji), więc wszystkie
ustalenia z tych źródeł opierają się na streszczeniach wyszukiwarki albo na automatycznym
wyciągu z wersji HTML (arXiv/ar5iv) — **stąd `[Z]`, nie `[D]`, nawet tam, gdzie cytat wygląda
jak dosłowny fragment artykułu**. Wyjątek: dwa fragmenty z arXiv HTML (Successive Halving,
Hyperband) zawierają dosłowne wzory ze wzmianką numeru twierdzenia — potraktowane jako `[Z]`
mimo to, bo pośredniczyło w nich narzędzie streszczające, nie moja lektura.

---

## 0. Punkt startowy: co już jest w `tools/tune_weights.py`

`[D]`, przeczytane w całości:

- **CRN (common random numbers) już częściowo działa, przypadkiem.** `main()` woła
  `training_seeds()` raz, przed pętlą CEM (`tune_weights.py:161`), i przekazuje tę samą listę
  `seeds` do `run_cem` → `evaluate_candidate` dla **każdego** kandydata w **każdej** generacji
  (`tune_weights.py:75-82, 99-141`). To znaczy: każdy kandydat w całym przebiegu #81 był
  oceniany na dokładnie tych samych 6 seedach. To jest silniejsza forma CRN niż typowe
  „wspólne liczby losowe w obrębie jednej generacji" — tu wspólne są przez **cały przebieg**.
- To, co to kupuje: różnica średnich między dwoma kandydatami nie zawiera składnika „różne
  mapy", tylko czysto różnicę polityk na tych samych 6 mapach — klasyczny argument CRN (sekcja
  1 niżej). To, czego to **nie** kupuje: nie zmniejsza błędu standardowego *pojedynczego*
  oszacowania średniej kandydata względem populacji wszystkich możliwych seedów — 6 zawsze tych
  samych map to wciąż tylko 6 punktów danych, i `docs/strojenie-wag.md` (sekcja „Wynik") już to
  nazywa wprost: Δ=+237% zmierzone na tych samych seedach, na których trenowano, **nie mówi nic
  o generalizacji**.
- **Selekcja elity to czysta ranking-selekcja bez testu statystycznego**: `scored.sort(key=...)`,
  potem `scored[:elite_n]` (`tune_weights.py:127-128`) — żadnego porównania z progiem istotności,
  żadnej wiedzy o wariancji. To dokładnie sytuacja, którą opisuje pytanie z issue.
- **To nie jest pełne CMA-ES**, tylko prosty CEM: `update_distribution` liczy `mean`/`pstdev`
  niezależnie na cechę z surowej elity (bez wag rekombinacji, bez macierzy kowariancji, bez
  adaptacji rozmiaru kroku `cm`/`sigma`) — `tune_weights.py:89-96`. Reguły kciuka z literatury
  CMA-ES (sekcja 3) przenoszą się tu tylko częściowo, bo brakuje mechanizmów, które te reguły
  zakładają.
- Domyślne CLI to `population=24`, `elite=6` (`tune_weights.py:149-150`); przebieg #81 użył
  `population=14`, `elite=4` — mniejszej populacji i mniejszej elity niż domyślna, dobranych pod
  budżet czasowy, nie pod szum (`docs/strojenie-wag.md`, brak uzasadnienia statystycznego wyboru).

---

## 1. Common random numbers / paired evaluation

**Co to jest** `[Z]`: technika redukcji wariancji z symulacji dyskretnej — porównywane
warianty (tu: kandydaci wag) są oceniane na tych samych realizacjach losowości (tu: tych
samych seedach gry), zamiast na niezależnie losowanych. Cel: żeby zaobserwowana różnica
wyniku wynikała z różnicy polityk, nie z tego, że jeden kandydat trafił łatwiejsze mapy.
Źródła: przegląd technik redukcji wariancji w symulacji dyskretnej
(https://www.researchgate.net/publication/220136266_Discrete-Event_Simulation_Optimization_Using_Ranking_Selection_and_Multiple_Comparison_Procedures_A_Survey),
oraz klasyczna praca o modelach control-variate dla CRN w porównaniach wielokrotnych
(https://pubsonline.informs.org/doi/abs/10.1287/mnsc.39.8.989).

**Co dokładnie kupuje**: redukuje wariancję **różnicy** dwóch średnich, `Var(X̄_A - X̄_B)`,
o `2·Cov(X_A, X_B)` względem niezależnego próbkowania — im silniejsza dodatnia korelacja
wyników A i B na tej samej mapie (a taka korelacja jest naturalna: łatwa mapa daje wysoki
wynik obu politykom), tym większa redukcja. Nie zmienia to `Var(X̄_A)` osobno — to jest
redukcja szumu **porównania**, nie szumu **oszacowania**. `[Z]`

**Założenia**: (1) da się zsynchronizować strumień losowości między wariantami — u nas
trywialne, bo seed gry to jeden int przekazywany do `generator` (`policy.reset(seed)`,
`tune_weights.py:79`); (2) korelacja musi być **dodatnia** — w przeciwnym razie CRN pogarsza
wariancję różnicy zamiast ją zmniejszać `[Z]`
(https://demonstrations.wolfram.com/TheMethodOfCommonRandomNumbersAnExample/).

**Kiedy zawodzi**: (a) gdy korelacja wyników dwóch polityk na tej samej mapie jest słaba albo
ujemna — możliwe u skrajnie różnych wektorów wag na wczesnym etapie CEM (generacja 1 w #81:
`mean_score=3154` przy dużym rozrzucie startowego `std`), gdzie polityki mogą się bardzo różnić
zachowaniem na tej samej mapie; (b) CRN nie rozwiązuje problemu małej próby — u nas 6 map to
wciąż 6 map, a `docs/strojenie-wag.md` już zaznacza, że wynik na nich „nie mówi nic o
generalizacji"; (c) przy porównaniu **więcej niż dwóch** wariantów jednoczesna, ścisła
inferencja statystyczna z CRN robi się analitycznie trudna — stąd modele control-variate
cytowane wyżej jako osobne rozwinięcie problemu. `[Z]`

---

## 2. Racing: Hoeffding races, F-Race, Successive Halving

### 2.1 Hoeffding races (Maron & Moore, NeurIPS 1993)

**Co to jest** `[Z]`: dla każdego kandydata utrzymywany jest przedział ufności średniego wyniku,
budowany z **nieparametrycznej** nierówności Hoeffdinga (nie zakłada normalności, tylko
ograniczony zakres wyniku). Po każdej nowej próbce (tu: grze) przedziały są aktualizowane;
kandydat, którego górny kraniec przedziału leży poniżej dolnego krańca najlepszego dotychczas
kandydata, jest odrzucany z dalszego próbkowania.
Źródła: https://proceedings.neurips.cc/paper/1993/hash/02a32ad2669e6fe298e607fe7cc0e1a0-Abstract.html,
opis mechanizmu: https://www.semanticscholar.org/paper/Hoeffding-Races:-Accelerating-Model-Selection-for-Maron-Moore/ccc906c983f3492256bdb0d96849575883cc22d8.

**Wzór przedziału ufności** `[Z]` (znaleziony w formie ogólnej, nie z oryginalnego artykułu —
wariant cytowany w literaturze pochodnej): dla `t` próbek promień przedziału to w przybliżeniu
`c = R·√(ln(2nb/δ) / (2t))`, gdzie `R` to zakres możliwych wyników, `n` liczba kandydatów, `b`
związane z całkowitym limitem próbek, `δ` poziom ufności. Kluczowa własność: promień **maleje
jak `1/√t`**, ale **rośnie liniowo z `R`** — zakresem możliwych wyników, nie odchyleniem
standardowym.
Źródło ogólnego kształtu wzoru (nie oryginał Marona-Moore'a, praca pochodna o „Hoeffding and
Bernstein Races"): https://icml.cc/Conferences/2009/papers/229.pdf.

**Co dokładnie kupuje**: liczba próbek do odrzucenia wyraźnie gorszego kandydata rośnie tylko
`O(log n)` z liczbą kandydatów (bo `δ` trzeba podzielić między `n` testów, co wchodzi pod
logarytm), więc dodanie kolejnych kandydatów jest tanie — koszt całkowity zbliża się do kosztu
znalezienia najlepszego, nie do `n × pełna ocena`. `[Z]`

**Kiedy zawodzi**: (a) bound Hoeffdinga skaluje się z **zakresem** `R` wyniku, nie z jego
odchyleniem standardowym — u nas `docs/strojenie-wag.md` pokazuje wyniki od `mean_score=3154`
(generacja 1) do `elita_best=14736` (generacja 8), czyli zakres realnych wyników w jednym
przebiegu CEM jest rzędu **dziesiątek tysięcy**; nieprzycięty Hoeffding na takim `R` da przedział
ufności zbyt szeroki, by cokolwiek odrzucić przy 6 grach — races w tej postaci prawdopodobnie
nie zdążyłyby nic wyeliminować w naszym budżecie bez przycięcia/normalizacji zakresu wyniku,
czego oryginalny artykuł wymaga jako założenia (`Pr(Z∈[a,b])=1`); (b) races radykalnie tracą
sens, gdy prawdziwe wartości kandydatów są bliskie (typowa sytuacja właśnie w plateau z #81,
generacje 8-10: `14736,00 → 14486,83 → 14486,83`) — wtedy przedziały ufności nigdy się nie
rozejdą przy skończonym budżecie i wszystkie „przeżywają" do końca, race degeneruje się do
pełnej oceny. `[Z]`, wniosek własny z połączenia wzoru z liczbami z `docs/strojenie-wag.md` `[D]`.

### 2.2 F-Race (Birattari i in.)

**Co to jest** `[Z]`: race zaprojektowany wprost do strojenia parametrów algorytmów pod szumem
(nie do ogólnego doboru modelu jak Hoeffding races). Zamiast przedziału Hoeffdinga używa
nieparametrycznego testu Friedmana (blokowanego po instancji/seedzie — to wymaga CRN jako
elementu konstrukcji, nie opcji) do wykrycia, czy między przeżywającymi konfiguracjami jest
w ogóle istotna różnica; jeśli tak, kolejne testy parami odrzucają gorsze. Nowe „bloki"
(u nas: kolejne seedy) są dodawane sekwencyjnie, aż budżet się skończy albo zostanie jedna
konfiguracja. Źródła: https://www.researchgate.net/publication/2555802_A_Racing_Algorithm_for_Configuring_Metaheuristics,
przegląd: https://link.springer.com/chapter/10.1007/978-3-642-02538-9_13.

**Co dokładnie kupuje**: test Friedmana nie zakłada normalności rozkładu wyniku (istotne, bo
wynik Block Blasta jest silnie prawoskośny — `p10=160` przy średniej `705` z cytatu w issue, co
sugeruje rozkład daleki od symetrycznego) i wykorzystuje blokowanie po mapie (CRN), więc — wg
źródeł — jest **skuteczniejszy niż race oparty na teście t** w bezpośrednim porównaniu `[Z]`
(wzmianka w https://researchr.org/publication/MaronM93-pochodnych opisach F-Race, niepotwierdzona
liczbowo w dostępnych mi streszczeniach).

**Kiedy zawodzi**: (a) test Friedmana traci moc przy bardzo małej liczbie bloków (map) — jeśli
zacząć race od 1-2 seedów, statystyka nie ma szans wykryć różnicy nawet dużej, więc F-Race
wymaga sensownego minimum instancji startowych, zanim zacznie cokolwiek eliminować (dokładna
liczba minimalna nie jest podana w dostępnych mi streszczeniach — luka, patrz „Czego nie wiem");
(b) odrzucenie jest nieodwracalne — kandydat, który trafił pechowo słabe wczesne seedy, odpada
na stałe, nawet jeśli reszta rozkładu jest dla niego korzystna — to jest cena każdego race'u,
nie tylko F-Race; (c) wymaga, by CRN rzeczywiście dawało dodatnią korelację (patrz sekcja 1) —
jeśli nie, blokowanie nie pomaga i test traci sens konstrukcyjny. `[Z]`

### 2.3 Successive Halving — dwie różne rodziny, tylko jedna pasuje do naszego problemu

To rozróżnienie nie pojawiło się wprost w żadnym pojedynczym źródle, które czytałem — łączę
dwie osobne linie literatury, bo mylenie ich jest łatwe i konsekwentne (obie nazywają się
„successive halving"):

**(A) Successive Halving dla zaszumionych ramion o stałym budżecie** (Karnin, Koren, Somekh,
ICML 2013, „Almost Optimal Exploration in Multi-Armed Bandits") `[Z]` — to jest wariant
pasujący do naszego problemu: ramiona (kandydaci) dają **losowy, i.i.d.** wynik przy każdym
pociągnięciu (u nas: gra na losowym seedzie), a więcej pociągnięć = mniejszy szum oszacowania
średniej. Źródło: https://proceedings.mlr.press/v28/karnin13.html — **nie zdołałem odczytać
pełnej treści** (PDF nie sparsował się narzędziem), tylko streszczenie: algorytm dzieli budżet
na `⌈log₂ n⌉` rund, w każdej rundzie ocenia przeżywające ramiona dodatkowymi próbkami i odrzuca
gorszą połowę po średniej dotychczasowej.

**(B) Successive Halving dla ramion nie-losowych, zbieżnych w czasie** (Jamieson & Talwalkar,
AISTATS 2016, „Non-stochastic Best Arm Identification and Hyperparameter Optimization") `[Z]`
— to jest wariant do wczesnego zatrzymywania trenowania sieci (strata maleje deterministycznie
z liczbą epok, nie jest szumem próbkowania). **Ten wariant nie pasuje wprost do naszego
problemu** (jedna gra na jednym seedzie nie „zbiega" z kolejnymi próbami — to niezależne
próbki tego samego rozkładu, nie koszt-jakość jednego procesu), ale to on ma dostępny, dosłowny
wzór budżetu (przez fetch HTML z arXiv, https://arxiv.org/html/1502.07943v1, `[Z]`):

```
Wejście: budżet B, n ramion
Dla k = 0 ... ⌈log₂ n⌉ − 1:
  każde ramię w S_k dostaje r_k = ⌊B / (|S_k| · ⌈log₂ n⌉)⌋ dodatkowych prób
  odrzuć dolną połowę po sumarycznym wyniku
Wyjście: ostatnie ramię
```

Mechanika (podział budżetu na `⌈log₂ n⌉` rund, halving po każdej) jest identyczna w obu
wariantach A i B — różni je tylko **założenie o naturze sygnału** (i.i.d. szum vs. zbieżność w
czasie), stąd pożyczam ten wzór do zilustrowania mechaniki, jasno zaznaczając, że gwarancja
teoretyczna z (B) nie przenosi się na nasz przypadek.

**Co dokładnie kupuje (wariant B, dosłownie z artykułu)** `[Z]`: twierdzenie 1 artykułu mówi, że
przy budżecie `B` większym od pewnego progu zależnego od różnic strat między ramieniem 1 a
resztą, algorytm zwraca najlepsze ramię; przy heterogenicznych „prędkościach zbieżności" ramion
koszt jest rzędu `(n-1)·log₂(n)` razy **średnia** prędkość zbieżności, wobec `n razy
maksymalna` prędkość dla naiwnego przydziału równego — czyli oszczędność rośnie z tym, jak
bardzo ramiona różnią się jakością.

**Kiedy zawodzi**: (a) wariant B: **brak gwarancji, jeśli `B` jest poniżej progu identyfikacji**
— w najgorszym przypadku (twierdzenie 4 artykułu, `[Z]`) wynik jest tylko tak dobry, jak naiwny
przydział równy, więc przy zbyt małym budżecie SH nie jest gorszy, ale też nie jest lepszy;
(b) przy naszej skali (`n=14` kandydatów jak w #81) `⌈log₂14⌉=4` rundy — jeśli podzielić budżet
84 gier/generację (jak w #81) na 4 rundy i 14 ramion w pierwszej rundzie, to
`r₀=⌊84/(14·4)⌋=1` gra na kandydata w pierwszej rundzie — **poniżej sensownej rozdzielczości
szumu** dla gry o rozrzucie rzędu wartości średniej (patrz argument z issue: przy 6 grach błąd
już jest porównywalny z różnicami; przy 1 grze na kandydata pierwsza runda to czysty szum, nie
selekcja) — to jest bezpośrednie zagrożenie dla zastosowania SH tu bez zwiększenia budżetu albo
zmniejszenia liczby rund/kandydatów. `[Z]`+`[D]` (arytmetyka własna na parametrach #81).

### 2.4 Hyperband (Li, Jamieson, DeSalvo, Rostamizadeh, Talwalkar, JMLR 2018)

**Co to jest** `[Z]`: rozszerzenie successive halving (wariantu B, non-stochastic) o zewnętrzną
pętlę po różnych kompromisach „liczba ramion na start" vs „budżet na ramię", żeby nie trzeba
było zgadywać jednego `n` z góry — dla `n` za dużego traci się zbyt wcześnie dobre-ale-wolno-
zbiegające ramiona, dla `n` za małego traci się szansę na eksplorację. Źródło (dosłowny wyciąg
przez arXiv HTML, https://arxiv.org/html/1603.06560, `[Z]`): zewnętrzna pętla po `s` od `s_max`
do `0`, gdzie `s_max=⌊log_η(R)⌋`, `R` to maksymalny zasób na konfigurację, `η` (zwykle 3 lub 4)
kontroluje agresywność odrzucania.

**Co dokładnie kupuje**: raportowane przyspieszenia względem losowego przeszukiwania i
optymalizacji bayesowskiej rzędu **6×–70×**, zależnie od zadania `[Z]` (te same źródło).

**Kiedy zawodzi** — artykuł wprost wskazuje `[Z]`: (a) gdy optymalne hiperparametry **zależą od
przydzielonego zasobu** (np. najlepszy learning rate na 1 epoce różni się od najlepszego na 100
epokach) — wtedy wczesne zatrzymanie oparte na słabym zasobie systematycznie faworyzuje złych
kandydatów; **to jest realne ryzyko przeniesienia na nasz przypadek**, jeśli „zasobem" miałaby
być liczba gier — ale u nas gry to niezależne próbki tego samego rozkładu (nie „trening"), więc
ten konkretny tryb porażki dotyczy wariantu B/Hyperband, nie A; (b) gdy narzut na start
(`overhead`) jest duży względem czasu samej oceny — u nas koszt uruchomienia gry jest niewielki
względem czasu samej gry (symulator czysto pythonowy, brak sieci), więc to prawdopodobnie nie
dotyczy; (c) w przestrzeniach o niskiej wymiarowości losowe przeszukiwanie już radzi sobie
dobrze, więc zysk Hyperbanda jest mniejszy (`6×` zamiast `30-70×` w cytowanym eksperymencie
3-wymiarowym) — nasz wektor wag ma 6 wymiarów, więc to ostrzeżenie częściowo dotyczy skali
zysku, jakiego można by się spodziewać. `[Z]`

---

## 3. Trzecia technika (i czwarta): OCBA oraz uncertainty handling w CMA-ES

### 3.1 Optimal Computing Budget Allocation (OCBA, Chen i in.)

Wybrana jako trzecia technika, bo odpowiada **wprost** na pytanie z tytułu issue („jak tanio")
w postaci konkretnego wzoru na to, ile prób dać każdemu kandydatowi — czego ani CRN, ani racing
nie robi wprost (racing eliminuje/nie eliminuje, nie mówi „ile dokładnie dodać").

**Co to jest** `[Z]`: zamiast dzielić budżet gier równo między kandydatów (jak dziś: sztywne 6
gier/kandydata w #81), OCBA alokuje sekwencyjnie więcej prób kandydatom, których **różnica ze
zwycięzcą jest mała względem ich wariancji** — bo to oni decydują o poprawności selekcji.
Źródło: https://en.wikipedia.org/wiki/Optimal_computing_budget_allocation,
https://mason.gmu.edu/~cchen9/ocba.html.

**Wzór** `[Z]`: stosunek liczby prób między kandydatami `i, j` (przy założeniu, że żaden z nich
nie jest bieżącym liderem) to `Nᵢ/Nⱼ = (σᵢ/δ₁ᵢ)² / (σⱼ/δ₁ⱼ)²`, gdzie `δ₁ᵢ` to różnica średniej
lidera i kandydata `i`, `σᵢ` odchylenie standardowe wyniku kandydata `i`.

**Co dokładnie kupuje**: cytowany wynik liczbowy — ta sama jakość selekcji (prawdopodobieństwo
poprawnego wyboru najlepszego) przy **~1/10 budżetu obliczeniowego** względem przydziału
równego `[Z]` (twierdzenie generyczne z materiałów przeglądowych, nie zweryfikowane na naszym
problemie).

**Założenia**: (1) średnie próbkowe są w przybliżeniu normalne (z CLT — wymaga niemałego `n`
per kandydat, żeby to zadziałało); (2) wariancje `σᵢ` są znane albo estymowalne z próby wstępnej.

**Kiedy zawodzi**: (a) przy bardzo małej liczbie gier startowych (np. 2-3, jak w minimalnym
screeningu racingowym) sama estymata `σᵢ` jest tak niepewna, że alokacja oparta na niej może być
myląca — to jest problem typu „bootstrap": OCBA potrzebuje wstępnej próby, żeby dobrze
zaalokować resztę, a ta wstępna próba sama musi być wystarczająco duża; (b) rozkład wyniku
Block Blasta jest prawdopodobnie prawoskośny (cytat z issue: `p10=160` przy średniej `705` —
duży rozstęp dolny/środkowy sugeruje ogon w górę, nie symetrię), co łamie założenie o
normalności średniej próbkowej przy małych `n`; przy większym `n` (CLT) problem łagodnieje, ale
„jak dużym" nie jest tu ustalone. `[Z]` + wniosek własny o skośności z liczb w issue `[D]`
(dane pochodzą z treści issue, nie z osobnego pomiaru).

### 3.2 Uncertainty handling w CMA-ES (Hansen, Niederberger, Guzzella, Koumoutsakos, IEEE TEC 2009)

Czwarta technika, wybrana bo odpowiada wprost na pytanie z kryteriów akceptacji o dobór
parametrów CEM/CMA-ES pod szumem, a nie tylko o porównanie dwóch kandydatów.

**Co to jest** `[Z]`: zamiast ustalać z góry sztywną liczbę gier/kandydata, algorytm mierzy
**zaburzenie rankingu** — dorzuca dodatkowe oceny wybranym, już ocenionym osobnikom i sprawdza,
jak bardzo zmienia to ich pozycję w rankingu populacji; jeśli zaburzenie jest duże, dokłada
więcej prób *w tej generacji* i **wstrzymuje wzrost kroku (`sigma`)**, zamiast pozwolić szumowi
sterować adaptacją. Źródła:
https://www.researchgate.net/publication/220743287_Uncertainty_handling_CMA-ES_for_reinforcement_learning,
https://dl.acm.org/doi/10.1145/1569901.1570064. Ogólna zasada uśredniania (potwierdzona
niezależnie w przeglądzie algorytmów ewolucyjnych pod szumem): uśrednienie po `κ` niezależnych
ocenach zmniejsza siłę szumu o czynnik `√κ` `[Z]` (ogólna tożsamość statystyczna, niezależnie
cytowana w https://www.smapip.is.tohoku.ac.jp/~smapip/2003/hayashibara/proceedings/HajimeKita.pdf
i pokrewnych pracach o algorytmach ewolucyjnych z zaszumioną funkcją celu).

**Co dokładnie kupuje**: wg streszczeń — zapobiega **przedwczesnej zbieżności** (kolaps kroku
`sigma` wywołany szumem, nie prawdziwym zbieganiem do optimum) przy **małej liczbie dodatkowych
ocen** `[Z]`, bez podania dokładnej liczby w dostępnych mi streszczeniach.

**Kiedy zawodzi / ograniczenia**: (a) wymaga infrastruktury do **ponownej oceny tego samego
kandydata** i porównania zmiany rankingu — `tools/tune_weights.py` tego nie ma (każdy kandydat
oceniany raz, `evaluate_candidate` wywoływane raz na kandydata na generację,
`tune_weights.py:116-121`) — to nie jest więc podmiana jednej linijki, tylko zmiana architektury
pętli; (b) samo `update_distribution` w `tune_weights.py` nie ma adaptacji kroku (`sigma`) w
stylu CMA-ES — jest tylko `pstdev` z surowej elity — więc mechanizm „wstrzymaj wzrost sigma"
nie ma dokładnego odpowiednika do wpięcia bez dopisania adaptacji kroku, czego CEM tu nie robi.
`[D]` (na podstawie przeczytanego kodu) + `[Z]` (opis mechanizmu z zewnątrz).

---

## 4. Dobór `population`, `elite` i liczby ocen na kandydata w CEM/CMA-ES pod szumem

**Reguła kciuka na rozmiar populacji** `[Z]`, z tutorialu Hansena o CMA-ES
(https://arxiv.org/abs/1604.00772, wyciąg przez ar5iv HTML,
https://ar5iv.labs.arxiv.org/html/1604.00772): domyślny rozmiar populacji
`λ = 4 + ⌊3·ln(n)⌋`, gdzie `n` to liczba strojonych parametrów. Dla naszych **6 cech**
(`FEATURE_NAMES`, `features.py`, poza budżetem tego zadania, ale liczba cech jest podana wprost
w `docs/strojenie-wag.md`): `λ = 4 + ⌊3·ln(6)⌋ = 4 + ⌊5,37⌋ = 4 + 5 = 9`.

**Reguła kciuka na elitę** `[Z]`, ten sam tutorial: `μ ≈ λ/2` (liczba rodziców/elity to
połowa populacji), z wagami rekombinacji `wᵢ ∝ μ-i+1` (elita nie jest równoważona — lepsi
liczą się mocniej), oraz `μ_eff ≈ 3λ/8` jako „efektywny" rozmiar elity po ważeniu.

**Porównanie z #81** `[D]`: przebieg użył `population=14` (więcej niż domyślne `λ≈9` dla 6
cech — sensowna nadwyżka pod szum, bo więcej kandydatów w generacji to więcej niezależnych
prób rozkładu przy tej samej liczbie generacji) i `elite=4` (**29% populacji**, wyraźnie mniej
niż zalecane `μ≈50%`). To jest różnica, nie błąd — `update_distribution` w `tune_weights.py`
to **twarda selekcja obcinająca** (bierze surowe `mean`/`pstdev` z top-N), nie ważona
rekombinacja CMA-ES, więc reguła `μ≈λ/2` z CMA-ES (dobrana pod ważenie, gdzie słabsi z elity
i tak liczą się mniej) nie przenosi się wprost 1:1 — ale samo zjawisko „węższa elita = mniej
efektywnych próbek do estymacji `mean`/`std`, więc bardziej podatne na to, że o miejscu w
elicie decyduje szum, nie sygnał" jest tym samym zjawiskiem, które podejrzewa treść issue.

**Reguła na liczbę ocen na kandydata**: **literatura nie daje tu jednej stałej liczby** — ani
CMA-ES tutorial Hansena, ani tutorial CEM (de Boer i in. 2005, którego pełnej treści nie
zdołałem odczytać — PDF nie sparsował się narzędziem) nie podają wzoru „N gier wystarczy".
Konsensus jakościowy z kilku niezależnie znalezionych źródeł (UH-CMA-ES sekcja 3.2, przegląd
algorytmów ewolucyjnych pod szumem) jest spójny: **liczba prób powinna być adaptacyjna,
zależna od zmierzonego zaburzenia rankingu / wariancji, a nie stałą z góry** — bo sztywna liczba
albo marnuje budżet na kandydatów już oczywiście gorszych, albo wciąż nie wystarcza dla
kandydatów blisko granicy elity. `[Z]`. Jedyna twarda tożsamość matematyczna dostępna do
policzenia samemu: błąd standardowy średniej z `k` gier maleje jak `σ/√k` — więc np. podwojenie
liczby gier z 6 do 24 zmniejsza błąd standardowy o połowę, nie o połowę-i-więcej; to jest
malejący zwrot, klasyczny argument za tym, by nie inwestować dodatkowych gier równo we
wszystkich kandydatów, tylko selektywnie (racing/OCBA), zamiast podnosić globalną stałą
`games_per_candidate`. `[Z]` (tożsamość ogólna) + arytmetyka własna.

---

## 5. Przymiarka do naszego budżetu

Dane wejściowe z issue i `docs/strojenie-wag.md` `[D]`: **~22,6 gry/minutę**, budżet **~40 minut
CPU**. Weryfikacja arytmetyczna liczby z issue na danych #81 `[K]`: `840 gier / (2224,9 s / 60)
= 840 / 37,08 = 22,65 gry/min` — zgadza się z cytowanym „~22,6", licząc samemu z liczb w
`docs/strojenie-wag.md`.

**Budżet całkowity**: `22,6 × 40 = 904 gry` (vs. 840 gier w #81 na 37 min — niemal ten sam
rząd wielkości, tylko nieco więcej miejsca).

Trzy warianty, każdy z policzonymi konsekwencjami (nie jest to wybór — to są policzone
konsekwencje zastosowania reguł z sekcji 3-4 i 2 do naszych liczb, wybór między nimi to decyzja
orchestratora):

**Wariant A — populacja wg reguły CMA-ES, ten sam koszt/kandydata co w #81:**
`population=9` (reguła Hansena dla 6 cech), `elite=5` (`≈λ/2`), `games_per_candidate=6`
(niezmienione względem #81, bo żadne źródło nie uzasadnia innej stałej — sekcja 4) →
`9×6=54 gier/generację` → `904/54 ≈ 16 generacji` (vs 10 w #81, **+60% generacji** przy tym
samym budżecie i tej samej wiarygodności pojedynczej oceny).

**Wariant B — populacja jak w #81, dwustopniowy race zamiast płaskich 6 gier:**
`population=14` (jak #81), etap 1: wszyscy × 3 gry (`42 gry`, tanie odsianie), etap 2: awans
górnej połowy (`7` kandydatów, mechanika successive-halving z sekcji 2.3) × dodatkowe 3 gry
(`21 gier`) → przeżywająca elita ma **łącznie 6 gier** (tę samą wiarygodność co #81), a
odsiane 7 kosztuje tylko 3 gry zamiast 6 → `42+21=63 gry/generację` (vs 84 w #81, **-25%**)
→ `904/63 ≈ 14 generacji` (vs 10, **+40%**) przy tej samej dokładności oceny elity co #81.
Ryzyko z sekcji 2.3(b): 3 gry w etapie 1 to wciąż mało punktów danych — to jest miejsce, gdzie
technika może się nie sprawdzić bez pomiaru rzeczywistej wariancji wyniku na naszych seedach
(patrz „Czego nie wiem").

**Wariant C — bez zmiany parametrów CEM, budżet-nadwyżka na potwierdzenie zwycięzcy:**
`904 − 840 = 64 gry` wolne przy niezmienionych parametrach #81 → można nimi dograć np. 16
dodatkowych gier każdemu z 4 finalistów elity ostatniej generacji (`4×16=64`), zamieniając ich
ocenę z 6 gier na `6+16=22` gry — błąd standardowy średniej maleje z `σ/√6` do `σ/√22`, czyli
o czynnik `√(22/6)≈1,9`. To bezpośrednio adresuje podejrzenie z issue („czy plateau
`elita_best` w gen. 8-10 to zbieżność, czy szum") **bez zmiany samego przebiegu CEM** —
kosztem tego, że nie testuje niczego z sekcji 2-3, tylko dokłada gry po fakcie.

Żaden z wariantów nie jest tu wskazywany jako „ten właściwy" — każdy odpowiada na inny aspekt
pytania z issue (A: więcej generacji, ten sam szum na kandydata; B: taniej per generacja przy tej
samej pewności elity, kosztem ryzyka zbyt małego etapu 1; C: nic nowego w CEM, tylko pewniejsza
odpowiedź o tym, czy istniejący wynik #81 jest realny).

---

## Cytaty

> "Common random numbers, a variance reduction technique widely used in simulation, can be used
> to enhance the efficiency of some of the procedures."
Źródło: https://www.researchgate.net/publication/220136266_Discrete-Event_Simulation_Optimization_Using_Ranking_Selection_and_Multiple_Comparison_Procedures_A_Survey

> "The method of common random numbers does not always work and can backfire if the engineer
> creates a negative, rather than positive, correlation between the two random variables."
Źródło: https://demonstrations.wolfram.com/TheMethodOfCommonRandomNumbersAnExample/

> "Models whose confidence interval of the test error lies outside of at least one interval of
> a better performing model are dropped."
Źródło: https://www.semanticscholar.org/paper/Hoeffding-Races:-Accelerating-Model-Selection-for-Maron-Moore/ccc906c983f3492256bdb0d96849575883cc22d8

> "F-Race is a racing algorithm that starts by considering a number of candidate parameter
> settings and eliminates inferior ones as soon as enough statistical evidence arises against
> them" ... "a non-parametric Friedman test is used to check whether there are significant
> differences among the configurations."
Źródło: https://www.researchgate.net/publication/2555802_A_Racing_Algorithm_for_Configuring_Metaheuristics

> "Pull each arm in S_k for r_k = ⌊B/(|S_k|⌈log₂(n)⌉)⌋ additional times."
> "Theorem 1: If budget B > z = 2⌈log₂(n)⌉·max(i≥2) i·(1+γ̄⁻¹((ν_i−ν_1)/2)), the algorithm
> returns the best arm."
Źródło (wyciąg HTML): https://arxiv.org/html/1502.07943v1

> "Hyperband can provide over an order-of-magnitude speedup over our competitor set on a variety
> of deep-learning and kernel-based learning problems."
Źródło: https://arxiv.org/abs/1603.06560

> "These problems are particularly difficult for Hyperband, since the benefit of early-stopping
> can be muted" [gdy optymalne hiperparametry zależą od przydzielonego zasobu].
Źródło (wyciąg HTML): https://arxiv.org/html/1603.06560

> "N₂/N₃ = [(σ₂/δ₁,₂)²] / [(σ₃/δ₁,₃)²]" — reguła alokacji OCBA.
Źródło: https://en.wikipedia.org/wiki/Optimal_computing_budget_allocation

> "numerical results show that OCBA can achieve the same simulation quality with only one-tenth
> of the computational effort compared to traditional methods."
Źródło: https://en.wikipedia.org/wiki/Optimal_computing_budget_allocation

> "A simple and reasonable setting is wᵢ∝μ−i+1, and μ≈λ/2, where μ_eff≈3λ/8."
Źródło (wyciąg HTML): https://ar5iv.labs.arxiv.org/html/1604.00772

> "Choosing c_m<1 can be advantageous on noisy functions."
Źródło (wyciąg HTML): https://ar5iv.labs.arxiv.org/html/1604.00772

> "The proposed uncertainty handling ... is independent of the uncertainty distribution,
> prevents premature convergence of the evolution strategy and is well suited for online
> optimization as it requires only a small number of additional function evaluations."
Źródło: https://www.researchgate.net/publication/220743287_Uncertainty_handling_CMA-ES_for_reinforcement_learning

---

## Czego nie wiem

- **Rzeczywiste `σ` (odchylenie standardowe) wyniku `TrayPolicy` na naszych seedach treningowych
  ani na `bench/seeds_fixed.json`** — bez tej liczby żadna z reguł OCBA/racing/UH-CMA-ES z sekcji
  2-3 nie da się realnie zastosować (wszystkie zależą od `σ` per kandydat). To jest jedyna luka,
  którą rozstrzygnąłby wyłącznie pomiar u nas — nie literatura.
- Czy istniejące CRN w `tools/tune_weights.py` (te same 6 seedów przez cały przebieg #81) w
  praktyce **pomaga** selekcji elity bardziej, niż **szkodzi** generalizacji przez przeuczenie
  do 6 konkretnych map — literatura mówi, że oba efekty są realne i niezależne od siebie
  (sekcja 1), ale które dominuje tutaj, rozstrzygnąłby dopiero benchmark na 300 seedach
  (`tray:weights.json` vs `tray`), nieuruchomiony w tym zadaniu.
- Czy zakres wyniku (`R` w bound Hoeffdinga, sekcja 2.1) jest w praktyce na tyle duży, że
  Hoeffding races w nieprzyciętej formie faktycznie nic by nie eliminowały w naszym budżecie —
  to jest wniosek z arytmetyki na cudzym wzorze i naszych liczbach z `docs/strojenie-wag.md`,
  nie zmierzone bezpośrednio (nie uruchamiałem symulatora).
- Minimalna liczba bloków/seedów, przy której test Friedmana w F-Race (sekcja 2.2) ma w ogóle
  moc wykrywania różnicy — nie znalazłem tej liczby w dostępnych mi streszczeniach źródeł.
- Czy reguła `λ=4+⌊3·ln(n)⌋` (CMA-ES, dobrana dla gładkich, ciągłych krajobrazów optymalizacji)
  przenosi się sensownie na krajobraz zdefiniowany przez **zaszumiony, nieciągły w praktyce**
  wynik gry — żadne ze znalezionych źródeł nie adresuje wprost tej kombinacji (CMA-ES + bardzo
  drogi, silnie zaszumiony symulator gry planszowej).
- Pełna treść pięciu źródeł pierwotnych (Hoeffding races NeurIPS 1993, Jamieson & Talwalkar
  AISTATS 2016, Hyperband JMLR 2018, tutorial CE de Boer i in. 2005, UH-CMA-ES Hansen i in. IEEE
  TEC 2009) — narzędzie do pobierania stron nie sparsowało żadnego z tych PDF-ów w tej sesji;
  wszystkie twierdzenia z tych źródeł opierają się na streszczeniach wyszukiwarki albo
  wyciągach HTML z arXiv, nie na mojej bezpośredniej lekturze całości.
- Czy dokładnie 3 gry (Wariant B, etap 1, sekcja 5) wystarczą, by racing/successive-halving
  w ogóle sensownie odsiał dolną połowę kandydatów, czy to wciąż zbyt mało wobec realnego `σ` —
  bez zmierzonego `σ` to jest zgadywanie liczby, nie wniosek z literatury.

**Czy odpowiedziałem na pytanie z issue**: częściowo tak — opisałem i porównałem (kupuje/założenia/
kiedy zawodzi) cztery techniki (CRN, racing w trzech wariantach, OCBA, uncertainty handling
CMA-ES), podałem konkretne reguły doboru `population`/`elite`/gier-na-kandydata z literatury i
przeliczyłem trzy warianty budżetowe na nasze liczby (904 gry, 40 min). Nie rozstrzygnąłem
(i nie mogłem, w ramach mandatu „zaraportuj, nie mierz") **czy podejrzenie z issue — że elita z
6 gier to w dużej mierze losowanie zwycięzcy — jest prawdziwe u nas**: literatura mówi, jakie
narzędzia by to zweryfikowały (OCBA, racing, UH-CMA-ES), ale bez zmierzonego `σ` wyniku
`TrayPolicy` u nas żadne z nich nie da liczbowej odpowiedzi na to konkretne podejrzenie —
to zostaje w „Czego nie wiem" jako rzecz do rozstrzygnięcia wyłącznie pomiarem.
