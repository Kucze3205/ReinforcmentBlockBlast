# Droga pętli: przełomy, ślepe uliczki, punkty zwrotne

Badanie do [#368](../../issues/368) (mapa [#361](../../issues/361)). Narracja zrekonstruowana z `RAPORT.md`, dzienników cykli (`docs/journal/cykl-0001..0060.md`), raportów eksperymentów w `docs/*.md`, `bench/*.json` i `git log`. Te same wpisy w formie maszynowej (oś czasu): [`droga.json`](droga.json). Numery wpisów są wspólne dla obu plików.

Zastrzeżenia: data wpisu to data dziennika cyklu (koniec cyklu), pomiar bywa z cyklu wcześniejszego. Liczby przepisałem z dzienników i raportów; nie przeliczałem benchmarków. Cykle 11-13 nie mają dzienników (padnięte sesje). Klasyfikacja jest moja. Gwiazdka przy tytule oznacza punkt zwrotny.

## Skrót

Od zachłannej (704,79 pkt) do bota, który nie przegrywa, w 60 cyklach, 2026-09-25 do 2026-10-02:

| # | Przełom | Efekt |
|---|---|---|
| 3 | Odejście od DQN, ocena planszy + przeszukanie na CPU | zmiana kierunku |
| 6 | Przeszukanie całej tacki + CEM | 704,79 do 4510,24 (x6,4) |
| 17 | Układ AD (kwadraty 3x3) w przeszukaniu | 6171 do 10 584 (+71,5%) |
| 22 | Szeroka wiązka (beam 8 do 128) | +121% przy tych samych wagach |
| 28 | Śmierć w symulatorze = błąd przeszukania (100/100) | zmiana diagnozy |
| 29 | Gwarancja tacki (complete=1) | 123 077 do 560 859, zero śmierci |
| 30-31 | gain_weight | pkt/postawienie x4,9, 11,03 mln (cel symulatorowy) |
| 33-34 | Cel zmieniony na "nie przegrywa", 0/600 przegranych | polityka zamrożona od cyklu 34 |
| 60 | Seria s7 10/10 do 1 mln w prawdziwej apce | cel osiągnięty |

Dwa wnioski przekrojowe z danych:

1. **Dźwignie, które działały, to kształt przeszukania i reprezentacja oceny wycelowana w konkretnego zabójcę** (kwadrat 3x3, prostokąty 3x4/4x3), a nie ilość treningu. Od cyklu 22 dłuższy trening i mniejszy krok TD dawały szum.
2. **Od cyklu 34 polityka się nie zmieniła.** Wszystkie przegrane w seriach s3-s6 (cykle 38-56) wynikały z odczytu ekranu i sterowania (most), a nie z polityki. Hipoteza "to polityka" była obalana po obejrzeniu zrzutów w cyklach 44, 52 i 55, a cykl 60 ją potwierdził serią 10/10.

## Ślepe uliczki z powodem porzucenia

| # | Co | Wynik | Powód porzucenia |
|---|---|---|---|
| 1 | DQN (sieć neuronowa) | 53 kroki/s, płaska krzywa po ~80 tys. kroków, gorsze od zachłannej | Koszt bez GPU i płaska krzywa; kod zostawiony, sieć nie wróciła |
| 8 | CEM na wagach lookahead (#111) | 5773 vs 6171 (-6,45%, -0,76 SE) | CEM wybrał szum: 32 partie dają próg wykrywalności ~64% średniej |
| 9 | Combo w ocenie (#122) | wynik x0,934, przeżycie x0,8685 | Kupuje punkty za życie planszy, a wiąże przeżycie |
| 13 | Sygnał punktowy (score) w TD | 4572 vs 5839 (-25,9%, -2,86 SE) | W tej grze wiąże przeżycie |
| 14 | Dłuższy trening układu A (100k) | 6017 vs 6171 (-0,25 SE) | Plateau; pojemność układu, nie odcinki |
| 17 | ADC nad AD, starty z późnej gry | ADC +3,8% (0,46 SE); ss -7,05% | Zysk ADC stopniał z +14% do +1,2% przy 70k; ss bez efektu |
| 20 | Skala 200k-800k, mniejszy krok TD | pasmo 27-35 tys. (se ~9%) | Szum; rekord adcg 400k to maksimum z 8 losowań |
| 21 | Drugi poziom przeszukania | domyślny gorszy; wariantów brak różnicy >1 se | Przekleństwo optymalizatora (obciążenie x2,1); samples=0 tańsze o 18% |
| 22 | Etapy N-tuple (adgs2) | 66-71 tys. vs 88 tys. rekordu | Poniżej rekordu, +6% nad kontrolą w szumie |
| 23 | Uczenie z przeszukania (#216) | -46,6% (8k), -59,6% (16k) odcinków | Szkodzi tym bardziej, im dłużej; podejrzenie off-policy (niezmierzone) |

Czego nie próbowano: sieci neuronowej jako naprowadzania przeszukania (jedyny kandydat na powrót sieci, odłożony w cyklu 3), pełnego TreeStrap/expert iteration (opisane w `docs/research/uczenie-z-przeszukania.md`, wariant 1 nie zmierzony).

## Wpisy chronologiczne

### 1. DQN na zwykłym runnerze

**Cykl przed pętlą, 2026-09-20 · ŚLEPA ULICZKA**

- **Próba:** Sieć DQN uczona od zera (kod z 2026-03, agent.py/model.py), pomiar #40.
- **Hipoteza:** Uczenie wzmacniane z siecią da agenta lepszego od zachłannej heurystyki.
- **Wynik:** Około 53 kroków/s, krzywa płaska po ~80 tys. kroków, przeżycie gorsze od zachłannej; symulator bez sieci robi ~10 tys. kroków/s.
- **Czemu:** Koszt (brak GPU, limit 3600 s na polecenie) i płaska krzywa; w klasycznym Tetrisie DQN/C51/PPO przegrywają z heurystyką z przeszukaniem (#54). agent.py i model.py nie skasowane (sieć miała wrócić jako naprowadzanie przeszukania; nie wróciła).
- **Źródła:** `docs/journal/cykl-0001.md (#40)`, `docs/journal/cykl-0003.md`, `docs/research/kierunek-algorytmiczny.md`

### 2. Pętla nie działa: zamek, GH_TOKEN, scalanie

**Cykl 1-2, 2026-09-25 · naprawa narzędzi**

- **Próba:** Bieg na sucho mechaniki pętli (orchestrator/implementer/verifier/researcher).
- **Hipoteza:** Pętla przejdzie pełny cykl bez ręki człowieka.
- **Wynik:** Nie przeszła: gh issue lock blokował raport, GH_TOKEN eksportowany za późno (żadna rola nie dostawała treści zadania), merge_main nie scalał przez czerwone testy (from turtle import done w model.py). Zero commitów sesji na main przez dwa cykle. Linia bazowa (zachłanna) 704,79 śr. / 34,99 postawień.
- **Czemu:** Mechanika nigdy nie działała; poprawki #47, #49. Cykl 3 potwierdził działanie całej ścieżki.
- **Źródła:** `docs/journal/cykl-0001.md`, `docs/journal/cykl-0002.md`, `docs/journal/cykl-0003.md`

### 3. Zmiana kierunku: ocena planszy + przeszukanie tacki + strojenie na CPU*

**Cykl 3, 2026-09-25 · PRZEŁOM**

- **Próba:** Research #54 (kierunek algorytmiczny) i pomiar #40.
- **Hipoteza:** Przy braku GPU wartość siedzi w funkcji oceny i przeszukaniu, nie w sieci.
- **Wynik:** DQN schodzi z linii głównej. Ręcznie ważone cechy dają w Tetrisie ~5 mln linii, strojone CBMPI ~51 mln (źródła zewnętrzne z #54). Próg decyzyjny na wynik #82 ustawiony przed pomiarem (cykl 4).
- **Czemu:** Decyzja o kierunku, od której zależało wszystko dalej; zapisany z góry próg zapobiegł nieskończonemu odraczaniu.
- **Źródła:** `docs/journal/cykl-0003.md`, `docs/journal/cykl-0004.md`, `docs/research/kierunek-algorytmiczny.md`

### 4. Awarie pomiaru: crashed, bench bez liczb, wynik ginie po benchmarku

**Cykl 3-5, 2026-09-25 · naprawa narzędzi**

- **Próba:** Łańcuch #57, #58, #59, #61 oraz #82 (CEM i benchmark).
- **Hipoteza:** Pomiar kandydata da liczbę.
- **Wynik:** Trzy awarie mechaniki zjadły łańcuch; rola bench zameldowała done i nic nie policzyła (ls zamiast benchmarku); wynik #82 przepadł, bo padł skrypt promocji po benchmarku (59 min CPU). Pięć cykli bez zmierzonego kandydata.
- **Czemu:** Raport crashed bywa fałszywy w obie strony (gałąź ma pracę albo jej nie ma), więc trzeba oglądać git log origin/task/N; run_verification zwraca tylko wyjście polecenia, które padło.
- **Źródła:** `docs/journal/cykl-0004.md`, `docs/journal/cykl-0005.md`, `docs/journal/cykl-0007.md`

### 5. HeuristicPolicy z ręcznymi wagami (#57)

**Cykl 4, 2026-09-25 · krok**

- **Próba:** Sześć cech planszy, ręczne wagi, ruch o pół kroku w przód.
- **Hipoteza:** Cechy dadzą istotnie więcej niż zachłanna.
- **Wynik:** 762,5 / 36,84 vs 704,79 / 34,99: +8,19%, poniżej progu 10%, p10 gorsze (139,9 vs 160).
- **Czemu:** Mały zysk: sama ocena bez przeszukania nie wystarcza. Linia zostaje, bo teza #54 dotyczy strojenia, którego jeszcze nikt nie uruchomił.
- **Źródła:** `docs/journal/cykl-0004.md`, `docs/cechy-planszy.md`

### 6. Przeszukanie tacki + CEM (#87): pierwszy rekord

**Cykl 6, 2026-09-25 · PRZEŁOM**

- **Próba:** TrayPolicy: wszystkie ułożenia trzech klocków (beam=8) z oceną sześciu cech; wagi z CEM.
- **Hipoteza:** Przeszukanie całej tacki i strojenie wag podniosą wynik krotnie.
- **Wynik:** 4510,24 / 92,57 postawień (+539,9% vs zachłanna). Rozkład: przeszukanie ×4,89, CEM ×1,21 (ten drugi oparty na 6 partiach, później obalony).
- **Czemu:** Przeszukanie całej tacki to pierwsza duża dźwignia (cztery piąte skoku). Dystans do 10 mln: ~2217× zamiast ~14 000×.
- **Źródła:** `docs/journal/cykl-0006.md`, `bench/87-kandydat.json`

### 7. Drugi poziom przeszukania (LookaheadPolicy, #97)

**Cykl 7, 2026-09-26 · krok**

- **Próba:** Dodanie wartości oczekiwanej po następnej tacce.
- **Hipoteza:** Spojrzenie na losowy dopływ podniesie wynik.
- **Wynik:** 6171,04 / 110,5 (+36,8%, ~3 SE), ×1,37 względem tacki.
- **Czemu:** Realny, ale niewielki zysk; później okazuje się, że drugi poziom przy szerokiej wiązce szkodzi (wpis o drugim poziomie).
- **Źródła:** `docs/journal/cykl-0007.md`, `bench/97-lookahead.json`

### 8. CEM na wagach lookahead (#104, #110, #111)

**Cykl 8-9, 2026-09-26 · ŚLEPA ULICZKA**

- **Próba:** 6 pokoleń CEM, 32 partie na kandydata.
- **Hipoteza:** Strojenie wag podniesie rekord 6171.
- **Wynik:** 5772,95 / 106,28 vs 6171,04 / 110,5: -6,45% (-0,76 SE), bez zmian. Średnia populacji rosła 5310 do 7231 w logu treningu.
- **Czemu:** CEM wyselekcjonował szum: 32 partie dają próg wykrywalności ~64% średniej (#101), a elitę ocenia się na tych samych seedach. Obalone założenie cykli 5-8 o tanim mnożniku x1,21.
- **Źródła:** `docs/journal/cykl-0009.md`, `bench/110-cem-wagi.json`, `bench/111-cem.json`, `docs/strojenie-lookahead.md`

### 9. Combo w ocenie (#118, #122)

**Cykl 9-10, 2026-09-26 · ŚLEPA ULICZKA**

- **Próba:** Wagi combo w funkcji oceny, bo 93% punktów to clear_points.
- **Hipoteza:** Ocena widząca combo podniesie wynik.
- **Wynik:** 5763,49 / 95,97 vs 6171,04 / 110,5: wynik x0,934, przeżycie x0,8685; tempo +7,5% na postawienie, życie planszy -13,1%.
- **Czemu:** Wagi combo kupują punkty za życie planszy, a wiążącym ograniczeniem jest przeżycie. Mechanizm zostaje jako bezwładna infrastruktura (wagi 0).
- **Źródła:** `docs/journal/cykl-0010.md`, `bench/122-combo.json`, `docs/combo-w-ocenie.md`

### 10. Co naprawdę wiąże: przeżycie, nie jakość łańcucha

**Cykl 9-10, 2026-09-26 · krok**

- **Próba:** Pomiar #119 (skąd punkty), wyprowadzenie ~5n^2 z cyklu 9, pomiar sd_diff.
- **Hipoteza:** 10 mln wypada przy ~1414 postawieniach (~5n^2).
- **Wynik:** Obalone: rzeczywisty współczynnik 0,213 (24x mniej), wykładnik 1,55; mediana łańcucha 9, 3 zerwania na partię. Sufit 2000 ruchów nigdy nie wiązał. Dystans do celu to 40-1600x w przeżyciu. sd_diff policzony poprawnie (wspólne seedy obniżają sigmę tylko o 6,6%).
- **Czemu:** Zmieniło kierunek poszukiwań z jakości łańcucha na przeżycie. Walidacja metodologii benchmarku zdjęła z pętli ryzyko błędnych promocji rekordu.
- **Źródła:** `docs/journal/cykl-0009.md`, `docs/journal/cykl-0010.md`, `docs/punkty-na-postawienie.md`, `docs/ile-do-10-mln.md`

### 11. Cykle 11-13: padnięte sesje

**Cykl 11-13, 2026-09-27 · naprawa narzędzi**

- **Próba:** Sesje bez wpisów w dzienniku.
- **Hipoteza:** -
- **Wynik:** Padnięte sesje (API 400, awaria #137 naprawiona przez właściciela); cykle 11-13 nie mają dzienników.
- **Czemu:** Awaria infrastruktury, nie linii pracy.
- **Źródła:** `docs/journal/cykl-0014.md`

### 12. Tabelaryczna ocena N-tuple/TD (#126)

**Cykl 10-14, 2026-09-27 · krok**

- **Próba:** Sieć n-tuple (4096 wag, TD po afterstate) zamiast sześciu ręcznych cech; research #94, #120, #131.
- **Hipoteza:** Uczona ocena przebije ręczne cechy.
- **Wynik:** Sygnał score alpha 0,001: wynik 506, 1220, 819 (szczyt w oknie 13, potem zawrót), przeżycie 28,4, 45,6, 36,4. W szczycie ~1,6x lepiej niż ręczne cechy w tej samej polityce (1220 vs 762,5).
- **Czemu:** Pierwszy dowód, że uczona ocena łapie coś, czego ręczne cechy nie mają; zawrót krzywej rozdzielony na dwie przyczyny (krok vs sygnał) i sprawdzony w cyklach 14-15.
- **Źródła:** `docs/journal/cykl-0014.md`, `docs/ntuple.md`, `docs/research/przeszukanie-z-wyuczona-ocena.md`

### 13. Sygnał punktowy (score) vs przeżycie (survival)

**Cykl 15, 2026-09-27 · ŚLEPA ULICZKA**

- **Próba:** #143 score alpha 0,0002 vs #144 survival alpha 0,001, ta sama architektura.
- **Hipoteza:** Sygnał przeżycia da lepszą ocenę niż punkty.
- **Wynik:** Survival 5839,48 / 120,31 (bez zmian vs rekord); score 4571,95 / 77,26 (-25,91%, -2,86 SE, regresja). Krzywa score przestała zawracać przy mniejszym kroku, ale jest słabsza.
- **Czemu:** Sygnał score porzucony (w tej grze wiąże przeżycie, #119/#131); wygrywa survival. Przy okazji poprawiono przesunięcie celu TD o jeden krok (#153); dla survival bitowo bez skutku.
- **Źródła:** `docs/journal/cykl-0015.md`, `docs/ntuple-score-a0002.md`, `docs/ntuple-survival.md`, `docs/research/sygnal-uczenia.md`

### 14. Dłuższy trening układu A (100k)

**Cykl 16, 2026-09-27 · ŚLEPA ULICZKA**

- **Próba:** #147, #151: trening do 100k odcinków.
- **Hipoteza:** Więcej odcinków podniesie rekord.
- **Wynik:** 6017,08 / 119,43 vs rekord 6171: -0,25 SE, bez zmian; plateau od ~66-70k, przeżycie +1%.
- **Czemu:** Linia A wyczerpana. Układ łat to dźwignia, nie liczba odcinków: AD (łaty widzące kwadraty 3x3, główny zabójca partii wg #128) dało +42% przeżycia zachłannie przy tej samej liczbie odcinków.
- **Źródła:** `docs/journal/cykl-0016.md`, `docs/ntuple-survival-100k.md`

### 15. Układ AD w przeszukaniu (#156): drugi przełom

**Cykl 17, 2026-09-27 · PRZEŁOM**

- **Próba:** Łaty AD (kwadraty 3x3), 40k odcinków, survival, przeszukanie tacki.
- **Hipoteza:** Lepsza ocena opłaca się w przeszukaniu bardziej niż zachłannie.
- **Wynik:** 10 584,01 / 216,57 vs 6171,04 / 110,5: +71,5% (5,5 SE). Przeżycie w przeszukaniu 216,6 vs 91,2 zachłannie (x2,4).
- **Czemu:** Ocena celowana w głównego zabójcę (kwadrat 3x3) i przeszukanie wzmacniają się nawzajem: zysk zachłanny +55% dał +76% w przeszukaniu. Dystans do celu ~945x.
- **Źródła:** `docs/journal/cykl-0017.md`, `bench/156-ntuple-survival-ad.json`, `docs/ntuple-survival-ad.md`

### 16. AD 70k

**Cykl 18, 2026-09-28 · krok**

- **Próba:** Dociągnięcie AD 40k do 70k.
- **Hipoteza:** Dalszy trening wciąż pomaga.
- **Wynik:** 14 791,52 / 281,14: +39,8% (3,98 SE) vs AD 40k. Obalone 'plateau ~60-65k'. Reguła: o zatrzymaniu treningu decyduje bench, nie krzywa zachłanna.
- **Czemu:** Przeszukanie wzmacnia przyrost oceny ~2x; pojedyncze okno spadku nie jest plateau.
- **Źródła:** `docs/journal/cykl-0018.md`, `bench/161-ad-70k.json`

### 17. ADC i start z późnej gry (ss)

**Cykl 19-21, 2026-09-28 · ŚLEPA ULICZKA**

- **Próba:** Układ ADC (większy od AD) 70k oraz ADC ss (--start-prob 0,5, stany z późnej gry).
- **Hipoteza:** ADC > AD przeniesie się na przeszukanie; stany z późnej gry przyspieszą naukę.
- **Wynik:** ADC 70k 15 357,71: +3,8% (0,46 SE, bez zmian); przewaga zachłanna +14% przy 40k stopniała do +1,2% przy 70k. ADC ss 14 274,63: -7,05% vs ADC. Przy nowym generatorze (cykl 21) ADC 100k 28 041 (+8,07%, bez zmian).
- **Czemu:** Przy 70k wiąże liczba odcinków, nie pojemność układu; literatura mówi o 1-5 mln odcinków, mieliśmy 70 tys. Starty z późnej gry bez efektu.
- **Źródła:** `docs/journal/cykl-0019.md`, `docs/journal/cykl-0020.md`, `bench/171-adc-70k.json`, `bench/177-adc-ss-70k.json`, `docs/ntuple-survival-adc-ss.md`

### 18. Rdzeń natywny w C i kalibracja generatora

**Cykl 20-21, 2026-09-28 · naprawa narzędzi**

- **Próba:** #184 przeszukanie wiązką w C (ntuple_native.c); #186 wagi typów klocków z 326 tacek apki.
- **Hipoteza:** Przyspieszenie otworzy dłuższe treningi; symulator zgodny z apką da trafniejszy cel.
- **Wynik:** Trening 0,149 do 0,011 s/odcinek (13,4x), 3 partie 15,9 do 0,5 s (32x), wyniki bitowo te same; pełny bench ~97,5 s. Nowy generator: ~1,75x więcej punktów przy +11% przeżycia (linia bazowa AD 70k 25 946,36).
- **Czemu:** Szybkość zmieniła ekonomię: parametry przeszukania dobrane pod 1800 s w Pythonie stały się przestarzałe, a 500k odcinków mieści się w jednej sesji.
- **Źródła:** `docs/journal/cykl-0020.md`, `docs/journal/cykl-0021.md`, `docs/ntuple-natywny.md`, `docs/generator-wagi-typow.md`

### 19. Szeroka wiązka: beam 8 do 128 (#195)*

**Cykl 22, 2026-09-28 · PRZEŁOM**

- **Próba:** Siatka koszt/jakość parametrów przeszukania na wagach AD 70k.
- **Hipoteza:** Parametry domyślne są dobre.
- **Wynik:** beam=8 23 292/281; 16 35 162; 32 44 605/407; 64 47 033; 128 51 432/433 (0,41 s/partię): +121% za ~7x kosztu decyzji.
- **Czemu:** Największa dźwignia od przejścia na n-tuple, przy tych samych wagach; w cyklu 23 rekord 83 865,64 / 619 przy beam=128 na adcga16 800k. Wzrost wklęsły: sam beam nie wystarczy na tysiące postawień.
- **Źródła:** `docs/journal/cykl-0022.md`, `docs/journal/cykl-0023.md`, `docs/przeszukanie-siatka.md`, `bench/201-adcga16-800k-beam128.json`

### 20. Skala treningu 200k-800k i mniejszy krok TD (adg, adcg, adcga4, adcga16)

**Cykl 22-23, 2026-09-28 · ŚLEPA ULICZKA**

- **Próba:** Migawki adg/adcg 200-500k (#194), adcga4/16 do 800k (#196, #197, #201).
- **Hipoteza:** Dłuższy trening i mniejszy krok podniosą krzywą.
- **Wynik:** Krzywe zachłanne płaskie od ~180k (~6-7 tys.), przy beam=8 wszystko w paśmie 27-35 tys. (se ~9%); rekord adcg 400k 34 657,70 to maksimum z 8 szumów (klątwa zwycięzcy). Przy beam=128 adcga16 vs adcg +18% (granica szumu).
- **Czemu:** Skala przestała być dźwignią, pojemność łat też (adcg 136 łat = adg 52 łaty). Krzywa zachłanna i beam=8 przestały mierzyć jakość oceny; od teraz ocena przy beam=128.
- **Źródła:** `docs/journal/cykl-0022.md`, `docs/journal/cykl-0023.md`, `docs/ntuple-survival-adcg.md`, `docs/ntuple-survival-adcga16.md`

### 21. Drugi poziom przeszukania szkodzi (#195, #202, #210)

**Cykl 22-24, 2026-09-29 · ŚLEPA ULICZKA**

- **Próba:** Siatka #195; diagnoza #202; warianty samples/margin przy beam=128 (#210).
- **Hipoteza:** Więcej próbek drugiego poziomu poprawi decyzje.
- **Wynik:** Domyślny drugi poziom pogarsza wynik; diagnoza: maksimum próbek Monte Carlo i drugie max po zawyżonych szacunkach (przekleństwo optymalizatora, obciążenie x2,1). Przy beam=128 żaden wariant nie odbiega o więcej niż 1 se; samples=0 daje to samo 18% taniej.
- **Czemu:** Poprawka nie jest warta kosztu; samples=0 przyjęte w ustawieniu rekordu.
- **Źródła:** `docs/przeszukanie-glebokie-diagnoza.md`, `docs/przeszukanie-drugi-poziom.md`, `docs/journal/cykl-0024.md`

### 22. Sufit ruchów i etapy N-tuple (adgs2)

**Cykl 23-24, 2026-09-29 · ŚLEPA ULICZKA**

- **Próba:** Sufit 2000 do 4000 (5,33% partii wiązało); #209, #213 dwustopniowy trening wg postawień.
- **Hipoteza:** Etapy poprawią ocenę późnej gry.
- **Wynik:** Rekord przy 4000: 88 133,50 / 647 (sufit ścinał ogon). adgs2 300k/400k: 70 670 / 66 926, poniżej rekordu, +6% nad kontrolą w szumie (wykrywalne dopiero ~18%).
- **Czemu:** Etapy zamknięte (nie trenujemy dalej adgs2). Sufit zostaje 4000 (0,33% < 5%).
- **Źródła:** `docs/journal/cykl-0024.md`, `docs/ntuple-survival-adgs2.md`, `bench/213-baseline-cap4000.json`

### 23. Uczenie z przeszukania (#216)

**Cykl 25, 2026-09-29 · ŚLEPA ULICZKA**

- **Próba:** TD na stanach z gry tanią wiązką beam=8 (tools/train_ntuple_search.py), start adcga16-800k, test przy beam=128; kontrola: dalszy trening zachłanny.
- **Hipoteza:** Stany z silniejszej polityki ruszą ocenę z plateau.
- **Wynik:** 8k odcinków -46,6% (5,72 SE); 16k -59,6% (7,40 SE); kontrola -12,8% (1,33 SE, szum).
- **Czemu:** Szkodzi tym bardziej, im dłużej; prawdopodobna przyczyna to off-policy (cel TD zakłada zachłanną kontynuację), niezmierzona. Kontrola też nie zyskuje, więc plateau nie wynika ze źródła stanów.
- **Źródła:** `docs/uczenie-z-przeszukania-pilot.md`, `docs/research/uczenie-z-przeszukania.md`, `docs/journal/cykl-0025.md`

### 24. ADCE: prostokąty 3x4/4x3 (#222, #234)

**Cykl 25-28, 2026-09-29 · krok**

- **Próba:** Nowy układ ADCE (196 łat, 273 664 wagi).
- **Hipoteza:** Plateau to granica reprezentacji.
- **Wynik:** ADCE 200k vs ADC 200k: +34,6% (2,69 SE); rekord #234 ADCE 400k beam=128,samples=0: 123 077,03 / 922,94 (+32,7%, 3,3 SE); realny poziom ~115 tys. (maksimum z dwóch migawek).
- **Czemu:** Pojemność oceny rusza plateau bez kosztu czasu treningu (rdzeń natywny). Pierwsza poprawa od cyklu 22.
- **Źródła:** `docs/journal/cykl-0026.md`, `docs/journal/cykl-0028.md`, `docs/ntuple-wieksze-laty.md`, `bench/234-adce-400k.json`

### 25. Generator świadomy planszy i model generatora

**Cykl 24-27, 2026-09-29 · naprawa narzędzi**

- **Próba:** #211, #217, #221, #226: model losowania tacek, test hipotezy 'tacka zależy od planszy' (Z-6).
- **Hipoteza:** Generator apki zależy od planszy; symulator powinien to odtwarzać.
- **Wynik:** Z-6 nierozstrzygnięte (potrzeba ~1700 par). Wybrany M2-simple; nowy generator zmienia poziom o +5% (88 133 do 92 773, w szumie).
- **Czemu:** Kalibracja wierności symulatora; konflikt rebase (#221) rozwiązany przeniesieniem plików przez git checkout origin/task/N --.
- **Źródła:** `docs/z6-model-generatora.md`, `docs/generator-swiadomy-planszy.md`, `docs/journal/cykl-0027.md`

### 26. 100/100 śmierci to błąd przeszukania (#236)*

**Cykl 28, 2026-09-29 · PRZEŁOM**

- **Próba:** Wyczerpujący przegląd tacki w chwili śmierci (100 partii polityki #227).
- **Hipoteza:** Przeżycie wiąże ocena lub horyzont.
- **Wynik:** W 100/100 przypadków ostatnia tacka była układalna w całości, a wiązka jej nie znalazła; w kodzie generator.next_pieces losuje do skutku aż tray_playable, więc w symulatorze każda śmierć to błąd przeszukania.
- **Czemu:** Obalone założenie cykli 22-27. Wiąże kompletność przeszukania w obrębie tacki, nie ocena ani horyzont.
- **Źródła:** `docs/journal/cykl-0028.md`, `docs/data/death-avoidability-100.json`

### 27. Gwarancja tacki: complete=1 (#239, #240)*

**Cykl 29, 2026-09-30 · PRZEŁOM**

- **Próba:** Przegląd wyczerpujący jako zapas, gdy wiązka nie znajdzie kompletnego ułożenia.
- **Hipoteza:** Polityka nie umrze, jeśli zawsze znajdzie ułożenie całej tacki.
- **Wynik:** 560 858,53 śr. fixed, 100% partii do sufitu 4000, mediana 555 620; +355,7% vs #234 (52 SE). Zero śmierci w ~1,9 mln postawień; 48/48 do 20 000 (#241).
- **Czemu:** Rozwiązało przeżycie w symulatorze. Benchmark przestał mierzyć przeżycie (średnia = sufit x pkt/postawienie); wąskim gardłem stał się koszt benchmarku i apka.
- **Źródła:** `docs/journal/cykl-0029.md`, `bench/240-complete.json`, `docs/gwarancja-tacki.md`

### 28. Waga punktów w ścieżce: gain_weight (#248, #259): cel symulatorowy*

**Cykl 30-31, 2026-09-30 · PRZEŁOM**

- **Próba:** Duża waga punktów bieżącej tacki w składniku ścieżki (gain_weight=100000), pomiar #248, bench #251-#259 przy suficie 16 000.
- **Hipoteza:** Przy gwarantowanym przeżyciu punkty na postawienie można podnieść.
- **Wynik:** pkt/postawienie przy beam=128: 140,9 do 684,6 (x4,9); beam 8: 105,5 do 290,5. Rekord #259: 11 034 218,3 śr. fixed (16 000/16 000, 0 śmierci); cel >=10 mln osiągnięty.
- **Czemu:** Ocena n-tuple wśród kompletnych ułożeń prawie nie liczy się dla punktów (nasycenie przy w=1e5, rozstrzyga tylko remisy); apka daje tylko układalne tacki (0/1160, #249), więc complete=1 przenosi się na oryginał.
- **Źródła:** `docs/journal/cykl-0030.md`, `docs/journal/cykl-0031.md`, `bench/record.json`

### 29. Pierwsza długa partia w apce (#262)

**Cykl 32, 2026-09-30 · krok**

- **Próba:** Jedna ciągła partia polityki rekordu na emulatorze, 10.7.5.
- **Hipoteza:** Polityka z symulatora przeniesie się na oryginał.
- **Wynik:** 2700 ruchów (2695 zgodnych odczytów), 1 004 153 pkt wzorem, licznik apki 681 507, bez końca partii, 12,6 postawień/min, decyzja mediana 1,65 ms. Trajektoria sprawdzona ręcznie (jq).
- **Czemu:** Pierwszy dowód transferu na oryginał. Stosunek licznik/wzór ~0,69 (wzór scoring.py nie trzyma ±10% na kilku partiach), scoring.py zamrożona.
- **Źródła:** `docs/journal/cykl-0032.md`, `docs/punktacja-apka-vs-wzor.md`

### 30. Zmiana celu: agent nie przegrywa (#264) i sufit 64 000 (#279)*

**Cykl 33-34, 2026-09-30 · krok**

- **Próba:** Komentarz właściciela w #264; bench #265-#279 przy suficie 64 000.
- **Hipoteza:** Średnia >=10 mln punktów nie jest właściwym kryterium.
- **Wynik:** Nowy cel: nie przegrywa; 1 mln licznika apki to limit długości partii. #279: 0 przegranych na 600 seedach (300 stałych + 300 rotowanych), epsilon=0, sufit 64 000, średnio 44,2 mln pkt (informacyjnie), ~16,5 h CPU. Polityka od cyklu 34 bez zmian.
- **Czemu:** Średnia punktów jest teraz informacją; wiąże przeżycie i licznik apki. Cała linia symulatora (wiązka + n-tuple) zostaje. Reguła sufitu x2 przy >5% partii wymuszałaby podwajanie bez końca, więc sufit podniesiony raz (10x ~3950 postawień).
- **Źródła:** `docs/journal/cykl-0033.md`, `docs/journal/cykl-0034.md`, `bench/265-cap64000.json`

### 31. Most: tempo, skrypt serii, czytnik licznika HUD

**Cykl 34-37, 2026-09-30 · naprawa narzędzi**

- **Próba:** #266 rozpiska kosztu ruchu i znaczniki t, #283 tools/partia_serii.py, #290, #294, #297, #302 czytnik licznika.
- **Hipoteza:** Most nie jest wąskim gardłem; licznik czytelny tesseractem.
- **Wynik:** Pomiar #286: ~1720 postawień do 1 mln licznika (szacunek 3950 obalony). read_score myli 4. cyfrę 7-cyfrowego licznika; czytnik zmieniony na wzorce cyfr; czytnik działał tylko na testach (uint8), nie przez screenshot().
- **Czemu:** Od celu nieprzegrywania jedyne przegrane to błędy mostu; test czytnika musi iść tą samą ścieżką co produkcja.
- **Źródła:** `docs/journal/cykl-0035.md`, `docs/journal/cykl-0036.md`, `docs/journal/cykl-0037.md`, `docs/seria-skrypt.md`, `docs/tempo-licznika.md`

### 32. Serie s1-s2: skórki, nakładki, okna

**Cykl 38-42, 2026-10-01 · naprawa narzędzi**

- **Próba:** Seria 10 partii na emulatorze (s1), potem s2.
- **Hipoteza:** Most przeżyje partię do 1 mln.
- **Wynik:** Skórki zmieniane w trakcie partii i nakładki (puchar, napis Combo) mylone z klockami; s1 8/10 przerwań; mimo to dwie partie doszły do 8,28 mln i 6,69 mln licznika bez przegranej (~4,6x i ~4,8x potrzebnej liczby postawień). Tempo ~26-27 postawień/min.
- **Czemu:** Polityka nie przegrywa na prawdziwym generatorze w długiej partii; poprawiano detektory okien i diagnozę przegranych (#299).
- **Źródła:** `docs/journal/cykl-0038.md`, `docs/journal/cykl-0039.md`, `docs/journal/cykl-0040.md`, `docs/journal/cykl-0041.md`, `docs/journal/cykl-0042.md`, `docs/seria/s1`

### 33. Pierwsza przegrana na oryginale i fałszywe detektory

**Cykl 43-47, 2026-10-01 · naprawa narzędzi**

- **Próba:** s2 partia 3 (392 postawienia), analiza #305, regresja detektorów (#311, #312).
- **Hipoteza:** Przegrana oznacza ślepą plamkę polityki.
- **Wynik:** Obalone: przegrane 2/3 to read_tray na drewnianej skórce (tło paska przechodzi is_block), nie polityka ani generator. Zabijanie gry ~16-18 min po starcie emulatora (usługi Google) mylone z ekranem końca; #304 wprowadził regresję (SPLASH_LOGO_BOX łapał górne wiersze planszy); is_home_screen dawał 147 fałszywych trafień. Regresja detektorów: 14 różnic przed, 0 po.
- **Czemu:** Przegrane z mostu, nie z polityki; narzędzia regresji (tools/porownanie_odczytu.py, tools/detektory_na_planszy.py) zwróciły się od pierwszego użycia.
- **Źródła:** `docs/journal/cykl-0043.md`, `docs/journal/cykl-0044.md`, `docs/journal/cykl-0045.md`, `docs/journal/cykl-0046.md`, `docs/journal/cykl-0047.md`

### 34. Serie s3-s5: reklamy, restart, baner Combo

**Cykl 48-53, 2026-10-02 · naprawa narzędzi**

- **Próba:** Detektory reklam, restart_app, kontrola utraty partii (#318), przegrana s5 p.7 (#329).
- **Hipoteza:** Przegrana s5 p.7 to polityka (cykl 51).
- **Wynik:** Obalone w cyklu 52: odczyt planszy bierze glify baneru 'Combo 145' za klocki; na prawdziwej planszy polityka ułożyłaby całą tackę. Baner to tylko 25% przypadków ok:false (cykl 53). Pełny unittest po rebase przewracał sesje z poprawnymi zmianami.
- **Czemu:** Wszystkie przegrane s3-s5 to most. Dodano docs/seria/plansza-roznice.md (100 klatek, 11 błędów mostu z ruchem).
- **Źródła:** `docs/journal/cykl-0050.md`, `docs/journal/cykl-0051.md`, `docs/journal/cykl-0052.md`, `docs/journal/cykl-0053.md`, `docs/seria/plansza-roznice.md`

### 35. Seria s6: 4 przegrane, nowe zasady 10/10

**Cykl 54-56, 2026-10-02 · naprawa narzędzi**

- **Próba:** s6 (10 partii): analiza wsteczna (#341), korekta duchów (#342), zasady zaliczania (#345).
- **Hipoteza:** Polityka przegrywa z własnej winy lub generator apki zmienił rozkład (cykle 54-55).
- **Wynik:** Oba obalone: we wszystkich czterech przegranych polityka na prawdziwej planszy kładzie całą tackę; ostatnie tacki układalne, rozkład tacek bez odchylenia. Obalone też 's4 bez przegranej' (4 przerwania to przegrane po kole fortuny). Nowa zasada właściciela: seria liczy się dopiero przy 10/10 do 1 mln.
- **Czemu:** Zamyka wątek wątpliwości o politykę: przegrane s3-s6 wynikają z odczytu i sterowania. tools/przeglad_s6.py daje powtarzalną diagnozę.
- **Źródła:** `docs/journal/cykl-0054.md`, `docs/journal/cykl-0055.md`, `docs/journal/cykl-0056.md`

### 36. Czas napisu, ponowny odczyt, stop po 1 mln

**Cykl 57-59, 2026-10-02 · naprawa narzędzi**

- **Próba:** #350 pomiar czasu napisu (80 serii), #347 stop po 1 mln wg HUD, #351, #353 ponowny odczyt planszy, gdy ekran nie zgadza się z oczekiwanym.
- **Hipoteza:** Reguła ogólna ponownego odczytu usunie błędy odczytu.
- **Wynik:** Napisy Combo N 61/80, duże liczby 12/80; pełny zestaw testów ~30 min (obalone 'rośnie i blokuje'). s7 pierwszy przebieg: 3 cele po 80 min, stop_prog niepotwierdzony 2/3 (#356).
- **Czemu:** Przeszukania nie ruszano; poprawki wyłącznie w moście.
- **Źródła:** `docs/journal/cykl-0057.md`, `docs/journal/cykl-0058.md`, `docs/journal/cykl-0059.md`

### 37. Cel osiągnięty: s7 10/10, 0 przegranych*

**Cykl 60, 2026-10-02 · PRZEŁOM**

- **Próba:** Seria s7 (run 37046972994, kod 40137e2) z kompletem poprawek mostu.
- **Hipoteza:** Z poprawkami mostu ta sama polityka przejdzie 10/10.
- **Wynik:** 10/10 partii do 1 mln licznika (od 1 001 477 do 1 282 497), 44-156 min, 919-3299 postawień, zero przegranych i przerwań. Ponowny odczyt zadziałał 59 razy (49 naprawionych, 10 rozbieżnych, żaden nie zakończył partii). Symulator: 0/600 przegranych (#279).
- **Czemu:** Potwierdza tezę cyklu 59: przegrane s3-s6 były mostem, nie polityką; polityka niezmieniona od cyklu 34. GOAL_REACHED dodany w git 2026-10-02 (wcześniej 2026-09-30, przy starym celu).
- **Źródła:** `docs/journal/cykl-0060.md`, `RAPORT.md`, `docs/seria/s7`

### 38. Doliczanie licznika po stop_prog (#356, #358)

**Cykl 59-60, 2026-10-02 · naprawa narzędzi**

- **Próba:** Ponowny odczyt licznika po stop_prog; pole odczyty w pomiar[stop_prog].
- **Hipoteza:** Usterka: w 5/10 partii s7 skrypt nie potwierdził miliona od razu (licznik się doliczał), partia grała do 280 tys. dłużej.
- **Wynik:** Poprawka #356 weszła; #358 scalone na main. Wszystkie partie przeżyły mimo opóźnienia.
- **Czemu:** Według zasad #345 wymagało naprawy; hipoteza diamentu obalona (read_hud_score czyta zrzuty poprawnie).
- **Źródła:** `RAPORT.md`, `docs/seria/s7/stop-prog.md`, `docs/journal/cykl-0060.md`
