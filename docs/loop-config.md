# Konfiguracja pętli — sekrety, zmienne, etykiety, uprawnienia

Bilet: [#13](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/13) · mapa: [#1](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/1)
Źródła ustaleń: [#4](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/4) (uwierzytelnianie), [#5](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/5) (samowyzwalanie i uprawnienia), [#7](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/7) (role)

Kontrakt nazw między workflowami a sesjami. Workflow, który odwołuje się do nazwy
spoza tej listy, jest błędem — nie okazją do dopisania nowej nazwy bez decyzji.

---

## Sekrety

| Nazwa | Przeznaczenie |
|---|---|
| `CLAUDE_CODE_OAUTH_TOKEN` | Jedyne poświadczenie generowane ręcznie. Uwierzytelnia sesje Claude Code subskrypcją właściciela. Powstaje z `claude setup-token`, ważny rok. |

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

---

## Uprawnienia

Domyślne uprawnienia workflow w repo są już na minimum i mają takie zostać:

| Ustawienie | Wartość |
|---|---|
| `default_workflow_permissions` | `read` |
| `can_approve_pull_request_reviews` | `false` |

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

Sekrety repo — w tym `CLAUDE_CODE_OAUTH_TOKEN` — i tak **nie są** przekazywane do
przebiegów z forkowych PR-ów ([#5](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/5)).
