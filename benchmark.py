"""
Benchmark bota Block Blast — narzędzie uruchamialne.

Realizuje definicję z #8: dwa zestawy po N seedów (stały + rotowany), eps = 0,
twardy sufit ruchów, trójstronny pomiar kandydat/poprzednik/rekordzista przez
TEN SAM, aktualny symulator, parowanie na wspólnych seedach.

    python benchmark.py --candidate greedy --previous random --issue 17
    python benchmark.py --candidate model/model.pth --previous w-abc/model.pth --issue 17

Wynik: maszynowy rekord `bench/<sha>.json` + czytelne podsumowanie na stdout.
Próg jest etykietą dla orchestratora, nie bramką — benchmark nigdy nie kończy
się kodem błędu z powodu regresji.
"""
import argparse
import hashlib
import json
import math
import multiprocessing
import os
import random
import statistics
import subprocess
import sys
import time

from features import ALL_FEATURE_NAMES, FEATURE_NAMES
from game import Game
from ntuple import NTupleValue
from policies import (
    GreedyPolicy,
    HeuristicPolicy,
    LookaheadPolicy,
    ModelPolicy,
    NTupleLookaheadPolicy,
    RandomPolicy,
    TrayPolicy,
)

CONFIG_PATH = "bench/config.json"
# Jawna lista, nie glob (#102): dopisanie pliku, który wpływa na mierzoną
# liczbę, ma być świadomą decyzją, a nie efektem ubocznym `os.listdir`.
HASHED_SOURCES = [
    "game.py",
    "scoring.py",
    "generator.py",
    "pieces.py",
    "features.py",
    "policies.py",
    "benchmark.py",
    # Ocena liścia ramienia `lookahead-ntuple:` żyje w `ntuple.py` — bez niego
    # odcisk źródeł nie widzi zmiany mierzonej polityki (#127, #140).
    "ntuple.py",
    # Rdzeń natywny N-tuple (#184): liczy wartości liścia i wiązkę
    # `lookahead-ntuple`, a jego opakowanie decyduje, kiedy liczy Python.
    "ntuple_native.c",
    "ntuple_native.py",
]

STATUS_OK = "ok"
STATUS_BLOCKED = "blocked"


class ArmUnavailable(Exception):
    """Zażądano ramienia pomiaru, którego nie da się załadować (#21: kończy `blocked`)."""


def load_config(path=CONFIG_PATH):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def fixed_seeds(config):
    with open(config["fixed_seed_file"], encoding="utf-8") as fh:
        seeds = json.load(fh)
    return seeds[: config["n_seeds"]]


def rotated_seeds(config, issue):
    """Powtarzalny dla audytu, ale niemożliwy do dostrojenia przed przydzieleniem issue."""
    rng = random.Random(f"{config['rotated_seed_salt']}:{issue}")
    return rng.sample(range(1, 2**31 - 1), config["n_seeds"])


def file_hash(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()[:16]


def source_hashes():
    return {name: file_hash(name) for name in HASHED_SOURCES}


def weights_file_for_spec(spec):
    """Ścieżka pliku wag, jeśli `spec` to `<prefix>:<plik>` (#102: skrót wag w rekordzie)."""
    for prefix in list(TUNED_POLICY_CLASSES) + [NTUPLE_POLICY_PREFIX]:
        if spec.startswith(prefix + ":"):
            return spec[len(prefix) + 1:]
    return None


def current_sha():
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        return "nogit"


def is_dirty():
    """Czy mierzony kod różni się od HEAD.

    Bez tego rekord `bench/<sha>.json` przypisałby pomiar do commita, którego
    wcale nie mierzył — w pętli autonomicznej to cichy fałsz w szeregu.
    """
    try:
        out = subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            text=True, stderr=subprocess.DEVNULL,
        )
        return bool(out.strip())
    except Exception:
        return True


TUNED_POLICY_CLASSES = {
    "heuristic": HeuristicPolicy,
    "tray": TrayPolicy,
    "lookahead": LookaheadPolicy,
}

