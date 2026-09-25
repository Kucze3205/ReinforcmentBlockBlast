# Kara terminalna i sygnał przeżycia — co wiadomo spoza repo

Raport dla issue [#53](../../issues/53). Odpowiada na trzy pytania osobno. Nie proponuje
implementacji ani decyzji — to należy do orchestratora.

Znaczniki: `[Z]` — zweryfikowane źródło z linkiem (cytat lub jednoznaczne stwierdzenie z tego
źródła). `[H]` — hipoteza albo moje domniemanie, w tym ekstrapolacja z jednej domeny na drugą.

## Grunt z repo (nie literatura, ale punkt odniesienia)

`[Z]` `game.py:47-61` — `step()` zwraca `-5` w dwóch gałęziach: gdy `piece is None or not
self.board.place_piece(...)` (ruch nielegalny) i gdy `not self._can_place_any()` po udanym
postawieniu (naturalny koniec partii — plansza 8×8, brak timera, koniec wtedy i tylko wtedy,
gdy żadnego klocka z tacki nie da się postawić). W drugiej gałęzi `gained` z tego samego kroku
jest liczone (`apply_placement`) i **nie jest zwracane** — nagroda za ostatnie, udane
postawienie partii przepada.

`[Z]` Issue [#23](../../issues/23), rozstrzygnięcie właściciela (komentarz OWNER,
2 sierpnia–wrzesień 2026, treść pobrana z GitHub API): nagroda = przyrost wyniku, shaping
usunięty; obie kary `-5` pozostają **nieratyfikowane**; sygnał przeżycia i te kary należą do
orchestratora, nie do tego biletu. Właściciel nazywa wprost oba problemy z tego raportu:
zgubioną nagrodę w kroku terminalnym i kolizję dwóch zdarzeń pod jedną wartością `-5`.

> `game.step` **wyrzuca punkty za ostatnie postawienie partii**. (...) Skutek: „nagroda =
> przyrost wyniku" **nie jest prawdą w kroku terminalnym** (...) Drugi problem w tej samej
> gałęzi: `-5` znaczy jednocześnie „błędny ruch agenta" i „normalny koniec partii" — dwie
> różne rzeczy pod jedną liczbą.
> — [issue #23, komentarz OWNER](../../issues/23)

To ustala zakres pytań (a) i (b) jako już nazwany przez właściciela problem, a nie
domniemanie researchera.

## (a) Kara terminalna w zadaniach z naturalnym końcem epizodu

Nasza gra nie ma timera i kończy się wyłącznie strukturalnie (brak legalnego ruchu) — to
klasyczna **terminacja środowiskowa** (ang. *environmental/true termination*), różna od
**terminacji przez limit kroków** (*time-limit/timeout termination*), gdzie epizod ucina się
sztucznie mimo że zadanie mogłoby trwać dalej.

`[Z]` Pardo, Tavakoli, Levdik, Kormushev, *Time Limits in Reinforcement Learning*, ICML 2018
([arXiv:1712.00378](https://arxiv.org/abs/1712.00378)) rozróżniają te dwa przypadki wprost i
przypisują im różne traktowanie bootstrapu wartości. Dla terminacji środowiskowej cel
uczenia to `y = r` — **bez bootstrapu** z wartości stanu następnego (co w praktyce oznacza
wartość stanu terminalnego = 0, a nie osobną karę doliczaną do `r`). Dla terminacji przez
limit czasu autorzy zalecają kontynuować bootstrap, bo epizod mógłby trwać dalej:

> "In the case of bootstrapping methods, we argue for continuing to bootstrap at states
> where termination is due to the time limit."
> — [Pardo i in. 2018](https://arxiv.org/abs/1712.00378) (treść pobrana przez ar5iv,
> parafraza/cytat pośredniczony przez narzędzie WebFetch — patrz „Czego nie udało się
> ustalić")

Wniosek z tego papieru dotyczy **rozróżnienia sposobu bootstrapu**, nie wprost tego, czy
dokładać osobną karę liczbową do nagrody w kroku terminalnym. Nasza gra pasuje do kategorii
„terminacja środowiskowa" (brak timera), więc wniosek o kontynuowaniu bootstrapu przy
timeoutach **nie ma zastosowania** — to jest właśnie rozróżnienie, którego wymaga kryterium
akceptacji tego raportu.

`[H]` Standardowa formalizacja epizodycznego MDP (Sutton & Barto) traktuje stan terminalny
jako pochłaniający, z wartością zerową „z definicji" — sam brak przyszłych nagród już koduje
„to jest gorsze niż przeżycie", bez potrzeby jawnej kary. To dokładnie hipoteza „kara
terminalna bywa redundantna", o którą pyta issue — piszę ją jako `[H]`, bo nie znalazłem
źródła, które nazywa ją tym mianem explicite; wynika z definicji wartości stanu terminalnego
w standardowej teorii, nie z eksperymentu.

Przeciwwagą jest praca o „self punishment":

`[Z]` Wang i in., *Self Punishment and Reward Backfill for Deep Q-Learning*
([arXiv:2004.05002](https://arxiv.org/abs/2004.05002)) argumentują, że w wielu środowiskach
testowanych DQN nie ma żadnego sygnału za przegraną, i że to bywa niewystarczające, bo agent
nie odróżnia stanu neutralnego od niepożądanego, gdy przyszła nagroda i tak wynosi zero
w obu:

> "Majority of environments, however, tested with DQN variants do not provide signals for
> loosing or for a terminal state." (...) "the lack of positive punishment (...) makes it
> impossible for the agent to distinguish between a neutral state (...) and an undesirable
> one"
> — [Wang i in. 2020](https://arxiv.org/abs/2004.05002)

Dodanie kary `p` w terminalu (`r(s,a) - p`) poprawiło wyniki w >65% z 8 testowanych gier
Atari, miejscami dużo. `[H]` Środowiska Atari w tym badaniu to w większości zadania z
nagrodą rzadką/sparse i pośrednim relatywnie do naszej gry sygnałem punktowym; nasza gra ma
gęstą nagrodę (punkty po każdym postawieniu, `game.py:54`), więc argument „agent nie widzi
różnicy między stanem neutralnym a złym" ma słabszą podstawę tutaj niż w Atari — to moja
ekstrapolacja, nie coś zmierzone w cytowanej pracy dla tego typu gry.

**Podsumowanie (a):** literatura nie jest zgodna. Formalna strona teorii RL (Pardo i in.,
i standardowa definicja MDP) traktuje terminację środowiskową jako `y = r`, wartość=0, bez
dodatkowej kary — nieobecność przyszłej nagrody już jest „karą". Praca empiryczna o
self-punishment pokazuje, że w praktyce (przynajmniej w Atari, nagroda rzadka) dołożenie
jawnej kary bywa korzystne. Żadne z tych źródeł nie testowało gry typu Block Blast (nagroda
gęsta, brak timera, terminacja czysto strukturalna).

## (b) Ta sama liczba dla dwóch zdarzeń: ruch nielegalny i naturalny koniec epizodu

`[Z]` Huang & Ontañón, *A Closer Look at Invalid Action Masking in Policy Gradient
Algorithms* ([arXiv:2006.14171](https://arxiv.org/abs/2006.14171)) porównują maskowanie
nielegalnych akcji (wielka ujemna wartość na logicie przed softmax) z karaniem ich w
nagrodzie (`r_invalid`). Maskowanie skaluje się z rozmiarem przestrzeni akcji, kara — nie:

> "Invalid action masking is shown to scale well as the number of invalid actions increases"
> (...) "Invalid action penalty is able to achieve good results in 4×4 maps, but it does not
> scale to larger maps."
> — [Huang & Ontañón 2022](https://arxiv.org/abs/2006.14171)

oraz hiperparametr kary jest trudny do dobrania i przy dużej wartości bezwzględnej ma efekt
odwrotny do zamierzonego:

> "the hyper-parameter r_invalid can be difficult to tune. Although having a negative
> r_invalid did encourage the agents not to execute any invalid actions, setting r_invalid =
> -1 seems to have an adverse effect"
> — [Huang & Ontañón 2022](https://arxiv.org/abs/2006.14171)

Ta praca **nie testuje** wprost scenariusza „ta sama wartość koduje dwa różne zdarzenia" z
pytania (b) — jej porównanie to maskowanie vs. kara za nielegalny ruch, nie kolizja
nielegalny-ruch/koniec-gry. Nie ma tam więc bezpośredniej odpowiedzi na (b), tylko na
sąsiedni problem (czy w ogóle karać nielegalne ruchy w nagrodzie).

Bezpośrednio do (b) odnoszą się publicznie dostępne (niepublikowane naukowo, hobbystyczne)
implementacje RL dla samego Block Blasta:

`[Z]` [rfahd1525/Block-Blast-AI-Reinforcement-Learning-Agent](https://github.com/rfahd1525/Block-Blast-AI-Reinforcement-Learning-Agent)
— PPO z Action Masking; README: "Invalid moves receive -∞ logits, ensuring the agent only
samples valid placements" — nielegalne ruchy nigdy nie docierają do funkcji nagrody, więc nie
mogą kolidować z żadną inną wartością nagrody.

`[Z]` [Botkraker/block-blast-AI](https://github.com/Botkraker/block-blast-AI) — README (wersja
v3, treść pobrana przez WebFetch z widoku github.com, nie z surowego pliku — patrz „Czego nie
udało się ustalić"):

> "reward per move = 1 - (filled cells / 64) - 20 if the game just ended" (...) "Illegal moves
> (overlapping blocks, pieces falling off the board) are masked out, so it only ever chooses
> among legal ones."
> — [Botkraker/block-blast-AI README](https://github.com/Botkraker/block-blast-AI)

Wzorzec z obu repo: **rozdzielenie strukturalne, nie liczbowe**. Legalność ruchu obsługuje
interfejs polityki (maska nad akcjami dostępnymi), a wartość nagrody „koniec gry" (`-20` w
tym repo) jest jedynym zdarzeniem, które w ogóle dociera do nagrody terminalnej — nie ma
więc przestrzeni, w której obie rzeczy współdzieliłyby jedną liczbę.

`[H]` Nie znalazłem żadnego źródła (naukowego ani z tych repo), które explicite dyskutuje
przypadek „ta sama liczba dla dwóch zdarzeń jest błędem i oto dlaczego" — to co powyżej to
moje wnioskowanie z tego, że we wszystkich znalezionych implementacjach tego typu gry problem
w ogóle nie występuje, bo architektura go wyklucza z góry (maskowanie), a nie dlatego, że
ktoś rozdzielił dwie różne kary liczbowo.

**Podsumowanie (b):** literatura o maskowaniu akcji odpowiada na pytanie „karać nielegalny
ruch w nagrodzie, czy maskować" (odpowiedź: maskowanie skaluje się lepiej, kara ma problem ze
strojeniem) — ale to inne pytanie niż kolizja dwóch zdarzeń pod jedną wartością. Na kolizję
bezpośrednio odpowiadają tylko hobbystyczne implementacje Block Blasta, wszystkie przez
wykluczenie: maskowanie usuwa nielegalny ruch z przestrzeni nagrody, więc kolizja nie może
powstać.

## (c) Jawny sygnał za przeżyty krok w grach typu Tetris/1010!/Block Blast

Nie znalazłem recenzowanej pracy naukowej, która badałaby explicite wielkość jawnego
składnika „za przeżyty krok" w Tetris, 1010! albo Block Bloście i jej wpływ na zachowanie —
patrz „Czego nie udało się ustalić".

`[Z]` [Botkraker/block-blast-AI](https://github.com/Botkraker/block-blast-AI), ta sama gra co
w repo: dodaje jawny, gęsty składnik przeżycia — `1 - (filled_cells / 64)` za **każdy** ruch
(maleje w miarę zapełniania planszy), obok kary `-20` za koniec. README nazywa to wprost
strategią zamiast punktacji:

> "Teaching it to survive instead of score" (...) agent nie widzi wyniku gry podczas
> treningu, optymalizuje przeżycie poprzez utrzymanie otwartej planszy, co pośrednio
> prowadzi do wyższych wyników.
> — [Botkraker/block-blast-AI README](https://github.com/Botkraker/block-blast-AI), parafraza
> WebFetch potwierdzona cytatem powyżej

Ten składnik jest tego samego rzędu wielkości (0–1) co typowa nagroda za ruch w tamtym
projekcie — nie jest to mały bonus w cieniu nagrody za punkty, tylko dominujący sygnał
(punktacja gry w ogóle nie wchodzi do nagrody w tym repo).

`[Z]` Z domeny lokomocji (nie gry planszowej — ekstrapolacja jak niżej): Rajeswaran i in. /
przegląd projektowania nagród, *Learning to Locomote: Understanding How Environment Design
Matters for Deep Reinforcement Learning*
([arXiv:2010.04304](https://arxiv.org/abs/2010.04304)), sekcja 9 „Survival Bonus", testują
wartości 0, 1, 5 (domyślna w PyBullet: 1):

> "If the survival bonus term is too large, however, the algorithm exploits the survival
> bonus reward while neglecting other reward terms. This results in a character that
> balances but never steps forward." (...) "setting it to 0 makes the discovery of a basic
> walking gait too difficult." (...) "The survival bonus value provides a critical form of
> reward shaping when learning to locomote. Values that are too small or too large leads to
> local minima."
> — [Rajeswaran i in., sekcja 9](https://arxiv.org/abs/2010.04304)

`[H]` To źródło dotyczy lokomocji dwunożnej, nie gry planszowej — przenoszę je tu jako
analogię do mechanizmu ryzyka („zbyt duży bonus za przeżycie → agent optymalizuje trwanie,
nie cel"), nie jako zmierzony wynik dla Block Blasta. W grze planszowej analogiczne
zachowanie patologiczne wyglądałoby jak: agent unika stawiania klocków, które czyszczą linie
(bo czyszczenie zmniejsza `filled_cells` chwilowo, ale głównie bo kończy fazę i przybliża
kolejne trudne postawienia) na rzecz maksymalizacji liczby kroków — nie zmierzyłem tego, to
czysta hipoteza z analogii.

**Podsumowanie (c):** jedyny bezpośredni precedens w tej dokładnej grze (Botkraker) dodaje
gęsty, dominujący sygnał przeżycia i **nie** używa punktacji gry wcale. Nie ma dowodu, że to
podejście jest lepsze — README nie podaje metody pomiaru, tylko deklarację projektową.
Literatura spoza tej gry (lokomocja) potwierdza ogólny mechanizm: zbyt duży bonus za
przeżycie tworzy lokalne minimum, w którym agent optymalizuje trwanie zamiast zadania.

## Czego nie udało się ustalić

- Czy istnieje recenzowana praca naukowa (nie hobbystyczne repo) badająca explicite jawny
  składnik nagrody „za przeżyty krok" w Tetris, 1010! albo Block Bloście, i jego wielkość
  względem nagrody za ruch — nie znaleziono żadnej w przeszukanych źródłach (pytanie c).
- Pełna treść papieru Pardo i in. 2018 nie została przeczytana bezpośrednio z PDF (parser
  zwracał dane binarne); cytaty i parafrazy pochodzą z wersji HTML (ar5iv) przepuszczonej
  przez pośredniczący model WebFetch, nie z mojego bezpośredniego czytania artykułu —
  moc dowodowa niższa niż standardowe `[Z]`, zaznaczone przy cytacie (pytanie a).
- Czy Huang & Ontañón (2006.14171) albo jakakolwiek inna recenzowana praca testowała wprost
  scenariusz „ta sama wartość nagrody koduje dwa różne zdarzenia" (nielegalny ruch i naturalny
  koniec epizodu) — nie znaleziono; dostępne źródła odpowiadają na sąsiednie pytanie
  (maskowanie vs. kara za nielegalny ruch), nie na kolizję dwóch zdarzeń (pytanie b).
- Treść *Reinforcement Learning For Constraint Satisfaction Game Agents*
  (arXiv:2102.06019, gry Minesweeper/2048/Sudoku — naturalny koniec epizodu) nie została
  ustalona poza ogólnikowym abstraktem; nie wiadomo, jak ten paper koduje przegraną względem
  ruchu nielegalnego (pytanie b, dodatkowe źródło niepotwierdzone).
- Rzeczywisty kod reward function repo
  [RisticDjordje/BlockBlast-Game-AI-Agent](https://github.com/RisticDjordje/BlockBlast-Game-AI-Agent)
  (DQN, PPO, PPO+Action Masking, DQN+Action Masking) nie został odczytany — README nie
  zawierał wystarczających szczegółów, a plik źródłowy nie został pobrany; nieznane, czy to
  repo dodaje sygnał przeżycia i jak traktuje kolizję z pytania (b).
- Żadne źródło nie podaje zmierzonej (nie deklarowanej) korzyści z dodania sygnału przeżycia
  w grze tego typu — najbliższe dane (Botkraker) to deklaracja projektowa bez metodologii
  pomiaru ani porównania z wariantem bez tego sygnału.

**Czy odpowiedziano na pytanie z issue:** częściowo. Na (a) i (c) znaleziono realne, ale
niejednoznaczne/niebezpośrednie źródła (formalna teoria RL kontra empiryczna praca o
self-punishment dla a; jedna implementacja tej samej gry plus analogia z lokomocji dla c).
Na (b) źródło literaturowe odpowiada na pytanie sąsiednie (maskowanie vs. kara), a na samą
kolizję dwóch zdarzeń odpowiadają wyłącznie hobbystyczne implementacje przez jej strukturalne
wykluczenie, nie przez świadome rozstrzygnięcie w literaturze.
