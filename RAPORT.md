# Raport pętli

**2026-09-25 · cykl 3**

**Czeka na ciebie:** [otwarte awarie](https://github.com/Kucze3205/ReinforcmentBlockBlast/labels/awaria)
— dziś żadnej. Pętla chodzi sama.

Są natomiast **dwie rzeczy, których żadna rola nie ma jak naprawić** i które opisuję niżej,
w „Co się wydarzyło". Obie są drobne i obie leżą poza zasięgiem sesji.

## Gdzie jesteśmy

Rekordu nadal nie ma. `bench/record.json` nie istnieje, nie ma ani jednych wag. Najlepsze,
co repo dziś potrafi, to zachłanna heurystyka patrząca na jeden klocek i na jeden ruch w przód:
**704,79 punktu** średnio i **34,99 postawień** na partię, na 300 stałych seedach. Losowa
polityka dla skali: 59,15. Cel to 10 000 000 średnio w symulatorze i jedna realna partia
≥ 1 mln w apce. Dystans: **około czternaście tysięcy razy**.

Ta liczba nie drgnęła **trzeci cykl z rzędu**. Cykl 1 był biegiem na sucho, cykl 2 spędził
się na odblokowywaniu pętli, cykl 3 dopiero teraz zlecił pierwszą prawdziwą pracę
algorytmiczną. To jest uczciwy opis: trzy cykle poszły na to, żeby maszyna w ogóle ruszyła.

## Co się wydarzyło

**Pętla jest sprawna na całej długości i to jest najważniejsza wiadomość tego cyklu.**
Commity sesji roboczych cyklu 2 dojechały na gałąź domyślną — sześć zadań, żadnego nie
uruchamiał człowiek. Zadanie dociera do sesji, sesja raportuje, raport ląduje przy issue,
issue się zamyka, zależne odblokowują się same, epilog rusza następne, a zmiany się scalają.
Ostatni niesprawdzony odcinek mechaniki jest sprawdzony.

**Cykl 3 podjął decyzję, którą poprzednie dwa odkładały: zmienia kierunek algorytmiczny.**
DQN schodzi z linii głównej. Miał przeciw sobie własny pomiar — 53 kroki na sekundę na
runnerze bez GPU, płaska krzywa po osiemdziesięciu tysiącach kroków, przeżycie gorsze od
zwykłej heurystyki — i, jak się okazało po przeszukaniu literatury, nie miał za sobą żadnego
precedensu. W tej rodzinie gier (Tetris i pokrewne) DQN, C51 i PPO przegrywają z ręcznie
dostrojoną heurystyką i wynikiem, i kosztem.

Nowa linia to trzy rzeczy naraz: **funkcja oceny planszy** zbudowana z cech (dziury,
fragmentacja, największy wolny prostokąt, ile kształtów jeszcze wchodzi), **wyczerpujące
przeszukanie bieżącej tacki** — trzy klocki są przecież znane jednocześnie, a dzisiejsza
polityka patrzy tylko na jeden — oraz **strojenie wag offline** metodą cross-entropy.
Argument, który przesądził: w klasycznym Tetrisie te same cechy dają pięć milionów linii
z wagami dobranymi ręcznie i pięćdziesiąt jeden milionów z wagami strojonymi. Cała przewaga
siedzi w wagach, strojenie jest liniowe, chodzi na zwykłym procesorze i nie potrzebuje GPU —
czyli mieści się dokładnie na sprzęcie, który mamy.

**Rozstrzygnięty został też spór o punktację.** Na bocznej gałęzi leżała drabinka punktowa
dająca ponad dwa razy więcej punktów za ten sam ruch. Odrzucona: obecny wzór jest zamrożony
na pomiarze z prawdziwej gry, zgodnym co do punktu przez osiemnaście ruchów, a drabinka nie
ma za sobą żadnego pomiaru. Dwukrotnie wyższe liczby to inflacja miarki, nie lepszy bot —
podnoszą tak samo wynik polityki losowej. Linia bazowa zostaje nieprzeliczona, więc
porównania w cyklu 3 będą uczciwe.

Nagroda dostała jedną konkretną poprawkę: silnik wyrzucał punkty zdobyte ostatnim ruchem
partii i raportował za niego karę. Średnio to jedenaście punktów, ale w skrajnym przypadku
sto pięćdziesiąt dwa — czyli agent dostawał karę za najlepszy ruch, jaki wykonał. Sprawdzone
zostało przy tym, że poprawka nie rusza linii bazowej, bo benchmark czyta wynik partii,
a nie nagrodę.

**Dwie rzeczy dla ciebie, obie drobne.** Pierwsza: cykl, który wykryje awarię, traci własny
dziennik — sesja zgłaszająca awarię raportuje uczciwie `partial`, a scalane są tylko sesje
`done`. Tak uwięzły dzienniki cykli 1 i 2; odzyskałem je ręcznie, ale pułapka zostaje
i dotyczy dokładnie tych cykli, w których wydarzyło się coś wartego zapisania. Druga: profil
implementera dopuszcza `python`, ale nie `python3`, przez co jednej sesji nie udało się
uruchomić testów. Obie poprawki leżą w plikach, których role nie dotykają.

## Co dalej

Cykl 3 buduje nową linię czterema zadaniami po kolei — cechy planszy, przeszukanie tacki,
strojenie wag, pomiar — i równolegle wysyła pierwszą od dwóch cykli sesję na emulator,
po materiał do pytania „w jaką grę bot naprawdę gra" i po odpowiedź, czy most jeszcze żyje.

**Rokowanie: linia rokuje, po raz pierwszy z konkretnego powodu.** Ma precedens ilościowy
w tej samej rodzinie gier, mieści się na naszym sprzęcie i ma dwa niezależne źródła przewagi,
z których dziś nie używamy żadnego. Próg oceny zapisałem przed pomiarem, żeby nie dał się
przesunąć po fakcie: benchmark ma pokazać **krotność, nie procenty**. Kilkanaście procent
nad 704,79 po pełnym strojeniu oznacza, że linia jest źle postawiona, i cykl 4 ma ją wtedy
zmienić, a nie iterować dalej.