# Osobny prefiks (#123): plik wag ma inny format niż FEATURE_NAMES (tablice LUT
# po łatach, patrz `ntuple.py`), więc `load_tuned_weights` się do niego nie stosuje.
NTUPLE_POLICY_PREFIX = "lookahead-ntuple"


def load_ntuple_weights(path):
    """Wczytuje `ntuple.NTupleValue` z pliku zapisanego przez `tools/train_ntuple.py`.

    Zgłasza `ArmUnavailable` zamiast wyjątku z głębi, tak jak `load_tuned_weights` (#80)."""
    if not os.path.exists(path):
        raise ArmUnavailable("brak pliku wag: " + path)
    try:
        return NTupleValue.load(path)
    except Exception as exc:
        raise ArmUnavailable("wagi ntuple " + path + " nieładowalne: " + str(exc)) from exc


def load_tuned_weights(path):
    """Wczytuje wektor wag z pliku zapisanego przez `tools/tune_weights.py` (klucz `weights`).

    Długość wektora jest przyjmowana od `len(FEATURE_NAMES)` (sześć wag
    planszowych) do `len(ALL_FEATURE_NAMES)` (plansza + combo, #118). Brakujący
    ogon jest **dopełniany zerami**, więc pliki sprzed #118 (`weights.json`,
    `weights-lookahead.json`) wczytują się bez zmiany i dają ocenę bez combo —
    czyli dokładnie tę samą politykę co dotąd.

    Zgłasza `ArmUnavailable` zamiast wyjątku z głębi: brak pliku, zły JSON albo
    długość wektora spoza tego zakresu (#80)."""
    if not os.path.exists(path):
        raise ArmUnavailable("brak pliku wag: " + path)
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        weights = tuple(data["weights"])
    except Exception as exc:
        raise ArmUnavailable("wagi " + path + " nieładowalne: " + str(exc)) from exc
    if not len(FEATURE_NAMES) <= len(weights) <= len(ALL_FEATURE_NAMES):
        raise ArmUnavailable(
            "wagi " + path + ": oczekiwano od " + str(len(FEATURE_NAMES))
            + " (FEATURE_NAMES) do " + str(len(ALL_FEATURE_NAMES))
            + " (ALL_FEATURE_NAMES) liczb, otrzymano " + str(len(weights))
        )
    return weights + (0.0,) * (len(ALL_FEATURE_NAMES) - len(weights))


def build_policy(spec, config):
    """`random`, `greedy`, `heuristic`, `tray`, `lookahead`, `heuristic:<plik>`,
    `tray:<plik>`, `lookahead:<plik>` albo ścieżka do wag torcha."""
    if spec == "random":
        return RandomPolicy(seed=config["torch_seed"])
    if spec == "greedy":
        return GreedyPolicy()
    if spec == "heuristic":
        return HeuristicPolicy()
    if spec == "tray":
        return TrayPolicy()
    if spec == "lookahead":
        return LookaheadPolicy()

    if spec.startswith(NTUPLE_POLICY_PREFIX + ":"):
        path = spec[len(NTUPLE_POLICY_PREFIX) + 1:]
        ntuple_value = load_ntuple_weights(path)
        return NTupleLookaheadPolicy(ntuple_value)

    for prefix, policy_cls in TUNED_POLICY_CLASSES.items():
        if spec.startswith(prefix + ":"):
            path = spec[len(prefix) + 1:]
            weights = load_tuned_weights(path)
            return policy_cls(weights=weights)

    if not os.path.exists(spec):
        raise ArmUnavailable("brak pliku wag: " + spec)
    try:
        import torch

        from agent import Agent

        torch.manual_seed(config["torch_seed"])
        agent = Agent()
        agent.model.load_state_dict(torch.load(spec, map_location=agent.device))
        agent.model.eval()
        return ModelPolicy(agent, os.path.basename(spec))
    except ArmUnavailable:
        raise
    except Exception as exc:
        # Najrealniejsze zagrożenie z #21: wagi istnieją, ale nie pasują do architektury.
        raise ArmUnavailable("wagi " + spec + " nieładowalne: " + str(exc)) from exc


