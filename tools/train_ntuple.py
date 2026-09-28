"""
TD(0) po stanach następczych do trenowania `ntuple.NTupleValue` (#123, #140).

Wznawialny na wzór `tools/tune_weights.py --state` (#104). RNG partii jest
wyprowadzony z `(seed, numer odcinka)` — wznowienie po śmierci sesji rozegra
dokładnie te partie, co przebieg nieprzerwany.

    python tools/train_ntuple.py --state ntuple-state.json --out ntuple-weights.json \\
        --episodes 2 --seed 1

Polityka behawioralna (ta, którą trenujemy i którą zbieramy dane) jest zachłanna
o jeden pół-ruch w przód, tak jak `HeuristicPolicy`, tylko wartość liścia liczy
sieć N-tuple, nie `weights · features(board)`: dla każdej legalnej akcji z bieżącej
tacki liczy `r + ntuple.value(afterstate)` i wybiera najlepszą. Afterstate =
plansza zaraz po postawieniu i ewentualnym czyszczeniu linii, przed dociągiem
kolejnej tacki — to jest ten sam punkt, w którym TD(0) n-tuple w 2048/SZ-Tetris
robi aktualizację (`docs/research/przeszukanie-z-wyuczona-ocena.md`, sekcja 1).

Aktualizacja TD(0) po każdym kroku (poza pierwszym):

    target = r_t + V(afterstate_t)
    V(afterstate_{t-1}) += alpha * (target - V(afterstate_{t-1}))

gdzie `r_t` to nagroda ruchu wybranego z `afterstate_{t-1}` (ten, co prowadzi
do `afterstate_t`), i jedna dodatkowa aktualizacja po ostatnim kroku partii, z
`target = 0` (stan terminalny — gra się skończyła, żadnej przyszłej nagrody nie
będzie).

Stan `--reward score` zapisany przed poprawką #153 (cel liczony jako
`r_{t-1} + V(afterstate_t)`) nie wczyta się do wznowienia: `load_state` sprawdza
pole `params.td_target` i rzuca `ValueError`, żeby nie zmieszać w jednym
przebiegu wag uczonych dwoma różnymi celami bez śladu (`docs/ntuple.md`, sekcja
„Kształt nagrody użyty w TD"). `--reward survival` nie jest tym dotknięty:
`r ≡ 1` niezależnie od przesunięcia, więc stare stany survival wczytują się
bez zmian.

Sygnał uczenia `r` wybiera `--reward` (#140) — to opcja treningu, nie nagroda
środowiska; `Game.step` i punktacja są nietknięte:

- `score` (domyślnie): `r = gain`, dokładnie to, co zwraca
  `policies._simulate_placement` (ten sam wzór co `Game.apply_placement`);
- `survival`: `r = 1` za każde postawienie, więc V szacuje liczbę pozostałych
  postawień.

Układ łat `--layout` (#149, domyślnie `A`) wybiera `ntuple.LAYOUTS` — `AD` dodaje
kwadraty 3x3 do wierszy/kolumn wariantu `A`, `ADC` (#162) dodaje do `AD` prostokąty
2x3/3x2, patrz `docs/ntuple.md`. Wznowienie z innym układem niż zapisany w stanie
rzuca `ValueError`, jak zmiana `--reward`.

Seedy treningowe są rozłączne z `bench/seeds_fixed.json`, wymuszone asercją w
`episode_seed()` — tak jak `tools/tune_weights.training_seeds()` (#59, #123).
Seedy ewaluacji (`--eval-every`) leżą w przedziale `[2**31, 2**32)`, poza
zakresem seedów treningu i rotowanych seedów benchmarku (`[1, 2**31 - 1)`),
i są rozłączne z `bench/seeds_fixed.json` — `eval_seeds()`.

Zapis (#140): stan (wagi + małe liczniki) i wagi idą na dysk co `--save-every`
odcinków, przy każdej ewaluacji i na końcu wywołania; log odcinków jest
dopisywany przyrostowo do `<stan>.log.jsonl`. Koszt zapisu nie zależy od
liczby odcinków za nami.

Starty z późnej gry (#168): `--start-states <plik> --start-prob <p>` — z
prawdopodobieństwem `p` odcinek startuje z planszy wylosowanej z `<plik>`
(zebranego `tools/collect_states.py`) zamiast z pustej. Tacka i dalsze klocki
nadal pochodzą z generatora gry na seed odcinka, dokładnie jak dziś — plik
podmienia tylko `Game.board`, przez `Game.set_board` (nieinwazyjne wobec
`step`/punktacji). Wybór (start z pliku czy nie, który wpis) jest
deterministyczny z `(--seed, numer_odcinka)`, przez `random.Random` niezależny
od tego, który wybiera seed partii (`episode_seed`) — wznowienie w połowie
odtwarza dokładnie ten sam wybór co przebieg ciągły. Bez `--start-states`
(domyślnie) zachowanie jest bitowo takie samo jak przed #168: `choose_start_board`
zwraca `None` bez tworzenia jakiegokolwiek `random.Random`. `--start-states`/
`--start-prob` nie wchodzą do `params` sprawdzanych przy wznowieniu — można je
dodać do stanu zapisanego bez nich (i zmieniać między wywołaniami), bo nie
zmieniają kształtu tego, co trening mierzy (seed/alpha/move_cap/reward/layout),
tylko to, skąd startuje plansza. Ewaluacja (`--eval-every`) zawsze startuje z
pustej planszy, niezależnie od tych flag.
"""
import argparse
import glob
import json
import os
import random
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game import Game
from ntuple import DEFAULT_LAYOUT, LAYOUTS, REWARD_SCORE, REWARD_SURVIVAL, REWARDS, NTupleValue, board_bits
from policies import _placement_gain, _simulate_placement

