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

**Sesja**:
Jedno uruchomienie agenta Claude Code, wyzwolone przez issue z etykietą
`rola:*`, kończące się raportem w komentarzu i zamknięciem issue.

**Ogniwo**:
Pojedynczy przebieg workflow w łańcuchu składającym się na jedną długą sesję.
Istnieje, bo job w Actions ginie po 6 h, a limit subskrypcji może uciąć pracę
wcześniej — dlatego każde ogniwo zapisuje stan przed końcem.
_Avoid_: etap, krok, iteracja

**Epilog**:
Krok workflow wykonywany zawsze, także po śmierci agenta. Dowozi raport, scala
gałąź zadania i wypycha odblokowanych dependentów. Nie jest agentem.

**Rola**:
Para skill + profil uprawnień, wybierana etykietą `rola:<nazwa>`. Zatrudnienie
nowej roli nie wymaga edycji workflow.
_Avoid_: tryb, persona, typ agenta