def play_game(policy, seed, move_cap):
    game = Game(seed=seed)
    policy.reset(seed)
    while not game.done:
        if game.placements >= move_cap:
            return game.score, game.placements, True
        actions = game.available_actions()
        if not actions:
            break
        game.step(policy.act(game, actions))
    return game.score, game.placements, False


# Globalne, żeby `Pool` mógł zdalnie zbudować politykę raz na proces roboczy
# (`_worker_init`), a nie raz na partię: koszt `build_policy` (np. `torch.load`)
# powtórzony przy każdym seedzie zdominowałby czas symulacji.
_worker_policy = None
_worker_move_cap = None


def _worker_init(spec, config, move_cap):
    global _worker_policy, _worker_move_cap
    _worker_policy = build_policy(spec, config)
    _worker_move_cap = move_cap


def _worker_play(seed):
    return play_game(_worker_policy, seed, _worker_move_cap)


def aggregate_set(scores, survivals, capped_flags):
    """Statystyki zbiorcze partii z surowych list per-seed.

    Dzielone z `tools/merge_bench.py` (#167): kawałek liczy je na swojej
    podpuli seedów, złożenie — na scalonych listach z wszystkich kawałków.
    """
    capped = sum(1 for c in capped_flags if c)
    return {
        "mean": round(statistics.mean(scores), 2),
        "median": round(statistics.median(scores), 2),
        "p10": round(percentile(scores, 10), 2),
        "survival_mean": round(statistics.mean(survivals), 2),
        "capped_pct": round(100.0 * capped / len(scores), 2),
    }


def run_set(policy, seeds, move_cap, jobs=1, spec=None, config=None):
    if jobs > 1:
        # Partie zależą tylko od swojego seeda (#148), więc `Pool.map` — który
        # zwraca wyniki w kolejności zadań, niezależnie od kolejności ukończenia
        # — daje ten sam plik wyjściowy co pętla sekwencyjna.
        with multiprocessing.Pool(
            jobs, initializer=_worker_init, initargs=(spec, config, move_cap)
        ) as pool:
            results = pool.map(_worker_play, seeds)
    else:
        results = [play_game(policy, seed, move_cap) for seed in seeds]

    scores, survivals, capped_flags = [], [], []
    for score, placements, was_capped in results:
        scores.append(score)
        survivals.append(placements)
        capped_flags.append(bool(was_capped))
    summary = aggregate_set(scores, survivals, capped_flags)
    summary["scores"] = scores
    summary["survivals"] = survivals
    summary["capped_flags"] = capped_flags
    return summary


def percentile(values, pct):
    ordered = sorted(values)
    k = (len(ordered) - 1) * pct / 100.0
    lo = int(k)
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo)


def paired_delta(candidate_scores, baseline_scores, threshold_pct):
    """Różnica sparowana na wspólnych seedach + etykieta progu (nieblokująca).

    Dopisuje błąd standardowy różnicy (#102): przy 300 seedach `sd_diff` samo
    w sobie nie mówi, czy `mean_diff` jest odróżnialne od szumu — próg
    promocji potrafi leżeć w okolicach jednego błędu standardowego.
    """
    diffs = [c - b for c, b in zip(candidate_scores, baseline_scores)]
    n = len(diffs)
    base_mean = statistics.mean(baseline_scores)
    mean_diff = statistics.mean(diffs)
    sd_diff = statistics.pstdev(diffs) if n > 1 else 0.0
    se_diff = sd_diff / math.sqrt(n) if n > 0 else 0.0
    pct = 100.0 * mean_diff / base_mean if base_mean else 0.0
    if pct >= threshold_pct:
        label = "poprawa"
    elif pct <= -threshold_pct:
        label = "regresja"
    else:
        label = "bez zmian"
    return {
        "mean_diff": round(mean_diff, 2),
        "pct": round(pct, 2),
        "sd_diff": round(sd_diff, 2),
        "se_diff": round(se_diff, 2),
        "se_pct": round(100.0 * se_diff / base_mean, 2) if base_mean else 0.0,
        "mean_diff_over_se": round(mean_diff / se_diff, 2) if se_diff else 0.0,
        "label": label,
    }