BENCH_CONFIG = "bench/config.json"
DEFAULT_OUT = "ntuple-weights.json"
DEFAULT_ALPHA = 0.001
DEFAULT_SAVE_EVERY = 100
# Okno krzywej uczenia, jak w `docs/data/ntuple-krzywa.json` (#126).
CURVE_WINDOW = 2000
# Odcinkow na plik logu (#187): pomiar istniejacych logow `ntuple/*.log.jsonl`
# (ADC/ADC-ss, 100k odcinkow kazdy) daje max 164 B/wpis, srednio 142-150 B/wpis.
# Przy 150 000 odcinkow/blok to najwyzej ~24,6 MB/plik — pod limitem GitHuba
# (40 MB z kryterium akceptacji, 100 MB odrzucenia) z zapasem. Patrz
# `docs/ntuple-szybkosc.md`, sekcja rotacji logu.
BLOCK_EPISODES = 150_000
STATE_FORMAT = 2
# Cel TD zapisywany w `params.td_target` (#153): odróżnia stan zapisany po
# poprawce przesunięcia od stanu sprzed niej (brak pola — cel liczył
# `r_{t-1} + V(afterstate_t)`, dziś `r_t + V(afterstate_t)`).
TD_TARGET_VERSION = "r_t"

# Seedy treningu (`episode_seed`) i rotowane seedy benchmarku
# (`benchmark.rotated_seeds`) są z `[1, 2**31 - 1)`. Ewaluacja bierze seedy
# z przedziału powyżej — rozłączne z obydwoma dla każdego numeru issue.
TRAINING_SEED_HIGH = 2**31 - 1
EVAL_SEED_LOW = 2**31
EVAL_SEED_HIGH = 2**32


def load_bench_seeds(config):
    with open(config["fixed_seed_file"], encoding="utf-8") as fh:
        return set(json.load(fh)[: config["n_seeds"]])


def episode_seed(seed, episode_number, forbidden):
    """Seed partii danego odcinka: deterministyczny z `(seed, episode_number)`,
    rozłączny z `bench/seeds_fixed.json` (#123).

    Kolizja z zakazanym zbiorem jest rozstrzygana dodatkową solą, wyprowadzoną
    wciąż tylko z `(seed, episode_number)` — bez zależności od historii
    poprzednich odcinków, więc wynik jest identyczny w przebiegu ciągłym i
    wznowionym."""
    salt = 0
    while True:
        candidate = random.Random(
            "train_ntuple:{0}:{1}:{2}".format(seed, episode_number, salt)
        ).randrange(1, TRAINING_SEED_HIGH)
        if candidate not in forbidden:
            assert candidate not in forbidden, "seed treningowy pokrywa sie z bench/seeds_fixed.json"
            return candidate
        salt += 1


def load_start_states(path):
    """Plansze startowe zebrane przez `tools/collect_states.py` (#168).

    Akceptuje format tego narzędzia (`{"boards": [{"board": ..., ...}, ...]}`)
    i, dla prostoty testów, zwykłą listę plansz — w obu przypadkach zwraca
    listę samych siatek."""
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    entries = data["boards"] if isinstance(data, dict) else data
    return [entry["board"] if isinstance(entry, dict) else entry for entry in entries]


