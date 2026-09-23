# Block Blast — autonomiczna pętla agentowa

Repozytorium niesie dwie rzeczy naraz: reimplementację gry Block Blast wraz z
agentem, który się w nią gra, oraz pętlę agentową, która ten kod rozwija bez
udziału człowieka. Glosariusz opisuje pętlę — jej terminy łatwo pomylić z
terminami gry.

## Język

### Pętla i jej gałęzie

**Pętla**:
Samopodtrzymujący się cykl sesji agentowych w GitHub Actions, rozwijający
agenta aż do osiągnięcia celu z mapy. Włączana i wyłączana wyłącznie przez
człowieka, zmienną repo `AUTOPILOT`.

**Gałąź pętli**:
Gałąź domyślna repozytorium — te dwa określenia znaczą dokładnie to samo i
nigdy nie mogą się rozejść. Dziś `main`.
_Avoid_: gałąź główna, mainline, trunk, `main` jako nazwa w kodzie workflow

**Gałąź zadania**:
`task/<n>`, gdzie `n` to numer issue. Gałąź jednej sesji, scalana w gałąź pętli
przez epilog. Nie widzi cache'u ani plików żadnej innej gałęzi zadania.
_Avoid_: gałąź robocza, feature branch

### Jednostki pracy

**Cykl**:
Odcinek pracy pętli od jednego issue `rola:orchestrator` do następnego: jedna
mapa zadań, sesje, które ją wykonują, i issue złączeniowe, które budzi kolejnego
orchestratora. Jednostka, w której liczy się postęp i w której powstaje jeden
wpis do dziennika.
_Avoid_: obrót, runda, iteracja pętli

**Sesja**:
Jedno uruchomienie agenta Claude Code, wyzwolone przez issue z etykietą
`rola:*`, kończące się raportem w komentarzu i zamknięciem issue.

**Ogniwo**:
Pojedynczy przebieg workflow w łańcuchu składającym się na jedną długą sesję.
Istnieje, bo job w Actions ginie po 6 h, a limit subskrypcji może uciąć pracę
wcześniej — dlatego każde ogniwo zapisuje stan przed końcem.
_Avoid_: etap, krok, iteracja

**Przebieg**:
Jedno uruchomienie workflow w GitHub Actions — wiersz z zielonym albo czerwonym
kółkiem w zakładce Actions. Jedna sesja to jeden przebieg albo łańcuch ogniw,
czyli wielu przebiegów.
_Avoid_: run, job, uruchomienie

**Epilog**:
Krok workflow wykonywany zawsze, także po śmierci agenta. Dowozi raport, scala
gałąź zadania i wypycha odblokowanych dependentów. Nie jest agentem.

**Rola**:
Para skill + profil uprawnień, wybierana etykietą `rola:<nazwa>`. Zatrudnienie
nowej roli nie wymaga edycji workflow.
_Avoid_: tryb, persona, typ agenta

### Pamięć i okna

**Dziennik pętli**:
`docs/journal/cykl-NNNN.md`, jeden plik na cykl, pisany przez orchestratora.
Pamięć pętli: jedyne, co przeżywa koniec sesji, i jedyne wejście orchestratora
startującego na zimno. Indeks, nie magazyn — niesie sedno i link do raportu,
nigdy przepisaną treść.
_Avoid_: log, historia, notatki

**Stan**:
Ostatnia sekcja wpisu do dziennika, przepisywana i kompresowana z poprzedniego
cyklu. Czyni najnowszy plik samowystarczalnym, więc orchestrator nie czyta
historii. Jedyny fragment dziennika z limitem długości.

**Raport tygodniowy**:
`RAPORT.md` w korzeniu repo. Okno właściciela: proza, nadpisywana, historia w
`git log`. Nie myli się z raportem sesji, którym jest komentarz przy issue.
_Avoid_: raport (bez przymiotnika, gdy w pobliżu jest raport sesji)

**Awaria**:
Stan spoczynku pętli: praca nie ruszy bez ręki człowieka. Otwarte issue z
etykietą `awaria` ucisza dozorcę, więc pętla nie kopie w próżnię. Jedyny stan,
w którym brak przebiegów nie jest zatorem. Ogłasza ją orchestrator, który
wyczerpał próby, **albo dozorca** — ten drugi wtedy, gdy orchestrator nie jest
w stanie wstać (#26). Zatrzymuje pętlę wyłącznie wtedy, gdy nie ruszy **nic**;
to, co gatuje jedną rolę, idzie samym mailem.
_Avoid_: błąd, awaria sesji, crash

**Zator**:
Pętla stoi: nie chodzi żaden przebieg i nic nie czeka na termin, choć praca
została. Nie to samo co awaria — zator pętla leczy sama, kopnięciem.
_Avoid_: zawieszenie, deadlock, blokada

**Kopnięcie**:
Odpalenie workflow przez dozorcę, żeby ruszyć stojącą pracę. Dozorca kopie,
zanim zawoła — samo wykrycie zatoru jest bezwartościowe, skoro nikt nie patrzy.
_Avoid_: retry, restart, ponowienie

**Dozorca**:
Sztywny skrypt na cronie, bez agenta, spoza łańcucha pętli. Wykrywa zator i
kopie, zanim zawoła. Milczy, dopóki `awaria` jest otwarta.
_Avoid_: watchdog, monitor, strażnik