def measure_arm(policy, seeds_fixed, seeds_rotated, move_cap, jobs=1, spec=None, config=None):
    fixed = run_set(policy, seeds_fixed, move_cap, jobs=jobs, spec=spec, config=config)
    rotated = run_set(policy, seeds_rotated, move_cap, jobs=jobs, spec=spec, config=config)
    base = fixed["mean"]
    gap = round(100.0 * (base - rotated["mean"]) / base, 2) if base else 0.0
    return {
        "policy": policy.name,
        "fixed": fixed,
        "rotated": rotated,
        # Rozjazd stały/rotowany = miara przetrenowania na benchmark (#8).
        "overfit_gap_pct": gap,
    }


RAW_SET_KEYS = ("scores", "survivals", "capped_flags")


def strip_scores(record):
    """Surowe serie zostają poza rekordem — rekord ma być czytelny, nie pełny."""
    for arm in record["arms"].values():
        for key in ("fixed", "rotated"):
            for raw_key in RAW_SET_KEYS:
                arm[key].pop(raw_key, None)
    return record


def parse_shard(spec):
    """`"K/N"` -> `(k, n)`, 1 <= k <= n. Zgłasza `ValueError` na złym formacie."""
    try:
        k_str, n_str = spec.split("/")
        k, n = int(k_str), int(n_str)
    except ValueError as exc:
        raise ValueError("--shard oczekuje K/N, np. 1/4, otrzymano: " + spec) from exc
    if n < 1 or not (1 <= k <= n):
        raise ValueError("--shard K/N wymaga 1 <= K <= N, otrzymano: " + spec)
    return k, n


def shard_seeds(seeds, k, n):
    """Podpula seedów kawałka `K/N`: indeks `i` (0-based) taki, że `i % N == K - 1`.

    Ta sama funkcja filtruje i zestaw stały, i rotowany — kawałek nr K bierze
    tę samą frakcję z obu (#167).
    """
    return [seed for i, seed in enumerate(seeds) if i % n == k - 1]