def choose_start_board(states, seed, episode_number, prob):
    """Plansza startowa odcinka (#168): z prawdopodobieństwem `prob` wylosowana
    z `states`, inaczej `None` (pusta plansza, dzisiejsze zachowanie).

    Deterministyczne z `(seed, episode_number)`, przez `random.Random` w
    osobnej przestrzeni nazw niż `episode_seed` — nie zużywa jego RNG, więc
    dodanie tej flagi nie zmienia seeda partii. Gdy `states` jest puste albo
    `prob <= 0`, nie tworzy żadnego `random.Random` — bit-identyczne z
    zachowaniem bez `--start-states`."""
    if not states or prob <= 0:
        return None
    rng = random.Random("train_ntuple_start_state:{0}:{1}".format(seed, episode_number))
    if rng.random() >= prob:
        return None
    return rng.choice(states)


def eval_seeds(n, forbidden):
    """`n` seedów ewaluacji, te same w każdym punkcie i w każdym przebiegu (#140).

    Nie zależą od `--seed`, więc dwa treningi z różnymi sygnałami oceniane są na
    tych samych partiach. Rozłączne z `bench/seeds_fixed.json` (asercja) i —
    przez przedział `[2**31, 2**32)` — z seedami treningu i rotowanymi seedami
    benchmarku."""
    seeds = []
    index = 0
    while len(seeds) < n:
        candidate = random.Random("eval_ntuple:{0}".format(index)).randrange(
            EVAL_SEED_LOW, EVAL_SEED_HIGH
        )
        index += 1
        if candidate in forbidden or candidate in seeds:
            continue
        assert candidate >= TRAINING_SEED_HIGH, "seed ewaluacji w zakresie seedow treningu/rotowanych"
        assert candidate not in forbidden, "seed ewaluacji pokrywa sie z bench/seeds_fixed.json"
        seeds.append(candidate)
    return seeds


def step_reward(reward, gain):
    """Sygnał uczenia za jedno postawienie: `gain` gry albo `1` (przeżycie)."""
    return 1 if reward == REWARD_SURVIVAL else gain


def _choose_action(ntuple, game, actions, reward=REWARD_SCORE):
    """Zachłanna o jeden pół-ruch w przód wg `r + ntuple.value(afterstate)`.

    Zwraca `(akcja, indeksy łat afterstate, r)` — indeksy i `r` są od razu
    potrzebne do aktualizacji TD, nie ma po co liczyć ich drugi raz.

    Z rdzeniem natywnym (#184) stany następcze i ich wartości liczy
    `ntuple_native` (`_choose_action_native`), bitowo to samo; indeksy łat są
    wtedy tablicą C, którą `NTupleValue` przyjmuje tak jak listę."""
    core = getattr(ntuple, "native", None)
    if core is not None:
        chosen = _choose_action_native(core, game, actions, reward)
        if chosen is not None:
            return chosen
    best_action, best_idxs, best_r, best_score = None, None, None, None
    for action in actions:
        gain, board_after = _simulate_placement(game, action)
        r = step_reward(reward, gain)
        idxs = ntuple.indices(board_after)
        score = r + ntuple.value_from_indices(idxs)
        if best_score is None or score > best_score:
            best_action, best_idxs, best_r, best_score = action, idxs, r, score
    return best_action, best_idxs, best_r


def _choose_action_native(core, game, actions, reward):
    """`_choose_action` na rdzeniu: `None`, gdy rdzeń tej decyzji nie policzy
    (nieobsługiwany klocek, nielegalna akcja) — wtedy liczy pętla Pythona.

    `survival`: `r = 1` dla każdej akcji, najlepszą wybiera rdzeń. `score`:
    rdzeń oddaje wartości, liczbę linii i pustość planszy po każdej akcji, a
    `gain` składa `policies._placement_gain` z tych samych funkcji punktacji co
    `_simulate_placement`; porównanie `r + V` idzie w Pythonie, w tej samej
    kolejności i z tym samym rozstrzyganiem remisów."""
    if not actions or not core.set_tray(game.pieces):
        return None
    bits = board_bits(game.board)
    if reward == REWARD_SURVIVAL:
        r = step_reward(reward, None)
        res = core.afterstates(bits, actions, r_const=r)
        if res is None:
            return None
        best, idx = res
        return actions[best], idx, r
    res = core.afterstates(bits, actions)
    if res is None:
        return None
    values, lines, empty = res
    gains = {}
    best, best_r, best_score = None, None, None
    for k, action in enumerate(actions):
        key = (action[0], lines[k], empty[k])
        gain = gains.get(key)
        if gain is None:
            gain = gains[key] = _placement_gain(game, action[0], key[1], key[2])
        r = step_reward(reward, gain)
        score = r + values[k]
        if best_score is None or score > best_score:
            best, best_r, best_score = k, r, score
    return actions[best], core.afterstate_indices(bits, actions[best]), best_r


