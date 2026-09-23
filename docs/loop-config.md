# Konfiguracja pętli — sekrety, zmienne, etykiety, uprawnienia

Bilet: [#13](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/13) · mapa: [#1](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/1)
Źródła ustaleń: [#4](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/4) (uwierzytelnianie), [#5](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/5) (samowyzwalanie i uprawnienia), [#7](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/7) (role)

Kontrakt nazw między workflowami a sesjami. Workflow, który odwołuje się do nazwy
spoza tej listy, jest błędem — nie okazją do dopisania nowej nazwy bez decyzji.

---

## Sekrety

| Nazwa | Wygasa | Przeznaczenie |
|---|---|---|
| `CLAUDE_CODE_OAUTH_TOKEN` | ~2027-09-20 | Jedyne poświadczenie generowane ręcznie. Uwierzytelnia sesje Claude Code subskrypcją właściciela. Powstaje z `claude setup-token`, ważny rok. Bez niego **nie ruszy nic**. |
| `ASSETS_READ_TOKEN` | ~2026-10-21 | Odczyt splitów APK Block Blasta z prywatnego release'u ([#14](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/14)). Bez niego nie ruszy **verifier**; reszta pętli pracuje dalej. |

**Kolumna „Wygasa" jest notatką dla właściciela. Pętla jej nigdy nie czyta**
([#26](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/26)). Poświadczenia sprawdza się pomiarem w chwili użycia, nie przewidywaniem
z kalendarza — patrz „Sonda poświadczenia" niżej. Daty są przybliżone, bo token
`setup-token` nie niesie w sobie daty wygaśnięcia, panel konta go nie listuje,
a sekret Actions nie ma pola `expires_at`; liczą się od dnia założenia sekretu.

Do samowyzwalania pętli **nie ma sekretu** — wystarcza wbudowany `GITHUB_TOKEN`
w parze z `workflow_dispatch` ([#5](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/5)). Żadnego PAT-a, żadnego klucza GitHub App.

### `ANTHROPIC_API_KEY` — zakaz

Ta nazwa **nie może istnieć** ani jako sekret, ani jako zmienna, ani w `env:`
żadnego joba. Ma udokumentowane pierwszeństwo nad tokenem subskrypcji i cicho
przekieruje rachunek na płatne API ([#4](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/4)). Cisza jest tu najgorsza — nic się nie zepsuje,
tylko przyjdzie faktura.

---

## Zmienne repo

| Nazwa | Wartość | Przeznaczenie |
|---|---|---|
| `AUTOPILOT` | `on` \| cokolwiek innego | Przełącznik właściciela. Pierwszy krok **każdego** workflow pętli. |

Warunek jest jawnie fail-safe: pętla rusza **wyłącznie** przy dosłownym `on`.
Brak zmiennej, literówka, pusta wartość — wszystko to znaczy „stój".

```yaml
if: vars.AUTOPILOT == 'on'
```

**Czego `AUTOPILOT` nie potrafi:** pętla nie może go przestawić sama. Klucz
`permissions` nie zna zakresu pozwalającego zapisać zmienną repo ([#5](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/5)). To
przełącznik człowieka, nie bezpiecznik. Stan awaryjny, który pętla ustawia sobie
sama, musi leżeć w pliku w repo albo w przypiętym issue.

---

## Etykiety

Etykieta na issue wybiera zachowanie workflow. Jeden prefiks `rola:` dla wszystkiego,
co wybiera rolę; lista **nie jest zamknięta** — orchestrator dokłada nowe role jako
`rola:<nazwa>` bez tykania workflowów, bo rola to para skill + profil z `.claude/profiles.yml` ([#7](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/7)).

| Etykieta | Znaczenie |
|---|---|
| `rola:orchestrator` | Planuje, tworzy issues, dispatchuje sesje. Jedyna rola tworząca issues. |
| `rola:implementer` | Zmienia kod. Bez internetu. |
| `rola:researcher` | Ma internet. Bez zapisu kodu. |
| `rola:verifier` | Emulator i most do oryginału. Jedyna rola z emulatorem. |
| `rola:bench` | Pseudo-rola: przebieg benchmarku, bez sesji agenta. |

### Nadpisania — lista zamknięta

Domyślnie Sonnet 5 / effort medium. Etykietę nadaje **wyłącznie orchestrator**,
nigdy sesja sama sobie ([#7](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/7)).

| Etykieta | Nadpisuje |
|---|---|
| `model:opus` | model → Opus |
| `effort:high` | effort → high |

### Stan

| Etykieta | Znaczenie |
|---|---|
| `conflict` | Merge nieudany. Issue zostaje **otwarte** i odpala się ponownie ze świeżego HEAD. Konflikt nie jest porażką zadania ([#7](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/7)). |
| `awaria` | Pętla stoi i czeka na człowieka. Ucisza dozorcę ([#25](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/25)). Stawia ją orchestrator albo — gdy ten nie jest w stanie wstać — **dozorca** ([#26](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/26)). |

---

## Uprawnienia

Domyślne uprawnienia workflow w repo są już na minimum i mają takie zostać:

| Ustawienie | Wartość |
|---|---|
| `default_workflow_permissions` | `read` |
| `can_approve_pull_request_reviews` | `false` |

Druga pozycja to w UI checkbox **„Allow GitHub Actions to create and approve pull
requests"**, siedzący tuż pod Workflow permissions. Nazwa mówi o zatwierdzaniu, ale
jedna opcja gasi **dwie** rzeczy: `GITHUB_TOKEN` nie może PR-a zatwierdzić **ani go
otworzyć**.

To jest otwarta sprawa dla [#16](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/16). Przepływ `task/<n>` → PR → merge przez epilog ([#7](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/7)) **nie ruszy**
przy `false`. Checkbox zostaje wyłączony do czasu, aż #16 świadomie zdecyduje, że
pętla potrzebuje PR-ów — i wtedy warto najpierw zapytać, po co jej PR-y, skoro epilog
merguje bezwarunkowo, a benchmark jest nieblokujący ([#8](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/8)). Jeśli PR jest tylko powierzchnią
audytu, znika razem z nim ten checkbox, `pull-requests: write` i przyszła migracja na
GitHub App z [#5](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/5).

Skoro domyślne to `read`, **każdy workflow musi jawnie zadeklarować `permissions:`**.
Minimalne zestawy z [#5](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/5):

| Workflow | `permissions:` |
|---|---|
| orchestrator | `actions: write`, `issues: write`, `contents: write` |
| sesja | `contents: write`, `issues: write`, `actions: write` (+ `pull-requests: write`, jeśli otwiera PR-y) |

`actions: write` jest tym, co pozwala pętli wywołać `workflow_dispatch` na samej sobie.

Osobno, niezależnie od `permissions:`: tryb automation Claude Code **nie nadaje
żadnych uprawnień narzędziowych**. Każdy job musi podać `--permission-mode` i pełną
listę `--allowedTools` ([#4](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/4)).

---

## Ustawienia wyklikiwane ręcznie

Settings → Actions → General. Nie ma dla nich REST API, więc nie ma jak ich
sprawdzić z poziomu sesji — stan poniżej jest deklaracją właściciela, nie pomiarem.

| Ustawienie | Wymagane |
|---|---|
| Send write tokens to workflows from pull requests | **wyłączone** (repo jest publiczne) |
| Require approval for all external contributors | **włączone** (przebiegi z forków) |

Oba potwierdzone przez właściciela 2026-09-20 przy zamykaniu [#13](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/13). Jeśli kiedyś przestaną się
zgadzać, nikt tego nie zauważy automatycznie — dlatego przegląd tych dwóch pozycji
należy do raportu tygodniowego, gdy ten powstanie.

Sekrety repo — w tym `CLAUDE_CODE_OAUTH_TOKEN` — i tak **nie są** przekazywane do
przebiegów z forkowych PR-ów ([#5](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/5)).

---

## Sonda poświadczenia

Ustalone w [#26](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/26). Wygasłe poświadczenie jest jedyną awarią, która **wygląda jak
zdrowie**: sesje startują i padają po ~3 s z `total_cost_usd: 0`, więc przebiegi
powstają, niezmiennik żywotności z [#10](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/10) jest spełniony i dozorca milczy w
nieskończoność. Limitu subskrypcji to **nie pali** — kosztuje wyłącznie ciszę.

Zamiast kalendarza — pomiar w chwili użycia:

```bash
curl -s -o /dev/null -w '%{http_code}' https://api.anthropic.com/v1/models   -H "Authorization: Bearer $CLAUDE_CODE_OAUTH_TOKEN"   -H "anthropic-version: 2023-06-01"   -H "anthropic-beta: oauth-2025-04-20"
# 200 żyje · 401 martwy · 403 odwołany
```

| Gdzie | Po co |
|---|---|
| preflight w workflow sesji | 401/403 kończy job, zanim wstanie agent — zero sesji-zombie |
| dozorca | przy martwym poświadczeniu workflow sesji może nie wstać wcale |

Nagłówek `anthropic-beta: oauth-2025-04-20` jest ten sam, którego używa CLI.
Sonda nie zjada limitu subskrypcji. **`/api/oauth/validate` odpada** — token
z `setup-token` ma scope `user:inference` i dostaje tam 403 także wtedy, gdy jest
zdrowy.

### Reakcja

| Co padło | Skutek |
|---|---|
| poświadczenie, bez którego **nie ruszy nic** | `awaria` + dozorca kończy czerwono → mail do właściciela |
| poświadczenie, bez którego **nie ruszy jedna rola** | sam mail; pętla pracuje dalej |

Mail jest darmowy i nie wymaga nowego poświadczenia: powiadomienia o czerwonych
przebiegach idą do tego, kto przebieg wywołał, a przebieg z `schedule` mailuje do
**autora pliku workflow**. Sesje wywołuje bot, więc mailuje wyłącznie dozorca —
i tylko dlatego, że kończy czerwono celowo. To uchyla zapis z [#10](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/10), że kanału push
nie ma.

---

## Gałąź pętli

**Gałąź pętli to gałąź domyślna repozytorium. Dziś `main`.** Nie są to dwa
pojęcia, które trzeba trzymać w zgodzie — to jedno pojęcie. Wymuszają to dwa
udokumentowane ograniczenia GitHuba, z których żadne nie ma obejścia:

| Ograniczenie | Skutek |
|---|---|
| *„Workflow runs cannot restore caches created for child branches or sibling branches"* — run czyta cache z własnej gałęzi **albo z domyślnej** | Stan emulatora, który wg [#3](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/3) jedzie przez `actions/cache`, nie przechodzi między gałęziami siostrzanymi |
| Workflow na zdarzeniu `issues` odpala się **wyłącznie z pliku na gałęzi domyślnej**; `workflow_dispatch` jest na tej samej liście widoczny dopiero stamtąd | Ludzka ścieżka wejścia `issues: [labeled]` z [#5](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/5) nie działa, dopóki workflowy leżą poza gałęzią domyślną |

### Nazwa nie jest wpisywana na sztywno

Workflow ustala gałąź pętli przez `github.event.repository.default_branch`,
nigdy przez literał `main`.

Powód jest jeden i wystarczający: **pętla nie może edytować `.github/workflows/`**
(akcja twardo tego zabrania). Nazwa wpisana na sztywno byłaby jedyną rzeczą, której
pętla nie umie naprawić, umieszczoną w jedynym miejscu, którego nie umie tknąć.
Przy odczycie z API zmiana nazwy gałęzi pętli to przestawienie gałęzi domyślnej
w ustawieniach repo — bez dotykania jednego pliku workflow.

### Stan emulatora: dwie warstwy cache'u

Sesja pracuje na `task/<n>` ([#7](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/7)), więc **zapisuje** cache wyłącznie w zasięgu własnej
gałęzi — ale **czyta** także z gałęzi domyślnej. Stąd podział:

| Warstwa | Zasięg | Co niesie | Żywotność |
|---|---|---|---|
| Baza | gałąź domyślna | obraz systemu AVD + zainstalowany APK | między sesjami |
| Partia | `task/<n>` | `userdata-qemu.img.qcow2` bieżącej partii | między ogniwami **jednej** sesji |

Świeża sesja weryfikacyjna zaczyna partię od zera i to jest w porządku:
[#9](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/9) wymaga jednej partii ≥1M w obrębie jednego łańcucha ogniw, nie ciągłości
między sesjami.

**Merge na gałąź pętli w trakcie sesji weryfikacyjnej nie unieważnia jej cache'u.**
Wpis cache'u jest związany z kluczem i gałęzią, nie z commitem, a sesja siedzi na
własnym `task/<n>`, którego merge na gałąź domyślną nie dotyka. Pytanie z
[#24](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/24) zamknięte przecząco.

Klucze muszą być nowe przy każdym zapisie (`avd-<warstwa>-${{ github.run_id }}`)
i odczytywane przez `restore-keys`, bo wpis o danym kluczu jest niemutowalny
([#3](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/3) §5.3).