def render_markdown(record):
    lines = ["## Benchmark — `" + record["sha"][:12] + "`", ""]
    if record.get("dirty"):
        lines += ["> Mierzony kod **różni się od HEAD** — pomiar nie opisuje tego commita.", ""]
    if record["status"] == STATUS_BLOCKED:
        lines += ["**status: blocked** — " + str(record["blocked_reason"]), ""]

    cfg = record["config"]
    lines += [
        "N = {0} seedów na zestaw · sufit {1} ruchów · eps = {2} · próg ±{3}% (nieblokujący)".format(
            cfg["n_seeds"], cfg["move_cap"], cfg["epsilon"], cfg["threshold_pct"]
        ),
        "",
        "| ramię | polityka | średnia | mediana | p10 | przeżycie | % uciętych | rozjazd stały/rotowany |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for name, arm in record["arms"].items():
        f = arm["fixed"]
        lines.append(
            "| {0} | `{1}` | {2} | {3} | {4} | {5} | {6}% | {7}% |".format(
                name, arm["policy"], f["mean"], f["median"], f["p10"],
                f["survival_mean"], f["capped_pct"], arm["overfit_gap_pct"],
            )
        )

    if record["deltas"]:
        lines += [
            "",
            "| porównanie (sparowane, zestaw stały) | Δ średniej | Δ % | etykieta |",
            "|---|---|---|---|",
        ]
        for name, d in record["deltas"].items():
            lines.append(
                "| {0} | {1} | {2}% | **{3}** |".format(name, d["mean_diff"], d["pct"], d["label"])
            )

    hashes = " · ".join("`" + k + "`=" + v for k, v in record["source_hashes"].items())
    lines += ["", "Hash symulatora: " + hashes, "Czas pomiaru: {0} s".format(record["duration_s"])]
    return "\n".join(lines)


def main(argv=None):
    # Raport jest po polsku i zawiera Δ — konsola Windows domyślnie jest cp1250
    # i wywaliłaby cały przebieg na samym drukowaniu wyniku.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    parser = argparse.ArgumentParser(description="Benchmark bota Block Blast")
    parser.add_argument(
        "--candidate", required=True,
        help="random | greedy | heuristic | tray | lookahead | heuristic:<plik> | "
             "tray:<plik> | lookahead:<plik> | lookahead-ntuple:<plik> | "
             "ścieżka do wag torcha",
    )
    parser.add_argument("--previous", help="ramię odniesienia: poprzednik")
    parser.add_argument("--record", help="ramię odniesienia: rekordzista")
    parser.add_argument("--issue", type=int, required=True, help="numer issue zadania-benchmarku")
    parser.add_argument("--config", default=CONFIG_PATH)
    parser.add_argument("--n-seeds", type=int, help="nadpisuje n_seeds z konfiguracji")
    parser.add_argument("--out", help="ścieżka rekordu; domyślnie bench/<sha>.json")
    parser.add_argument(
        "--jobs", type=int, default=1,
        help="partie (seed x ramię) liczone w N procesach; wynik bitowo ten sam co --jobs 1",
    )
    parser.add_argument(
        "--shard",
        help="K/N: gra tylko seedy o indeksie i%%N == K-1 (stałe i rotowane); "
             "złożenie tools/merge_bench.py wszystkich N kawałków = przebieg bez --shard",
    )
    args = parser.parse_args(argv)

    if args.shard:
        try:
            shard_k, shard_n = parse_shard(args.shard)
        except ValueError as exc:
            parser.error(str(exc))

    config = load_config(args.config)
    if args.n_seeds:
        config["n_seeds"] = args.n_seeds

    sha = current_sha()
    dirty = is_dirty()
    record = {
        "sha": sha,
        "dirty": dirty,
        "issue": args.issue,
        "status": STATUS_OK,
        "blocked_reason": None,
        # Bez skopiowanych parametrów porównanie dwóch przebiegów o różnych
        # progach byłoby niejawnym kłamstwem (#8).
        "config": config,
        "source_hashes": source_hashes(),
        "arms": {},
        "deltas": {},
        "duration_s": 0.0,
    }

    seeds_f = fixed_seeds(config)
    seeds_r = rotated_seeds(config, args.issue)
    if args.shard:
        seeds_f = shard_seeds(seeds_f, shard_k, shard_n)
        seeds_r = shard_seeds(seeds_r, shard_k, shard_n)
        record["shard"] = args.shard
    requested = [
        ("candidate", args.candidate),
        ("previous", args.previous),
        ("record", args.record),
    ]

    started = time.time()
    for name, spec in requested:
        if spec is None:
            continue
        try:
            policy = build_policy(spec, config)
        except ArmUnavailable as exc:
            # Rekordzista albo poprzednik zaginął: raport wychodzi, decyzję
            # podejmuje orchestrator (#21).
            record["status"] = STATUS_BLOCKED
            record["blocked_reason"] = "ramię `" + name + "`: " + str(exc)
            continue
        arm = measure_arm(
            policy, seeds_f, seeds_r, config["move_cap"],
            jobs=args.jobs, spec=spec, config=config,
        )
        weights_path = weights_file_for_spec(spec)
        if weights_path:
            arm["weights_hash"] = file_hash(weights_path)
        record["arms"][name] = arm

    if "candidate" in record["arms"]:
        cand = record["arms"]["candidate"]["fixed"]["scores"]
        for name in ("previous", "record"):
            if name in record["arms"]:
                record["deltas"]["kandydat vs " + name] = paired_delta(
                    cand, record["arms"][name]["fixed"]["scores"], config["threshold_pct"]
                )

    record["duration_s"] = round(time.time() - started, 1)
    if not args.shard:
        strip_scores(record)

    out_path = args.out or ("bench/" + sha + ("-dirty" if dirty else "") + ".json")
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=2, ensure_ascii=False)

    print(render_markdown(record))
    print("\nRekord: " + out_path, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