def run_episode(ntuple, seed, move_cap, alpha, reward=REWARD_SCORE, learn=True, start_board=None):
    """Jedna partia; przy `learn` z aktualizacją TD(0) po każdym postawieniu.

    `start_board` (#168, opcjonalne): plansza, z której partia startuje zamiast
    pustej — `None` (domyślnie) to dzisiejsze zachowanie bit w bit. Tacka,
    generator, wynik i combo startują jak zwykle; zmienia się tylko
    `Game.board` (`Game.set_board`, nieinwazyjne wobec `step`/punktacji).

    Cel dla `V(afterstate_{t-1})` to `r_t + V(afterstate_t)`, gdzie `r_t` jest
    nagrodą ruchu wybranego **z** `afterstate_{t-1}` (ten, który prowadzi do
    `afterstate_t`) — to jest `r` policzone w bieżącej iteracji pętli, nie w
    poprzedniej (#153: przed poprawką cel używał `r_{t-1}`, nagrody ruchu,
    który dopiero doprowadził do `afterstate_{t-1}`, więc `gain` tego ruchu był
    liczony do wartości dwa razy — raz w V, raz wprost w polityce).

    Zwraca statystyki partii (do logu) — same wagi `ntuple` są modyfikowane
    w miejscu. `learn=False` to ewaluacja: ta sama polityka, wagi nietknięte."""
    game = Game(seed=seed)
    if start_board is not None:
        game.set_board(start_board)
    prev_idxs = None
    steps = 0
    td_errors = []
    while not game.done and steps < move_cap:
        actions = game.available_actions()
        if not actions:
            break
        action, idxs, r = _choose_action(ntuple, game, actions, reward)
        if learn and prev_idxs is not None:
            target = r + ntuple.value_from_indices(idxs)
            error = target - ntuple.value_from_indices(prev_idxs)
            ntuple.update(prev_idxs, alpha * error)
            td_errors.append(error)
        game.step(action)
        prev_idxs = idxs
        steps += 1

    if learn and prev_idxs is not None:
        # Stan terminalny: żadnej przyszłej nagrody nie będzie, target = 0.
        error = 0.0 - ntuple.value_from_indices(prev_idxs)
        ntuple.update(prev_idxs, alpha * error)
        td_errors.append(error)

    return {
        "seed": seed,
        "score": game.score,
        "placements": game.placements,
        "steps": steps,
        "mean_abs_td_error": round(statistics.mean(abs(e) for e in td_errors), 4) if td_errors else 0.0,
        "start_from_file": start_board is not None,
    }


def evaluate(ntuple, seeds, move_cap, reward):
    """Partie na `seeds` zachłanną polityką treningu, bez uczenia."""
    games = [run_episode(ntuple, s, move_cap, 0.0, reward, learn=False) for s in seeds]
    return {
        "sredni_wynik": round(statistics.mean(g["score"] for g in games), 2),
        "srednie_przezycie": round(statistics.mean(g["placements"] for g in games), 2),
        "n_partii": len(games),
    }


def log_block(episode):
    """Numer bloku (0-indeksowany) pliku logu dla danego numeru odcinka (#187)."""
    return (episode - 1) // BLOCK_EPISODES


def log_path(state_path, episode=None):
    """Plik logu bloku zawierającego dany odcinek (#187): rotacja co
    `BLOCK_EPISODES` odcinków, żeby żaden plik logu nie rósł bez granic przy
    milionie odcinków. Blok 0 (`episode` `None` albo w `[1, BLOCK_EPISODES]`)
    zachowuje nazwę sprzed rotacji (`<stan>.log.jsonl`) — istniejące pliki w
    `ntuple/` (wszystkie < `BLOCK_EPISODES` odcinków) wczytują się bez zmiany
    nazwy."""
    base = os.path.splitext(state_path)[0]
    block = log_block(episode) if episode else 0
    if block <= 0:
        return base + ".log.jsonl"
    return "{0}.log.{1:04d}.jsonl".format(base, block)


