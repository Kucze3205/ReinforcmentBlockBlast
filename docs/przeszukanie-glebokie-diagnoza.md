# Diagnoza: dlaczego głębsze przeszukiwanie `lookahead-ntuple` pogarsza wynik

Zadanie: [#202](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/202). **Zaraportuj, nie
naprawiaj** — `policies.py`, `ntuple.py`, `ntuple_native.*`, `benchmark.py`, `game.py`,
`generator.py`, `bench/*` nietknięte (`git diff --quiet origin/main -- ...` w `## Weryfikacja`
zielone).

**Wynik w jednym zdaniu:** drugi poziom (`samples`/`branch`/`inner_*`) szacuje wartość każdego
kandydata **maksimum z kilku próbek Monte Carlo**, a wybór najlepszego kandydata to **drugie**
`max` po tych już-zawyżonych szacunkach — to podręcznikowe „przekleństwo optymalizatora"
(optimizer's curse, Smith & Winkler 2006): im więcej alternatyw (`branch`) i im więcej operacji
`max` składających się na ocenę jednej alternatywy (`inner_beam`, `inner_depth`, `samples`), tym
mocniej wygrywa kandydat, któremu sprzyjał szum estymatora, nie ten naprawdę najlepszy — i tym
gorzej wypada rzeczywista decyzja. Pomiar niżej pokazuje to bezpośrednio: obciążenie ocenianego
kandydata rośnie **×2,1** (0,2375 → 0,4924, różnica ~9 se), a zgodność wybranej akcji z uczciwym
(nisko-wariancyjnym) wyborem spada z 70,7% do 63,5%, dokładnie między konfiguracją domyślną a
konfiguracją, która w #195 dała anomalię (19643 wobec 23292, −1,9 se).

## Jak dziś liczona jest wartość kandydata

`NTupleLookaheadPolicy` dziedziczy całą mechanikę przeszukania z `LookaheadPolicy`
(`policies.py:136`); różni się tylko źródłem wartości liścia (`_ntuple_leaf`,
`policies.py:311-313`, `ntuple.value(board)`) i tym, że `_search` (`policies.py:315-331`) najpierw
próbuje rdzenia natywnego `_tray_beam_search_native` (`policies.py:425-498`,
`ntuple_native.c:310-427`), a dopiero gdy ten zwróci `None`, liczy w Pythonie
(`_tray_beam_search`, `policies.py:334-402`).

Jedna decyzja (`LookaheadPolicy.act`, `policies.py:218-249`):

1. **Poziom pierwszy** (`policies.py:225-228`) — `_tray_beam_search`/`_tray_beam_search_native` z
   szerokością `beam`, na **bieżącej** tacce, do jej wyczerpania. Zwraca `frontier`: wiązkę stanów
   końcowych po **całej** tacce, każdy z polem `score = path_key + leaf(board)`.
2. **Kandydaci** (`_distinct_first_actions`, `policies.py:251-267`) — `branch` najlepszych stanów
   z `frontier`, po jednym na odrębną **pierwszą** akcję, posortowanych po `score` z kroku 1 (a
   więc **bez** udziału drugiego poziomu — selekcja, które akcje w ogóle dostaną drugi poziom,
   jest z definicji płytka).
3. **Fallback bez drugiego poziomu** (`policies.py:232-233`) — gdy `samples <= 0` albo kandydatów
   jest mniej niż 2, zwraca po prostu `max(frontier, key=score)["first_action"]`. To jedyne
   miejsce, gdzie liczy się `frontier`'owy `score` bezpośrednio jako decyzja — i **nigdy** nie jest
   mieszane z wynikiem drugiego poziomu w jednym porównaniu (patrz Hipoteza 1 niżej).
4. **Węzeł losowy + poziom drugi** (`policies.py:235-249`) — `samples` wspólnych losowań
   `self._sampler.next_pieces()` (ta sama trójka dla wszystkich kandydatów tej decyzji). Dla
   każdego kandydata i każdej próbki: płytsze przeszukanie `_search(..., self.inner_beam,
   depth=self.inner_depth)` na **świeżym** stanie ścieżki (`gain`/`placed` zaczyna od 0 —
   `_tray_beam_search`, `policies.py:364-372`), a z jego wiązki bierze się
   `max(inner, key=score)["score"]` (`policies.py:245`) — to jest **drugie** `max` na tym torze.
   Wartość kandydata (`policies.py:246`):

       value = state[path_key]            # suma ścieżki pierwszej tacki (krok 1)
             + mean_over_samples(          # średnia po `samples` próbkach
                   max_over_inner_beam_search(   # max po wiązce drugiego poziomu
                       path_key drugiej tacki + leaf(board po niej)
                   )
               )

   Zwycięzcą (`policies.py:247-249`) jest kandydat o **największym** `value` — trzecie `max`, tym
   razem po `branch` już uśrednionych, ale wciąż **zawyżonych** (patrz niżej) ocenach.

## Sprawdzenie hipotez 1–4

### Hipoteza 1 — porównanie wartości z różnych głębokości

**Dosłownie obalona, mechanizm pokrewny potwierdzony pomiarem.**

Dosłowne mieszanie „kandydat rozwinięty na drugi poziom" i „kandydat oceniony tylko liściem" w
jednym `max` **nie występuje** — kod czyta się jednoznacznie: gdy `samples > 0` i kandydatów jest
≥ 2 (czyli w każdej z anomalnych konfiguracji z #195), **wszyscy** kandydaci z `branch` przechodzą
**identyczne** traktowanie w kroku 4 (te same `samples` próbek, ten sam `inner_beam`/`inner_depth`);
fallback z kroku 3 to osobna gałąź `if`/`return`, nigdy współistniejąca z krokiem 4 w jednej
decyzji. Zwycięzca zawsze wychodzi z jednego, spójnego `max(value)` po `branch` kandydatach ocenionych
tym samym wzorem.

To, co jednak **jest** prawdziwym problemem — i co dosłowna hipoteza 1 uchwyciła intuicyjnie, tylko
w złym miejscu — to fakt, że *selekcja*, które akcje w ogóle dostają drugi poziom (krok 2), idzie
po **płytkim** `score` z kroku 1 (bez lookahead), podczas gdy finalna decyzja idzie po **głębokim**
`value` z kroku 4. Gdy `branch` jest mały (2, jak domyślnie), to niegroźne — prawie zawsze wygrywa
i tak jeden z 2 najlepszych płytkich kandydatów. Gdy `branch` rośnie (3, 4, 8...), rośnie też liczba
alternatyw ocenianych **szumowym** estymatorem (krok 4 to Monte Carlo na `samples` próbkach, nie
pełna suma po rozkładzie tacki), a wybór *między* nimi to `max` po tym szumie — klasyczne
przekleństwo optymalizatora: `E[max_i(true_i + szum_i)] >= max_i(true_i)`, i różnica rośnie z
liczbą alternatyw `i` (tu: `branch`) oraz z wariancją każdej `szum_i` (tu: rośnie, gdy mniej
uśredniamy na jedno `max` — czyli maleje z `samples`, ale rośnie z `inner_beam`/`inner_depth`,
bo szerszy/głębszy wewnętrzny `max` sam jest bardziej zawyżony).

**Pomiar** (`tools/diagnose_lookahead_ntuple_search.py`, wagi `ntuple/survival-ad-70k.json`, 40
partii, seedy rozłączne z `bench/seeds_fixed.json` i z solą `tools/measure_ntuple_search_grid.py`
(`diag-202` vs `siatka-195`), `beam=8` stałe w obu konfiguracjach — dokładnie wiersz domyślny i
wiersz anomalii z #195):

Metoda: w każdej decyzji, gdzie polityka faktycznie używa drugiego poziomu, licznik powtarza krok
4 identycznie jak `act` (na tym samym `self._sampler`, więc gra idzie dalej tak samo jak przy
zwykłym `policy.act`), a dla **każdego** kandydata z `branch` dokłada niezależną, dużą próbkę
(„holdout", osobny `Generator`, 24 próbki, nie rusza `self._sampler`) tej samej estymacji.
`obciążenie` = wartość z decyzji (małe `samples`) minus wartość z holdoutu (duże, niskowariancyjne
`samples`) dla **wybranego** kandydata; `agree` = czy wybór z małej próby zgadza się z wyborem,
który dałby fair porównanie po holdoucie wszystkich kandydatów.

| konfiguracja | partii | decyzji z 2. poziomem | średni wynik | średnie przeżycie | śr. obciążenie wybranego | se obciążenia | zgodność z uczciwym wyborem |
|---|---:|---:|---:|---:|---:|---:|---:|
| domyślna `beam=8 s=2 b=2 in=1×1` | 40 | 12 548 | 29 459,60 | 323,05 | **0,2375** | 0,0179 | **70,70%** |
| `beam=8 s=4 b=3 in=2×2` (anomalia #195) | 40 | 11 993 | 24 009,20 | 310,12 | **0,4924** | 0,0205 | **63,47%** |

Różnica obciążenia: 0,4924 − 0,2375 = 0,2549, se złożone √(0,0179² + 0,0205²) ≈ 0,0272 → **Δ/se ≈
9,4** — jednoznacznie odróżnialne. Kierunek zgadza się z wynikiem partii (24 009 wobec 29 460 na
tych samych 40 seedach, z tym samym `beam`): większe obciążenie estymatora idzie w parze z gorszą
faktyczną grą i z **niższą** zgodnością wybieranej akcji z tym, co wybrałby estymator o mniejszej
wariancji. To jest ten sam mechanizm i ten sam kierunek, co anomalia w #195 (19 643 wobec 23 292
na `s=4 b=3 in=2×2` wobec domyślnej) — inne seedy, ten sam efekt.

### Hipoteza 2 — rozkład wylosowanych tacek w przeszukaniu różny od `generator.py`

**Obalona, bez potrzeby pomiaru.** `policies.py:12` importuje `from generator import Generator` —
dokładnie tę samą klasę, z tym samym `PIECE_TYPE_WEIGHTS` po kalibracji #186, której używa gra
(`game.py:9,21`, `self.generator = Generator(seed)`). `LookaheadPolicy.reset`
(`policies.py:206-209`) tworzy `self._sampler = Generator(seed=...)` — nowa instancja tej samej
klasy, nie osobna implementacja ani starsza kopia rozkładu. Nie ma dwóch rozkładów do porównania.

### Hipoteza 3 — obsługa tacki niegrywalnej na drugim poziomie

**Obalona jako przyczyna anomalii** (efekt istnieje, ale nie różni się między konfiguracjami).
`_tray_beam_search` (`policies.py:384-386`) i jego natywny odpowiednik (`ntuple_native.c:376-383`,
`if (!any) { cand[n] = *st; ...}`) przy braku legalnej akcji **nie karzą** — przenoszą stan bez
zmian do następnego poziomu, z tym samym `score`, co jego rodzic. #92 zmierzyło to zjawisko na
domyślnych parametrach (`inner_depth=1`) jako niewystępujące (0/2488); z głębszym `inner_depth`
(pełniejsze rozegranie próbkowanej tacki) rzeczywiście występuje, ale w **podobnej** proporcji w
obu konfiguracjach:

Pomiar (`NTUPLE_NATIVE=0`, żeby liczyć w Pythonie i widzieć `_tray_legal_actions` bezpośrednio —
rdzeń natywny liczy bitowo to samo, potwierdzone testem niżej; wagi `ntuple/survival-ad-70k.json`,
8 partii, sól `diag202-h3`, sufit 500 postawień):

| konfiguracja | wywołań `_tray_legal_actions` | z nich pusta lista | udział |
|---|---:|---:|---:|
| domyślna `beam=8 s=2 b=2 in=1×1` | 19 226 | 101 | 0,53% |
| `beam=8 s=4 b=3 in=2×2` | 49 060 | 233 | 0,47% |

Udział jest **nieznacznie niższy**, nie wyższy, w konfiguracji anomalnej — gdyby to on odpowiadał
za spadek wyniku, kierunek byłby odwrotny. Zdarzenie jest realne, ale rzadkie i stałe względem
głębokości/szerokości przeszukania — nie jest dźwignią, która rośnie z `samples`/`branch`/`inner_*`
i tłumaczy obserwowaną skalę anomalii.

### Hipoteza 4 — niezgodność ścieżki natywnej i Pythonowej dla `inner_depth > 1` albo `inner_beam > 1`

**Obalona, pokryta istniejącym testem.** `tests/test_ntuple_native.py::TestSearchEquivalence::
test_random_states_match_python_search` porównuje `_tray_beam_search_native` z
`_tray_beam_search` na 300 losowych stanach gry, z `depth` losowanym z `{None, 1, 2, 3, 4}` i
`beam` z `{1, 2, 8, 30}` (a więc pełne pokrycie `inner_depth ∈ {1,2,3}` i `inner_beam ∈ {1,2}`
używanych w siatce #195, plus zapas), dla obu `path_key`. Test przechodzi dziś (uruchomiony jako
część tego zadania: `python3 -m unittest tests.test_ntuple_native.TestSearchEquivalence -v` →
3/3 OK). Rdzeń natywny nie jest więc źródłem anomalii — wynik jest bit w bit identyczny z Pythonem
dla dokładnie tych głębokości i szerokości drugiego poziomu, które siatka #195 przetestowała.

## Przyczyna w jednym zdaniu

Drugi poziom `lookahead-ntuple` szacuje wartość każdego z `branch` kandydatów jako średnią z
`samples` operacji `max` po `inner_beam`/`inner_depth`-głębokim przeszukaniu próbkowanej tacki, a
finalna decyzja to kolejne `max` po tych już-zawyżonych szacunkach — klasyczne przekleństwo
optymalizatora, którego siła rośnie z `branch` (więcej alternatyw do wybrania) i z
`inner_beam`/`inner_depth` (więcej zagnieżdżonych `max` w ocenie jednej alternatywy), zmierzone
bezpośrednio jako wzrost obciążenia wybranego kandydata (×2,1) i spadek zgodności z uczciwym
wyborem (70,7% → 63,5%) między konfiguracją domyślną a anomalną z #195. To nie jest usterka
specyficzna dla N-tuple ani dla rdzenia natywnego (oba obalone wyżej) — to własność samej
struktury przeszukania (`LookaheadPolicy.act`), widoczna już w #92 na ręcznie strojonych wagach
przed wprowadzeniem N-tuple (`docs/lookahead.md`: „Głębiej nie znaczy lepiej", `in=2×2`/`in=1×3`
droższe i gorsze od `in=1×1` na tej samej, starszej wersji tego samego kodu). N-tuple tylko
odziedziczyło strukturalną wadę, nie wprowadziło nowej.

## Propozycja poprawki (proza, bez zmiany kodu polityki)

Dwa niezależne kierunki, żadnego z nich to zadanie nie wdraża:

1. **Rozdzielić próbki wyboru od próbek oceny (podział trenuj/testuj).** Zamiast wybierać zwycięzcę
   i raportować jego wartość z tych samych `samples` losowań, użyć jednej połowy próbek do wyboru
   `argmax`, a drugiej — niezależnej — do przypisania mu ostatecznej wartości (albo, taniej: po
   znalezieniu zwycięzcy dociągnąć małą, świeżą domiarkę tylko dla niego). To nie usuwa obciążenia
   w wyborze (wciąż wybieramy kandydata, któremu sprzyjał szum pierwszej połowy), ale usuwa
   **podwójne liczenie** tego samego szumu w ocenie i w selekcji, które dziś zawyżają się wzajemnie.
   Spodziewany efekt: mniejsze `obciążenie wybranego` w tabeli wyżej, bo estymator przestaje być
   sędzią we własnej sprawie.
2. **Nie rozszerzać `samples`/`branch`/`inner_*` — rozszerzać `beam`.** Pierwszy poziom nie ma tego
   problemu w tym samym stopniu: ocenia **rzeczywiste**, w pełni zdeterminowane stany końcowe
   bieżącej (znanej) tacki, więc poszerzenie `beam` to więcej **prawdziwych** kandydatów do
   obejrzenia, nie więcej zagnieżdżonych uśrednień szumu nad **hipotetyczną** przyszłą tacką. To
   dokładnie odtwarza wniosek #195 (`docs/przeszukanie-siatka.md`: `beam` sam w sobie daje
   +91,5% za ×2,3 kosztu, drugi poziom nic nie dokłada), tylko z mechanizmem: drugi poziom nie jest
   z natury bezużyteczny (bez niego `TrayPolicy` nie widzi w ogóle przyszłej tacki — #92), ale jego
   **poszerzanie ponad już-działający minimalny kształt** (`samples=2, branch=2, inner=1×1`) kupuje
   przede wszystkim więcej szumu do zmaksymalizowania, nie więcej sygnału. Praktyczna rekomendacja:
   traktować `docs/przeszukanie-siatka.md`'s `do_benchu` (dźwignia na `beam`) jako właściwy kierunek,
   a nie szukać dalej w stronę głębszego/szerszego drugiego poziomu bez wdrożenia poprawki (1).

## Nietknięte pliki

`policies.py`, `ntuple.py`, `ntuple_native.c`, `ntuple_native.py`, `benchmark.py`, `game.py`,
`generator.py`, `bench/*` — bez zmian (`git diff --quiet origin/main -- policies.py ntuple.py
ntuple_native.c ntuple_native.py benchmark.py game.py generator.py` → `nietkniete`).
`reward_shape_changed: no`.

Narzędzia użyte do pomiarów tego zadania: `tools/diagnose_lookahead_ntuple_search.py` (hipoteza 1,
mechanizm rzeczywisty); pomiar hipotezy 3 to jednorazowy licznik na `_tray_legal_actions`, nie
warty osobnego pliku w `tools/` (zero trwałej wartości powtórzenia — hipoteza obalona, liczba
zdarzeń stała względem konfiguracji).
