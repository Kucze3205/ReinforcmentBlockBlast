# PROTOTYP — pierwsza mapa orchestratora

> **To jest prototyp, nie dokumentacja.** Gałąź `prototype/orchestrator-map`, bilet
> [#11](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/11). Nie wchodzi na gałąź pętli.
> Odpowiada na jedno pytanie: **czy protokół z [#6](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/6)
> i podział ról z [#7](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/7) trzymają się kupy,
> gdy trzeba z nich napisać konkretne issues.**
>
> Odstępstwo od skilla `prototype`: obie jego gałęzie (demo HTML stanu / warianty UI) nie pasują —
> artefaktem, na który trzeba zareagować, jest **tekst issues**, nie klikalny stan. Reszta zasad
> skilla obowiązuje: wyrzucalne, blisko miejsca użycia, bez polerowania, stan na wierzchu.

---

## Scena: co pętla widzi w chwili pierwszego obrotu

Orchestrator startuje z `workflow_dispatch` puszczonego ręcznie przez właściciela (#16). Czyta repo
i zamknięte issues. Zastaje:

| fakt | źródło |
|---|---|
| symulator skalibrowany, wszystkie 10 rozbieżności z #2 zamknięte | #17 |
| `benchmark.py` działa, `bench/config.json`, 300 stałych seedów | #8, #17 |
| linia bazowa: **zachłanna 704,79 śr. / 34,99 postawień**, losowa 59,15 | `bench/43d1e7c….json` |
| **nie ma żadnych wag** — stare nie ładują się po zmianie `piece_mlp` 16 → 25 | #17, #21 |
| most do oryginału przeszedł raz pełny obieg, `bridge/runs/<sha>/` istnieje | #18 |
| dziewięć niepotwierdzonych założeń Z-1..Z-9 | `docs/calibration-assumptions.md` |
| `bench/record.json` **nie istnieje** — nie ma rekordzisty | #21 |
| dziennik pętli `docs/journal/` pusty | #6 |

Cel: średnia ≥ 10 000 000 pkt na 300 seedach (#9). Aktualnie najlepsze, co repo ma, to **zachłanna
heurystyka na 704 pkt** — czyli cztery rzędy wielkości poniżej celu, bez ani jednego wytrenowanego
modelu. To jest prawdziwy punkt startowy i mapa poniżej z niego wychodzi.

---

## Mapa: sześć issues

Numery `#24`–`#29` są hipotetyczne — to numery, które GitHub nada przy tworzeniu.
Etykiety podaję nad każdą treścią; treść jest dokładnie tym, co idzie do `--body`.

---

### `#24` — Zmierzyć Z-1 i Z-2 na oryginale

**Etykiety:** `rola:verifier`, `pokolenie:1`
**Blokady:** brak

```markdown
## Cel

Rozstrzygnąć dwa najtańsze założenia kalibracyjne pomiarem na prawdziwej apce, nie z dokumentacji.

- **Z-1** — punkt bazowy za linię: `10` czy `80`. Ośmiokrotna różnica w całej skali punktowej.
- **Z-2** — przyrost combo po czyszczeniu: `combo += 1` czy `combo += liczba_linii`.

Most (#18) istnieje i przeszedł pełny obieg, więc pomiar to sterowanie mostem do konkretnych
stanów planszy, a nie budowanie czegokolwiek nowego.

## Kryteria akceptacji

- [ ] Partia doprowadzona do stanu, w którym jeden klocek czyści dokładnie jedną linię przy combo = 0; przyrost wyniku odczytany ze zrzutu i zapisany.
- [ ] Ten sam pomiar powtórzony w **trzech niezależnych partiach** — jeśli liczby się rozjadą, to jest wynik sam w sobie i idzie do raportu jako taki.
- [ ] Dwa czyszczenia po 2 linie z rzędu; drugi przyrost odczytany. Rozstrzyga Z-2.
- [ ] Zrzuty przed/po każdym pomiarze w `bridge/runs/<sha>/z1z2/`, z `pomiar.json`: stan planszy, postawiony klocek, wynik przed, wynik po.
- [ ] `docs/calibration-assumptions.md`: Z-1 i Z-2 przeniesione z „do zweryfikowania" do „zmierzone", z linkiem do przebiegu. **Samego symulatora nie ruszać** — to zadanie mierzy, nie poprawia.

## Weryfikacja

`python -c "import json,pathlib; p=sorted(pathlib.Path('bridge/runs').glob('*/z1z2/pomiar.json')); assert p, 'brak pomiaru'; d=[json.loads(x.read_text()) for x in p]; assert len(d)>=3, f'za malo partii: {len(d)}'; print(d)"`

## Kontekst

- `docs/calibration-assumptions.md` — definicje Z-1 i Z-2 wraz z opisem pomiaru. **Przeczytaj przed startem.**
- #18 — most i jego kontrakt: `bridge/runs/<sha>/`.
- #2 — skąd bierze się sprzeczność między źródłami.
- #20 — otwarty bilet o niestałości punktacji. Jeśli trzy partie dadzą trzy różne liczby, **to jest materiał do #20** i tak to zaraportuj; nie próbuj tego rozstrzygać.

## Budżet

`timeout-minutes: 300` (łańcuch ogniw, emulator). `--max-turns: 120`.
Checkpointuj po **każdej** partii — utrata runnera nie może kosztować trzech partii.
```

---

### `#25` — Czy przeszukiwanie bije uczenie na tej planszy

**Etykiety:** `rola:researcher`, `model:opus`, `pokolenie:1`
**Blokady:** brak

```markdown
## Cel

Zebrać fakty pod decyzję o kierunku algorytmicznym. Mapa (#1) daje pełną swobodę — DQN w repo
jest punktem startowym, nie zobowiązaniem. Zanim pętla wyda setki godzin runnera na trenowanie,
ma wiedzieć, czy trenowanie jest w ogóle właściwą drogą.

Twarde ograniczenie, od którego zaczynasz: **runnery GitHub Actions nie mają GPU.** Metoda,
która wymaga tygodni GPU, jest dla tej pętli niewykonalna, choćby była najlepsza w literaturze.

## Kryteria akceptacji

- [ ] `docs/research/block-blast-algorytmy.md` z odpowiedziami na: (a) jakie wyniki publicznie raportują boty do Block Blasta i pokrewnych (Tetris/1010!/block-puzzle) i **jaką metodą**; (b) czy ktokolwiek raportuje wynik rzędu 10⁷ i czym go osiągnął; (c) co osiąga przeszukiwanie bez uczenia (beam search, MCTS, ewaluacja heurystyczna z lookahead) przy budżecie CPU; (d) ile realnie kosztuje trening RL na tej klasie gry, w GPU-godzinach i próbkach.
- [ ] Każde ustalenie z linkiem do źródła pierwotnego. **Rozdziel, co jest zmierzone, od tego, co ktoś twierdzi** — sekcja „Ustalenia" osobno od sekcji „Cytaty".
- [ ] Jawna sekcja **„Czego nie wiadomo"**. Orchestrator planuje na tym; przemilczana luka wróci jako zmarnowany obrót.
- [ ] Bez rekomendacji „róbmy X". Decyzję podejmuje orchestrator — twoje zadanie kończy się na faktach.

## Weryfikacja

`test -f docs/research/block-blast-algorytmy.md && grep -q "Czego nie wiadomo" docs/research/block-blast-algorytmy.md`

## Kontekst

- Linia bazowa do porównań: zachłanna **704,79 śr. / 34,99 postawień** na 300 seedach (`bench/43d1e7c….json`). Każdą cytowaną liczbę odnieś do niej albo powiedz, że nie da się odnieść.
- #8 — definicja benchmarku, w tym miara **przeżycia** (liczba postawień), odporna na rekalibrację punktacji. Przy porównaniach międzygrowych przeżycie jest często jedyną wspólną walutą.
- `docs/calibration-assumptions.md` — punktacja symulatora jest rekonstrukcją. Nie traktuj cudzych liczb punktowych jako porównywalnych z naszymi bez sprawdzenia reguł.
- #22 — otwarty bilet o granicach zaufania do tekstu z sieci. Do czasu rozstrzygnięcia: **cytat to cytat, nie fakt.**

## Budżet

`--max-turns: 80`. Limit `WebSearch`: 200/sesję, ale nie celuj w niego — sesja zjadająca limit
wyszukiwania prawie na pewno źle postawiła pytanie.
```

---

### `#26` — Wgrywanie i pobieranie wag przez Releases

**Etykiety:** `rola:implementer`, `pokolenie:1`
**Blokady:** brak

```markdown
## Cel

Zbudować narzędzie, przez które wagi wchodzą do repo i z niego wychodzą. Dziś nie istnieje —
#21 rozstrzygnęło **gdzie** wagi mieszkają, ale nikt tego nie napisał, a każda sesja
produkująca model potknie się o to samo.

Bez tego narzędzia benchmark nie ma czego zmierzyć, a pierwszy wytrenowany model przepadnie
razem z runnerem.

## Kryteria akceptacji

- [ ] `tools/weights.py` z trzema poleceniami: `publish <plik.pth>` (tworzy wydanie `w-<SHA>` z `model.pth` + `meta.json`), `fetch <tag|record|previous>` (ściąga do ścieżki lokalnej), `prune` (usuwa wydania spoza zbioru żywego).
- [ ] `meta.json` niesie: SHA commitu, numer issue, datę, kształt sieci, wynik benchmarku jeśli znany.
- [ ] `prune` **nigdy nie usuwa rekordzisty** — wskazanego przez `bench/record.json`. Brak `bench/record.json` (stan dzisiejszy) to nie błąd: oznacza „nie ma jeszcze rekordzisty", więc `prune` nie rusza niczego i kończy się zielono.
- [ ] `fetch` przy brakującym wydaniu kończy się kodem wyjścia mówiącym „nie ma", nie stack trace'em — wywołuje go job benchmarku, który ma z tego zrobić status `blocked`.
- [ ] Test w `tests/test_weights.py`, bez sieci: warstwa GitHuba za jedną funkcją, w teście podmieniona.

## Weryfikacja

`python -m pytest tests/test_weights.py -q`

## Kontekst

- #21 — rozstrzygnięcie: Releases, tag `w-<SHA>`, zbiór żywy = rekordzista + poprzednik + kandydat, `bench/record.json` jako wskaźnik pisany **wyłącznie** przez benchmark.
- #7 — `bench/record.json` jest poza zasięgiem zapisu każdego profilu. Twoje narzędzie go **czyta**, nigdy nie pisze.
- `benchmark.py` — argument `--candidate` przyjmuje ścieżkę do wag; to jest twój odbiorca.

## Budżet

`--max-turns: 60`.
```

---

### `#27` — Nagroda agenta: przyrost wyniku zamiast płaskiego +1

**Etykiety:** `rola:implementer`, `pokolenie:1`
**Blokady:** `#24`

```markdown
## Cel

`Agent.count_reward` daje płaskie `+1.0` za jakiekolwiek czyszczenie. Po kalibracji (#17)
wyczyszczenie 4 linii przy combo 5 jest warte 600 pkt, a jednej linii przy combo 0 — 10 pkt.
Agent dostaje za jedno i drugie ten sam sygnał, czyli jest ślepy dokładnie na mechanikę,
którą wydawca opisuje jako główną.

Zamienić sygnał na **przyrost wyniku po ruchu**, plus kara terminalna za przegraną.
Prosto, zgodnie z tym, co mierzy benchmark, bez własnego shapingu do strojenia.

## Kryteria akceptacji

- [ ] Nagroda = `score_po − score_przed`, przeskalowana tak, by typowy ruch mieścił się w rozsądnym przedziale dla sieci; **współczynnik skalowania jako stała nazwana w jednym miejscu**, nie rozsypana po kodzie.
- [ ] Kara terminalna za brak legalnego ruchu — jedna stała, tam samo.
- [ ] Żadnego shapingu poza tym. Jeśli uznasz, że bez shapingu sygnał jest za rzadki, żeby się uczyło — **nie dokładaj go po cichu**: zaraportuj to jako odkrycie i zostaw. To jest decyzja orchestratora, nie twoja.
- [ ] Skala punktowa zgodna z pomiarem Z-1 z #24. Jeśli #24 zmierzył `80`, a symulator ma `10` — **nie poprawiaj symulatora w tym zadaniu**. Zaraportuj rozjazd jako odkrycie; kalibracja to osobne zadanie z własnym benchmarkiem.
- [ ] `tests/test_engine.py` przechodzi.

## Weryfikacja

`python -m pytest tests/ -q`

## Kontekst

- #23 — bilet mapy opisujący tę rozbieżność w całości, łącznie z argumentem przeciwnym (przyrost wyniku jest rzadki i skokowy). Przeczytaj, zanim zaczniesz.
- #17 — co dokładnie zmieniła kalibracja: combo mnoży i wygasa przez licznik, punkty naliczane po każdym postawieniu.
- #24 — pomiar Z-1; jest twoją blokadą, więc w chwili startu jego wynik jest już w `docs/calibration-assumptions.md`.
- `agent.py`, `scoring.py`.

## Budżet

`--max-turns: 60`.
```

---

### `#28` — Benchmark: zachłanna po zmianie nagrody

**Etykiety:** `rola:bench`, `pokolenie:1`
**Blokady:** `#26`, `#27`

```markdown
## Cel

Przebiec benchmark i ustalić, czy zmiany z tego obrotu czegokolwiek nie zepsuły.

W tym obrocie **nie ma jeszcze wytrenowanego modelu**, więc kandydatem jest `greedy`.
Zadanie odpowiada na pytanie: czy po zmianie nagrody i po pomiarze Z-1 tor pomiarowy
nadal daje tę samą liczbę, co linia bazowa — i czy `tools/weights.py` wpina się w benchmark.

## Kryteria akceptacji

- [ ] `python benchmark.py --candidate greedy --issue <n>` przebiegł na pełnych 300 stałych seedach.
- [ ] Rekord w `bench/<sha>.json`. **`bench/record.json` nie powstaje** — `greedy` nie jest rekordzistą pętli, a linia bazowa nie jest modelem.
- [ ] Wynik porównany z `bench/43d1e7c….json` (704,79 / 34,99). Różnica większa niż szum przy ε = 0 i stałych seedach oznacza, że coś w torze się zmieniło — **to jest wynik do zaraportowania, nie do naprawienia tutaj**.
- [ ] `tools/weights.py prune` wywołane na sucho; kończy się zielono mimo braku `bench/record.json`.

## Weryfikacja

`python -c "import json,glob; f=sorted(glob.glob('bench/*.json')); r=[x for x in f if 'config' not in x and 'seeds' not in x]; print(json.load(open(r[-1])))"`

## Kontekst

- #8 — definicja benchmarku: średnia + przeżycie, ε = 0, sufit 2000 ruchów, próg ±10% **nieblokujący**.
- #17 — ostrzeżenie o zerwaniu szeregu: liczby punktowe sprzed kalibracji są nieporównywalne z liczbami po niej. Porównuj **wyłącznie** z rekordem po kalibracji.
- #21 — polityka zbioru żywego wag.

## Budżet

Job liczący, bez sesji Claude'a. `timeout-minutes: 120`.
```

---

### `#29` — Domknięcie obrotu 1

**Etykiety:** `rola:orchestrator`, `model:opus`, `effort:high`, `pokolenie:1`
**Blokady:** `#24`, `#25`, `#26`, `#27`, `#28`

```markdown
## Cel

Zebrać obrót 1, zapisać go w dzienniku i wyprodukować mapę obrotu 2.

To jest issue złączeniowe: zablokowane przez **wszystkie** zadania obrotu, więc odpala się
dopiero, gdy ostatnie z nich zostanie zamknięte. Zamknięcie tego issue popycha pętlę dalej.

## Kryteria akceptacji

- [ ] Przeczytane **wszystkie** issues z etykietą `report:unread`; po przeczytaniu etykieta zdjęta.
- [ ] `docs/journal/obrot-001.md` dopisany: co zlecono, co wróciło z jakim statusem, co się zmieniło w liczbach, które założenia padły, ile było konfliktów i ilu następców.
- [ ] Rozstrzygnięty **kierunek algorytmiczny** na podstawie #25 — albo jawnie odroczony z podaniem, czego jeszcze brakuje. Decyzja idzie do dziennika z uzasadnieniem, nie tylko do treści nowych issues.
- [ ] Mapa obrotu 2 utworzona: issues z etykietami ról, krawędziami blokowania i **jednym issue złączeniowym `rola:orchestrator`** zablokowanym przez wszystkie pozostałe.
- [ ] Każde nowe issue trzyma kontrakt z #6: `## Cel`, `## Kryteria akceptacji`, `## Weryfikacja`, `## Kontekst`. Protokołu do issue **nie wklejaj** — siedzi w skillu roli.
- [ ] Liczba jednocześnie odpalanych sesji ≤ **12**. Sufit konta to 20 jobów; zostaw zapas na epilogi i łańcuch verifiera.
- [ ] Każde nowe issue wydyspatchowane przez `gh workflow run`. Samo utworzenie issue **niczego nie odpala** — to potwierdzone w #5.

## Weryfikacja

`test -f docs/journal/obrot-001.md && test -z "$(gh issue list --label report:unread --json number -q '.[].number')"`

## Kontekst

- #6 — kontrakt issue i raportu, słownik statusów, rola epilogu.
- #7 — role, granice, zasady tworzenia issues i następców, zakaz edycji własnego skilla.
- `docs/journal/` — dziennik pętli. Poprzedni wpis jest twoją pamięcią; transkrypt poprzedniego orchestratora nie istnieje.
- #20, #22, #23 — otwarte bilety mapy. **Nie rozstrzygaj ich sam**; jeśli obrót przyniósł materiał, dopisz go jako komentarz i zostaw właścicielowi.

## Budżet

`--max-turns: 120`.

## Szczególna uwaga

Jeśli w tym obrocie **żadne** zadanie nie zamknęło się statusem `done`, nie produkuj mapy obrotu 2
na oślep. Zapisz to w dzienniku, utwórz **jedno** issue diagnostyczne i to ono niech będzie całą
mapą obrotu 2. Pętla mieląca puste obroty jest gorsza od pętli zatrzymanej.
```

---

## Wiązanie krawędzi: drugie przejście

Issues muszą najpierw istnieć — dopiero potem mogą się nawzajem wskazywać. Orchestrator tworzy
szóstkę, zbiera numery, potem wiąże. Krawędź idzie na **numeryczne `id` bazy**, nie na `#numer`:

```bash
REPO=Kucze3205/ReinforcmentBlockBlast
id() { gh api repos/$REPO/issues/$1 --jq .id; }

# #27 blokowane przez #24
gh api --method POST repos/$REPO/issues/27/dependencies/blocked_by -F issue_id=$(id 24)

# #28 blokowane przez #26 i #27
gh api --method POST repos/$REPO/issues/28/dependencies/blocked_by -F issue_id=$(id 26)
gh api --method POST repos/$REPO/issues/28/dependencies/blocked_by -F issue_id=$(id 27)

# #29 — złączenie, blokowane przez wszystko
for n in 24 25 26 27 28; do
  gh api --method POST repos/$REPO/issues/29/dependencies/blocked_by -F issue_id=$(id $n)
done

# dopiero teraz dispatch frontu
for n in 24 25 26; do gh workflow run sesja.yml -f issue=$n; done
```

`#29` nie jest dispatchowane przez orchestratora. Wypchnie je `unblock.yml`, gdy epilog zamknie
ostatnie z zadań blokujących (#6).

---

## Front prac w czasie

```
t0    #24 verifier   ──────────────────────┐   (emulator, łańcuch ogniw)
      #25 researcher ──────────┐           │
      #26 implementer ─────────┼───┐       │
                               │   │       │
t1                        #27 implementer ─┤   (czeka na Z-1 z #24)
                                   │       │
t2                            #28 bench ───┤   (czeka na #26 i #27)
                                           │
t3                                    #29 orchestrator
```

Trzy sesje na starcie, sufit 12 z zapasem. Front nie jest ani jedną sesją w kolejce, ani
dwunastoma naraz — i to jest to, co ten szkic miał pokazać.

---

## Co prototyp odsłonił

Sześć rzeczy wyszło dopiero przy pisaniu konkretnych treści. Każda jest materiałem do decyzji.

### 1. Sekcja `## Kontekst` puchnie, bo zimna sesja nie ma pamięci

#6 mówi: *„linki do issues/dokumentów, nigdy wklejki"*. Ale sesja czytająca `#27` musi znać
rozstrzygnięcie z #23, ostrzeżenie z #17 i pomiar z #24 — a to trzy issues po kilkaset słów każde.
Albo sesja przepala turę na czytanie trzech issues, albo orchestrator streszcza, czyli wkleja.

W szkicu wybrałem trzecią drogę: **link plus jedno zdanie po co tam iść**. Ale to znaczy, że
orchestrator musi streścić każde wejście — a im lepiej streszcza, tym bliżej wklejki, której #6 zakazuje.

### 2. „Zaraportuj, nie naprawiaj" musi być w treści issue, bo inaczej nie zadziała

Trzy zadania w tej szóstce dostały jawne zdanie *„jeśli zobaczysz X, zaraportuj i zostaw"*.
Bez tego sesja z dostępem do kodu naprawi rozjazd sama, i będzie miała rację jako programista —
a złamie podział pracy, bo naprawa nie przejdzie przez benchmark.

To nie jest protokół (nie idzie do skilla roli, bo dotyczy konkretnego zadania), ale też nie jest
celem. #6 nie ma na to sekcji. Dziś ląduje w kryteriach akceptacji jako zdanie na „nie" — a kryterium
akceptacji brzmiące „nie zrób czegoś" jest niesprawdzalne przez epilog.

### 3. `## Weryfikacja` przy zadaniu badawczym i decyzyjnym jest teatrem

Dla `#26` weryfikacja jest prawdziwa: `pytest`. Dla `#25` to `grep -q "Czego nie wiadomo"` —
sprawdza, czy plik ma nagłówek, nie czy badanie coś warte. Dla `#29` sprawdza, czy dziennik
istnieje i czy etykiety zdjęte, nie czy mapa ma sens.

#6 stawia epilog jako sędziego, *„bo bez tego jedynym sędzią pracy agenta jest ten sam agent"*.
Przy połowie typów zadań ten sędzia patrzy na obecność pliku. Pytanie, czy to jest akceptowalne
minimum, czy iluzja kontroli, która usypia.

### 4. Złączenie ma z czego zbierać feedback — ale tylko jeśli epilog domyka każdy przypadek

`#29` czyta `report:unread`. Ta etykieta pojawia się **tylko** przy zamknięciu issue przez epilog (#6).
Status `paused` zostawia issue otwarte, bez etykiety, i **trzyma złączenie**. Status `conflict` też
nie zamyka. Sesja wisząca na limicie tygodniowym blokuje więc obrót na siedem dni — a orchestrator
nie ma jak o tym wiedzieć, bo z definicji jeszcze się nie obudził.

To jest dokładnie ten cichy zastój, o który pyta #10 — i szkic pokazuje, że nie jest hipotetyczny:
leży na ścieżce krytycznej pierwszego obrotu, przy `#24`, które jedzie łańcuchem ogniw na emulatorze.

### 5. Pierwszy obrót nie ma czego trenować, a to prawdopodobnie norma

Nie ma wag, więc benchmark mierzy zachłanną, czyli **porównuje linię bazową z linią bazową**.
Obrót zużywa job i nic nie wnosi. Wyszło mi to dopiero przy pisaniu `#28`.

Wniosek jest ogólniejszy niż obrót 1: `rola:bench` ma sens tylko wtedy, gdy ktoś w tym samym
obrocie wyprodukował wagi. Skill orchestratora musi to wiedzieć, inaczej pętla będzie zlecać
benchmark z przyzwyczajenia — a #8 policzyło, że koszt benchmarku rośnie dokładnie wraz z postępem,
który mierzy.

### 6. `pokolenie:1` nie ma gdzie mieszkać

#7 wymaga licznika pokolenia z twardym limitem 3, ale #6 nie przewidział na to pola w kontrakcie
issue. Wstawiłem etykietę `pokolenie:<n>`, bo epilog i tak czyta etykiety — ale to jest decyzja
podjęta w prototypie, nie rozstrzygnięcie. Alternatywa: pole w bloku YAML raportu, które epilog
przepisuje do następcy.