def _log_block_paths(state_path):
    """Pliki logu wszystkich bloków tego stanu, w kolejności odcinków."""
    base = os.path.splitext(state_path)[0]
    found = []
    legacy = base + ".log.jsonl"
    if os.path.exists(legacy):
        found.append((0, legacy))
    prefix = base + ".log."
    for path in glob.glob(prefix + "[0-9]" * 4 + ".jsonl"):
        suffix = path[len(prefix):-len(".jsonl")]
        if suffix.isdigit():
            found.append((int(suffix), path))
    found.sort()
    return [path for _, path in found]


def read_log(state_path):
    """Wpisy logu odcinków, ze wszystkich bloków (#187), w kolejności odcinków
    (do testów i analizy; trening go nie czyta)."""
    entries = []
    for path in _log_block_paths(state_path):
        with open(path, encoding="utf-8") as fh:
            entries.extend(json.loads(line) for line in fh if line.strip())
    return entries


def _append_log_entries(state_path, entries):
    """Dopisuje `entries` do plików bloków logu, grupując po bloku (#187).
    Zwykle wszystkie trafiają do jednego pliku (`BLOCK_EPISODES` jest dużo
    większe niż `--save-every`), ale kod poprawnie obsługuje partię, która
    przecina granicę bloku."""
    groups = {}
    order = []
    for entry in entries:
        block = log_block(entry["episode"])
        if block not in groups:
            groups[block] = []
            order.append(block)
        groups[block].append(entry)
    for block in order:
        block_entries = groups[block]
        path = log_path(state_path, block_entries[0]["episode"])
        with open(path, "a", encoding="utf-8") as fh:
            for entry in block_entries:
                fh.write(json.dumps(entry) + "\n")


def _add_to_windows(windows, entry):
    """Dopisuje odcinek do akumulatorów okien krzywej (`CURVE_WINDOW` odcinków)."""
    start = (entry["episode"] - 1) // CURVE_WINDOW * CURVE_WINDOW + 1
    if not windows or windows[-1]["od_odcinka"] != start:
        windows.append({
            "od_odcinka": start, "do_odcinka": start, "n_odcinkow": 0,
            "suma_wyniku": 0, "suma_przezycia": 0, "suma_bledu_td": 0.0,
        })
    window = windows[-1]
    window["do_odcinka"] = entry["episode"]
    window["n_odcinkow"] += 1
    window["suma_wyniku"] += entry["score"]
    window["suma_przezycia"] += entry["placements"]
    window["suma_bledu_td"] += entry["mean_abs_td_error"]


def new_state(args, forbidden_seeds):
    return {
        "format": STATE_FORMAT,
        "episode": 0,
        "episodes_target": args.episodes,
        "weights": None,  # wypelnione przy pierwszym zapisie
        "games_played": 0,
        "duration_s": 0.0,
        "params": {
            "seed": args.seed,
            "alpha": args.alpha,
            "move_cap": args.move_cap,
            "reward": args.reward,
            "layout": args.layout,
            "td_target": TD_TARGET_VERSION,
        },
        "bench_seeds_n": len(forbidden_seeds),
        "log_bytes": 0,
        "windows": [],
        "eval": {"every": None, "episodes": None, "points": [], "best": None},
    }


def _migrate_v1(path, state):
    """Stan sprzed #140 trzymał cały log w sobie: przenosi go do plików bloków
    logu (#187) i liczy z niego okna krzywej. Jednorazowe; potem stan ma stały
    rozmiar. Stan sprzed #140 był zawsze mały (dużo poniżej `BLOCK_EPISODES`),
    więc migracja zawsze trafia do bloku 0 (`<stan>.log.jsonl`)."""
    log = state.pop("log")
    windows = []
    _append_log_entries(path, log)
    for entry in log:
        _add_to_windows(windows, entry)
    last_episode = log[-1]["episode"] if log else 0
    lp = log_path(path, last_episode) if last_episode else log_path(path)
    state["log_bytes"] = os.path.getsize(lp) if os.path.exists(lp) else 0
    state["windows"] = windows
    state["format"] = STATE_FORMAT
    state.setdefault("eval", {"every": None, "episodes": None, "points": [], "best": None})


def load_state(path, args, forbidden_seeds):
    with open(path, encoding="utf-8") as fh:
        state = json.load(fh)
    # Stan sprzed #140 nie ma pola `reward` — trenował na `gain`.
    state["params"].setdefault("reward", REWARD_SCORE)
    # Stan sprzed #149 nie ma pola `layout` — trenował na wariancie A.
    state["params"].setdefault("layout", DEFAULT_LAYOUT)
    # Stan `score` sprzed #153 liczyl cel TD jako r_{t-1} + V(afterstate_t) —
    # nieporownywalny z dzisiejszym r_t + V(afterstate_t). `survival` ma r ≡ 1,
    # wiec przesuniecie sie znosi i stare stany wczytuja sie bez zmian.
    if state["params"]["reward"] == REWARD_SCORE and state["params"].get("td_target") != TD_TARGET_VERSION:
        raise ValueError(
            "stan {0}: cel TD zapisany przed #153 (r_t-1 + V(afterstate_t)) nie jest "
            "porownywalny z poprawionym kodem (r_t + V(afterstate_t)) dla --reward score "
            "— zacznij nowy plik stanu".format(path)
        )
    state["params"].setdefault("td_target", TD_TARGET_VERSION)
    # Wznowienie z innymi parametrami dalo by przebieg, ktorego log klamie o tym,
    # co mierzyl (wzor z tools/tune_weights.load_state, #104).
    expected = {
        "seed": args.seed, "alpha": args.alpha, "move_cap": args.move_cap, "reward": args.reward,
        "layout": args.layout,
    }
    for key, value in expected.items():
        if state["params"][key] != value:
            raise ValueError(
                "stan {0}: parametr {1} ({2}) nie zgadza sie z wywolaniem ({3})".format(
                    path, key, state["params"][key], value
                )
            )
    if state["bench_seeds_n"] != len(forbidden_seeds):
        raise ValueError(
            "stan {0} liczy inna liczbe zakazanych seedow bench — inna konfiguracja".format(path)
        )
    if "log" in state:
        _migrate_v1(path, state)
    ev = state["eval"]
    if ev["points"] and (ev["every"], ev["episodes"]) != (args.eval_every, args.eval_episodes):
        # Najlepszy punkt z innego zestawu partii ewaluacji nie jest porownywalny.
        raise ValueError(
            "stan {0}: ewaluacja co {1} na {2} partiach nie zgadza sie z wywolaniem "
            "(co {3} na {4})".format(path, ev["every"], ev["episodes"], args.eval_every, args.eval_episodes)
        )
    # Log dopisany przed zapisem stanu, ktory nie doszedl (smierc sesji miedzy
    # jednym a drugim): odcinamy go do dlugosci zgodnej ze stanem. `log_bytes`
    # opisuje tylko plik bloku aktywnego w chwili ostatniego udanego zapisu
    # (#187) — wczesniejsze bloki sa juz zamkniete i nie sa dalej dopisywane.
    lp = log_path(path, state["episode"]) if state["episode"] else log_path(path)
    if os.path.exists(lp) and os.path.getsize(lp) > state["log_bytes"]:
        os.truncate(lp, state["log_bytes"])
    state["episodes_target"] = args.episodes
    return state


def write_json(path, data, indent=2):
    """Zapis przez plik tymczasowy i `os.replace` — przerwany zapis nie psuje pliku."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=indent)
    os.replace(tmp, path)


def weights_payload(ntuple, **extra):
    data = ntuple.to_dict()
    data.update(extra)
    return data


def curve(state):
    """Krzywa: okna treningu w formacie `docs/data/ntuple-krzywa.json` plus ewaluacja."""
    okna = []
    for w in state["windows"]:
        n = w["n_odcinkow"]
        okna.append({
            "od_odcinka": w["od_odcinka"],
            "do_odcinka": w["do_odcinka"],
            "n_odcinkow": n,
            "sredni_wynik": round(w["suma_wyniku"] / n, 2),
            "srednie_przezycie": round(w["suma_przezycia"] / n, 2),
            "sredni_abs_blad_td": round(w["suma_bledu_td"] / n, 4),
        })
    params = state["params"]
    return {
        "opis": "Sredni wynik i srednie przezycie polityki behawioralnej (zachlanna, N-tuple) "
                "w kolejnych oknach treningu oraz punkty ewaluacji bez uczenia (#140)",
        "params": params,
        "seed": params["seed"],
        "n_odcinkow_lacznie": state["episode"],
        "rozmiar_okna": CURVE_WINDOW,
        "okna": okna,
        "ewaluacja": {
            "co_ile_odcinkow": state["eval"]["every"],
            "n_partii": state["eval"]["episodes"],
            "punkty": state["eval"]["points"],
            "najlepszy": state["eval"]["best"],
        },
    }


def save(args, state, ntuple, pending_log):
    """Dopisuje zbuforowany log (do plików bloków, #187), potem wagi, stan i
    krzywą. Kolejność ma znaczenie: stan zapisany jako ostatni jest punktem,
    od którego rusza wznowienie."""
    if pending_log:
        _append_log_entries(args.state, pending_log)
        pending_log.clear()
    lp = log_path(args.state, state["episode"]) if state["episode"] else log_path(args.state)
    state["log_bytes"] = os.path.getsize(lp) if os.path.exists(lp) else 0
    state["weights"] = ntuple.weights
    write_json(args.out, weights_payload(ntuple))
    write_json(args.state, state)
    if args.curve_out:
        write_json(args.curve_out, curve(state))


def run_eval(args, state, ntuple, seeds):
    point = dict(odcinki=state["episode"], **evaluate(ntuple, seeds, args.move_cap, args.reward))
    ev = state["eval"]
    ev["points"].append(point)
    improved = ev["best"] is None or point["sredni_wynik"] > ev["best"]["sredni_wynik"]
    if improved:
        # Kryterium wyboru to wynik dla obu sygnałów — cel pętli to punkty (#140).
        ev["best"] = point
        write_json(args.best_out, weights_payload(ntuple, ewaluacja=point))
    print(
        "ewaluacja po {0} odcinkach: wynik_sr={1} przezycie_sr={2} ({3} partii){4}".format(
            point["odcinki"], point["sredni_wynik"], point["srednie_przezycie"],
            point["n_partii"], " — NAJLEPSZA, zapisano " + args.best_out if improved else "",
        ),
        file=sys.stderr,
    )


def run_generational(args, config, forbidden_seeds):
    layout = LAYOUTS[args.layout]
    if os.path.exists(args.state):
        state = load_state(args.state, args, forbidden_seeds)
        ntuple = NTupleValue(weights=state["weights"], reward=args.reward, layout=layout) if state["weights"] \
            else NTupleValue(reward=args.reward, layout=layout)
        print(
            "Wznawiam {0}: odcinek {1}/{2}".format(args.state, state["episode"], args.episodes),
            file=sys.stderr,
        )
    else:
        state = new_state(args, forbidden_seeds)
        ntuple = NTupleValue(reward=args.reward, layout=layout)
        for lp in _log_block_paths(args.state):
            os.remove(lp)  # log osierocony po stanie, ktorego juz nie ma
        print("Nowy przebieg {0}: 0/{1} odcinkow".format(args.state, args.episodes), file=sys.stderr)

    seeds_eval = None
    if args.eval_every:
        state["eval"]["every"] = args.eval_every
        state["eval"]["episodes"] = args.eval_episodes
        seeds_eval = eval_seeds(args.eval_episodes, forbidden_seeds)

    start_states = load_start_states(args.start_states) if args.start_states else None

    pending_log = []
    ran = 0
    while state["episode"] < args.episodes and ran < args.episodes_per_run:
        episode = state["episode"] + 1
        seed = episode_seed(args.seed, episode, forbidden_seeds)
        start_board = choose_start_board(start_states, args.seed, episode, args.start_prob)
        started = time.time()
        stats = run_episode(ntuple, seed, args.move_cap, args.alpha, args.reward, start_board=start_board)
        elapsed = time.time() - started

        state["episode"] = episode
        state["games_played"] += 1
        # Suma bez zaokraglania po kazdym odcinku (#158, odkrycie #149):
        # round() na skumulowanej wartosci gubil przyrosty krotsze niz ~0,05 s,
        # bo kazdy kolejny dodawal do juz zaokraglonej (czesto z powrotem do 0.0)
        # sumy zamiast do prawdziwego czasu dotychczas zmierzonego.
        state["duration_s"] += elapsed
        entry = dict(stats)
        entry["episode"] = episode
        entry["duration_s"] = round(elapsed, 3)
        pending_log.append(entry)
        _add_to_windows(state["windows"], entry)
        ran += 1
        print(
            "odcinek {0}/{1}: seed={2} wynik={3} postawienia={4} "
            "|blad_td|_sr={5} ({6} s)".format(
                episode, args.episodes, seed, stats["score"], stats["placements"],
                stats["mean_abs_td_error"], entry["duration_s"],
            ),
            file=sys.stderr,
        )

        evaluated = bool(args.eval_every) and episode % args.eval_every == 0
        if evaluated:
            run_eval(args, state, ntuple, seeds_eval)
        last = state["episode"] >= args.episodes or ran >= args.episodes_per_run
        if evaluated or last or episode % args.save_every == 0:
            save(args, state, ntuple, pending_log)

    if ran == 0:
        save(args, state, ntuple, pending_log)

    done = state["episode"] >= args.episodes
    print(
        "Zapisano {0} i {1} ({2}/{3} odcinkow{4}, {5} partii)".format(
            args.out, args.state, state["episode"], args.episodes,
            ", KONIEC" if done else "", state["games_played"],
        )
    )
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="TD(0) po stanach następczych: trener sieci N-tuple (#123, #140)"
    )
    parser.add_argument("--state", required=True, help="plik stanu treningu (wznawialny)")
    parser.add_argument("--out", default=DEFAULT_OUT, help="plik wag ntuple.NTupleValue")
    parser.add_argument("--episodes", type=int, required=True, help="docelowa liczba odcinkow")
    parser.add_argument(
        "--episodes-per-run", type=int, default=1,
        help="ile odcinkow liczy jedno wywolanie (domyslnie 1: jedno wywolanie = jeden odcinek)",
    )
    parser.add_argument("--seed", type=int, default=0, help="seed RNG odcinkow treningowych")
    parser.add_argument("--alpha", type=float, default=DEFAULT_ALPHA, help="krok TD(0)")
    parser.add_argument("--move-cap", type=int, default=None, help="sufit postawien na partie")
    parser.add_argument(
        "--reward", choices=REWARDS, default=REWARD_SCORE,
        help="sygnal uczenia: score = gain gry, survival = 1 za postawienie (domyslnie score)",
    )
    parser.add_argument(
        "--layout", choices=sorted(LAYOUTS), default=DEFAULT_LAYOUT,
        help="uklad lat N-tuple: A = 8 wierszy+8 kolumn (domyslnie), "
             "AD = A plus kwadraty 3x3 we wszystkich polozeniach (ntuple.LAYOUTS, #149), "
             "ADC = AD plus prostokaty 2x3/3x2 we wszystkich polozeniach (#162)",
    )
    parser.add_argument(
        "--save-every", type=int, default=DEFAULT_SAVE_EVERY,
        help="co ile odcinkow zapisac stan i wagi (plus przy ewaluacji i na koncu wywolania); "
             "przerwany blok traci najwyzej tyle minus jeden odcinkow",
    )
    parser.add_argument(
        "--eval-every", type=int, default=None,
        help="co ile odcinkow treningu grac partie ewaluacyjne bez uczenia",
    )
    parser.add_argument(
        "--eval-episodes", type=int, default=20, help="liczba partii jednej ewaluacji",
    )
    parser.add_argument(
        "--best-out", default=None,
        help="plik wag nadpisywany, gdy sredni wynik ewaluacji jest najlepszy dotad",
    )
    parser.add_argument(
        "--curve-out", default=None,
        help="plik krzywej: okna treningu (jak docs/data/ntuple-krzywa.json) i punkty ewaluacji",
    )
    parser.add_argument(
        "--start-states", default=None,
        help="plik plansz z tools/collect_states.py (#168); z --start-prob>0 odcinki startuja "
             "z wylosowanej z niego planszy zamiast pustej (tacka nadal z generatora na seed odcinka)",
    )
    parser.add_argument(
        "--start-prob", type=float, default=0.0,
        help="prawdopodobienstwo startu odcinka z pliku --start-states (domyslnie 0: zawsze pusta plansza)",
    )
    parser.add_argument("--config", default=BENCH_CONFIG)
    args = parser.parse_args(argv)

    if args.save_every < 1:
        parser.error("--save-every musi byc >= 1")
    if not 0.0 <= args.start_prob <= 1.0:
        parser.error("--start-prob musi byc w [0, 1]")
    if args.start_prob and not args.start_states:
        parser.error("--start-prob > 0 wymaga --start-states")
    if args.eval_every is not None:
        if args.eval_every < 1 or args.eval_episodes < 1:
            parser.error("--eval-every i --eval-episodes musza byc >= 1")
        if not args.best_out:
            parser.error("--eval-every wymaga --best-out")
    else:
        args.eval_episodes = None

    with open(args.config, encoding="utf-8") as fh:
        config = json.load(fh)
    if args.move_cap is None:
        args.move_cap = config["move_cap"]

    forbidden_seeds = load_bench_seeds(config)
    return run_generational(args, config, forbidden_seeds)


if __name__ == "__main__":
    sys.exit(main())
