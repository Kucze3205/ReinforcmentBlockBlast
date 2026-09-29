#!/usr/bin/env python3
"""
Z-6 (#211): dopasowanie modeli generatora ŚWIADOMEGO planszy (M0/M1/M2) do
693 par `docs/data/z6-pary.json`, log-wiarygodność na odłożonej próbie
testowej. **Pomiar, nie wdrożenie** — `generator.py`, `pieces.py` nietknięte
(patrz `## Cel` issue #211); decyzję o zmianie kodu podejmuje cykl 24.

    python3 tools/z6_model.py

Modele (wszystkie to szczególne przypadki jednego wzoru na log-wiarygodność
pary plansza+tacka, patrz `loglik_row` niżej):

  M0 - obecny `generator.py` (`PIECE_TYPE_WEIGHTS`), punkt odniesienia, BEZ
       dopasowania (p=0 -> wzór redukuje się do log q(tacka), niezależnie od
       planszy).
  M1 - M0 z wagami typów przeliczonymi MLE na części uczącej (zamkniętym
       wzorem: częstość + wygładzanie Laplace'a), orientacja nadal 1/n w
       obrębie typu (bez zmian od #186) -- p=0 jak w M0.
  M2 - losowanie odrzucające: tacka z wag typów; jeśli NIEukładalna na
       planszy (`tray_playable` z `tools/z6_testy.py` -- ta sama funkcja, co
       testy (c)/(d), issue #211 zabrania pisać nową), z prawdopodobieństwem
       `p` losuj od nowa (do `k` prób, potem przyjmij co wypadło). Wagi typów
       i `p` dopasowane RAZEM numerycznie (współrzędnościowy wschodzący
       złoty podział, `k` wybrany siatką po wiarygodności uczącej) -- bo
       odrzucanie zmienia efektywną częstość obserwowanych typów.

Wyprowadzenie wzoru na log-wiarygodność (patrz `docs/z6-model-generatora.md`
"Model" po szczegóły): niech pi = P(świeży niezależny rzut tacki jest
grywalny na TEJ planszy) pod wagami `w`, S(p,k,pi) = sum_{m=0}^{k-1}
((1-pi)*p)^m (oczekiwana liczba "efektywnych" prób do zatrzymania). Z
niezależności rzutów (iid, brak pamięci) rozkład WARUNKOWY wylosowanej tacki
w obrębie "grywalna"/"niegrywalna" jest taki sam jak dla pojedynczego rzutu
-- stąd czynnik pi się skraca:

    log L(tacka T | plansza) = log q(T) + log S(p,k,pi)                 [T grywalna]
    log L(tacka T | plansza) = log q(T) - log(1-pi) + log(1 - pi*S(p,k,pi))  [T niegrywalna]

gdzie q(T) = iloczyn po 3 slotach: w[typ]/n_poz(typ) (ten sam q co w M0/M1,
BEZ planszy). Przy p=0: S=1 zawsze, drugi wzór upraszcza się do log q(T) --
M0/M1 to M2 z p=0 (sprawdzone w `tests/test_z6_model.py`).

pi liczone importance samplingiem: dla każdej planszy losujemy raz (seed
stały, `IMPORTANCE_SEED`) `N_IMPORTANCE_SAMPLES` trójek póz JEDNOSTAJNIE z
41 póz (niezależnie od `w`) i zapisujemy `tray_playable` każdej. Dla
DOWOLNEGO `w` (w tym w trakcie optymalizacji) pi(w) liczy się jako ważona
średnia tych samych próbek (waga = iloraz gęstości w/jednostajnej) -- bez
ponownego wywoływania `tray_playable` (kosztownego, DFS) przy każdej
iteracji dopasowania.

#217 (wdrożenie): #211 zostawiło dopasowane `p=1,0`/`k=5` na górnej granicy
siatki `{1,2,3,5}` -- siatka `K_CANDIDATES` tu poszerzona o {10,20,50,
K_DO_SKUTKU=1000} ("do skutku" to ten sam wzór z `k` tak dużym, że w
praktyce nigdy nie jest osiągane na obserwowanych planszach). Dodano też
`fit_m2_simple`: M2 z wagami ZAMROŻONYMI na M0 (tylko `p`,`k` dopasowane) --
kryterium wyboru między nim a M2 z wagami dopasowanymi razem ("M2-fit") to
różnica log-wiarygodności testowej > 1 SE (patrz `main`), zgodnie z ideą
#211 "wagi typów to szum, różnicę robi samo odrzucanie".
"""
import hashlib
import json
import os
import sys

import numpy as np

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

from board import Board  # noqa: E402
from generator import PIECE_TYPE_WEIGHTS  # noqa: E402
from pieces import CANONICAL_TYPES, PIECE_POOL, PIECE_TYPES  # noqa: E402

from z6_testy import tray_playable  # noqa: E402  (funkcja "da się ułożyć" -- nie duplikować)

PAIRS_PATH = os.path.join(REPO_ROOT, "docs", "data", "z6-pary.json")

N_TYPES = len(CANONICAL_TYPES)
N_POSES = len(PIECE_POOL)
TYPE_NAMES = [t[0] for t in CANONICAL_TYPES]
N_POSES_BY_TYPE = np.array([len(poses) for poses in PIECE_TYPES], dtype=float)
NAME_TO_TYPE = {p.name: p.type_index for p in PIECE_POOL}
NAME_TO_POSE = {p.name: p.index for p in PIECE_POOL}
POSE_TO_TYPE = np.array([p.type_index for p in PIECE_POOL], dtype=int)

# Podział uczące/testowe: deterministyczny hasz `id` pary (sha1, nie zależy od
# kolejności wczytania pliku), ~20% testowe. Zapisany tu (nie w dokumencie) --
# jedyne miejsce prawdy.
TEST_HASH_MOD = 5
TEST_HASH_RESIDUE = 0

N_IMPORTANCE_SAMPLES = 400
IMPORTANCE_SEED = 211

SMOOTH_ALPHA = 0.5  # Laplace, żeby typy o 0 obserwacjach w train nie dawały log(0) w test.
# #217: poszerzenie siatki o {10,20,50} (#211 zostawił p=1,0/k=5 na górnej granicy
# starej siatki {1,2,3,5} -- dane "chciały" więcej odrzucania) plus wariant „do
# skutku" (losuj aż grywalna, bez ograniczenia poza awaryjnym limitem prób) -- w
# tym samym wzorze na S(p,k,pi) to po prostu k tak duże, że w praktyce nigdy nie
# jest osiągane na obserwowanych planszach (K_DO_SKUTKU), więc nie trzeba osobnego
# wzoru: "do skutku" = punkt na tej samej siatce, nie inny model.
K_DO_SKUTKU = 1000
K_CANDIDATES = (1, 2, 3, 5, 10, 20, 50, K_DO_SKUTKU)
P_GRID = np.linspace(0.0, 1.0, 101)
N_COORD_ROUNDS = 4
N_COORD_SWEEPS = 2
GOLDEN_ITERS = 40

FILL_HARD_THRESHOLD = 0.40

BENCH_WEIGHTS = "ntuple/survival-ad-70k.json"
BENCH_POLICY_SPEC = "lookahead-ntuple:" + BENCH_WEIGHTS
BENCH_N_EPISODES = 20
BENCH_MOVE_CAP = 240  # sufit postawień/partię -- ~80 odświeżeń tacki, budżet czasu narzędzia
BENCH_SEED_BASE = 211
BENCH_MC_REPS = 150


# ---------------------------------------------------------------------------
# wczytanie par, podział, cechy
# ---------------------------------------------------------------------------


def load_pairs(path=PAIRS_PATH):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data["pairs"]


def is_test_id(pair_id):
    digest = hashlib.sha1(pair_id.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % TEST_HASH_MOD == TEST_HASH_RESIDUE


def build_rows(pairs):
    rows = []
    for pair in pairs:
        grid = pair["board"]
        names = [t["name"] for t in pair["tray"]]
        type_idx = np.array([NAME_TO_TYPE[n] for n in names], dtype=int)
        pose_idx = np.array([NAME_TO_POSE[n] for n in names], dtype=int)
        shapes = [PIECE_POOL[i].shape for i in pose_idx]
        n_filled = sum(sum(r) for r in grid)
        fill = n_filled / (Board.WIDTH * Board.HEIGHT)
        rows.append({
            "id": pair["id"],
            "board": grid,
            "fill": fill,
            "type_idx": type_idx,
            "pose_idx": pose_idx,
            "shapes": shapes,
        })
    return rows


def annotate_playability(rows):
    """`tray_playable` na TACCE OBSERWOWANEJ (nie próbkach) -- 693 wywołań, tanie."""
    for r in rows:
        outcome = tray_playable(r["board"], r["shapes"])
        r["playable"] = bool(outcome) if outcome is not None else False
        r["playable_unknown"] = outcome is None


# ---------------------------------------------------------------------------
# importance sampling: pi(w) dla dowolnych wag bez ponownego DFS
# ---------------------------------------------------------------------------


def precompute_importance_samples(rows, n_samples=N_IMPORTANCE_SAMPLES, seed=IMPORTANCE_SEED):
    """Dla każdej planszy: `n_samples` trójek póz jednostajnych z 41 (niezależne
    od `w`), i czy taka tacka jest grywalna (`tray_playable`, ten sam DFS co
    testy (c)/(d)). Zwraca tablice (n_wierszy, n_samples, ...) do policzenia
    pi(w) dla DOWOLNEGO `w` bez ponownego DFS (ważenie gęstością)."""
    rng = np.random.default_rng(seed)
    n = len(rows)
    type_idx_samples = np.empty((n, n_samples, 3), dtype=np.int8)
    playable_samples = np.empty((n, n_samples), dtype=bool)
    log_const_samples = np.empty((n, n_samples), dtype=np.float64)

    for i, row in enumerate(rows):
        pose_samples = rng.integers(0, N_POSES, size=(n_samples, 3))
        type_idx_samples[i] = POSE_TO_TYPE[pose_samples]
        log_n_poses = np.log(N_POSES_BY_TYPE[type_idx_samples[i]]).sum(axis=1)
        log_const_samples[i] = 3.0 * np.log(N_POSES) - log_n_poses
        for j in range(n_samples):
            shapes = [PIECE_POOL[pose_samples[j, s]].shape for s in range(3)]
            outcome = tray_playable(row["board"], shapes)
            playable_samples[i, j] = bool(outcome) if outcome is not None else False

    return {
        "type_idx": type_idx_samples,
        "playable": playable_samples,
        "log_const": log_const_samples,
    }


def pi_batch(w, samples):
    """pi(w) na cały zestaw wierszy naraz (wektorowo)."""
    logw = np.log(w)
    log_probs = logw[samples["type_idx"]].sum(axis=2)  # (n, M)
    iw = np.exp(log_probs + samples["log_const"])
    return (samples["playable"] * iw).mean(axis=1)


# ---------------------------------------------------------------------------
# log-wiarygodność: jeden wzór, M0/M1 to M2 z p=0
# ---------------------------------------------------------------------------


def row_log_q(w, rows):
    type_idx = np.stack([r["type_idx"] for r in rows])  # (n,3)
    logw = np.log(w)
    log_n_poses = np.log(N_POSES_BY_TYPE[type_idx]).sum(axis=1)
    return logw[type_idx].sum(axis=1) - log_n_poses


def geometric_sum(r, k):
    """S = sum_{m=0}^{k-1} r^m, wektorowo po r; wolniejszy ale odporny na r~1."""
    total = np.ones_like(r)
    term = np.ones_like(r)
    for _ in range(k - 1):
        term = term * r
        total = total + term
    return total


EPS = 1e-300


def loglik_rows(w, p, k, rows, samples):
    """Suma log-wiarygodności `rows` pod (w,p,k). `samples` -- importance
    samples DOKŁADNIE dla tych wierszy, w tej samej kolejności."""
    pi = pi_batch(w, samples)
    log_q = row_log_q(w, rows)
    playable = np.array([r["playable"] for r in rows], dtype=bool)

    r = (1.0 - pi) * p
    S = geometric_sum(r, k)

    ll = np.empty(len(rows), dtype=np.float64)
    ll[playable] = log_q[playable] + np.log(np.maximum(S[playable], EPS))

    unpl = ~playable
    tail = np.maximum(1.0 - pi[unpl] * S[unpl], EPS)
    ll[unpl] = log_q[unpl] - np.log(np.maximum(1.0 - pi[unpl], EPS)) + np.log(tail)
    return ll


def total_loglik(w, p, k, rows, samples):
    return float(loglik_rows(w, p, k, rows, samples).sum())


# ---------------------------------------------------------------------------
# dopasowanie: M0 (bez dopasowania), M1 (MLE zamknięte), M2 (numerycznie)
# ---------------------------------------------------------------------------


def fit_m0():
    w = np.array(PIECE_TYPE_WEIGHTS, dtype=float)
    return w / w.sum()


def fit_m1(train_rows):
    counts = np.zeros(N_TYPES, dtype=float)
    for r in train_rows:
        for t in r["type_idx"]:
            counts[t] += 1
    counts += SMOOTH_ALPHA
    return counts / counts.sum()


def golden_section_max(f, a, b, iters=GOLDEN_ITERS):
    gr = (5 ** 0.5 - 1) / 2  # 1/phi
    c = b - gr * (b - a)
    d = a + gr * (b - a)
    fc, fd = f(c), f(d)
    for _ in range(iters):
        if fc < fd:
            a = c
            c = d
            fc = fd
            d = a + gr * (b - a)
            fd = f(d)
        else:
            b = d
            d = c
            fd = fc
            c = b - gr * (b - a)
            fc = f(c)
    x = (a + b) / 2
    return x, f(x)


def fit_m2_given_k(train_rows, train_samples, k, w_init, rounds=N_COORD_ROUNDS,
                    sweeps=N_COORD_SWEEPS):
    w = w_init.copy()

    def ll_p(p):
        return total_loglik(w, p, k, train_rows, train_samples)

    p_scores = np.array([ll_p(p) for p in P_GRID])
    p = float(P_GRID[np.argmax(p_scores)])

    for _ in range(rounds):
        p, _ = golden_section_max(ll_p, max(0.0, p - 0.15), min(1.0, p + 0.15))
        for _ in range(sweeps):
            for j in range(N_TYPES):
                lo = max(1e-6, w[j] * 0.3)
                hi = max(lo * 1.01, w[j] * 3.0)

                def f(x, j=j):
                    w2 = w.copy()
                    w2[j] = x
                    w2 = w2 / w2.sum()
                    return total_loglik(w2, p, k, train_rows, train_samples)

                x, _ = golden_section_max(f, lo, hi)
                w[j] = x
                w = w / w.sum()
        p_scores = np.array([ll_p(p2) for p2 in P_GRID])
        p_refine, _ = golden_section_max(ll_p, max(0.0, p - 0.05), min(1.0, p + 0.05))
        if ll_p(p_refine) >= ll_p(p):
            p = p_refine

    return w, p


def fit_m2(train_rows, train_samples, w1):
    best = None
    for k in K_CANDIDATES:
        w, p = fit_m2_given_k(train_rows, train_samples, k, w1.copy())
        train_ll = total_loglik(w, p, k, train_rows, train_samples)
        if best is None or train_ll > best["train_ll"]:
            best = {"k": k, "w": w, "p": p, "train_ll": train_ll}
    return best


def fit_m2_simple_given_k(train_rows, train_samples, k, w_fixed):
    """M2 z WAGAMI ZAMROŻONYMI na `w_fixed` (#217 kryterium 2) -- dopasowuje
    wyłącznie `p` (złoty podział), różnica samego odrzucania bez przeliczania
    wag typów."""
    def ll_p(p):
        return total_loglik(w_fixed, p, k, train_rows, train_samples)

    p_scores = np.array([ll_p(p) for p in P_GRID])
    p = float(P_GRID[np.argmax(p_scores)])
    p, _ = golden_section_max(ll_p, max(0.0, p - 0.05), min(1.0, p + 0.05))
    return w_fixed, p


def fit_m2_simple(train_rows, train_samples, w_fixed):
    best = None
    for k in K_CANDIDATES:
        w, p = fit_m2_simple_given_k(train_rows, train_samples, k, w_fixed)
        train_ll = total_loglik(w, p, k, train_rows, train_samples)
        if best is None or train_ll > best["train_ll"]:
            best = {"k": k, "w": w, "p": p, "train_ll": train_ll}
    return best


# ---------------------------------------------------------------------------
# ewaluacja: log-wiarygodność testowa, różnica vs M0 z SE, grywalność na trudnych planszach
# ---------------------------------------------------------------------------


def paired_diff_se(ll_a, ll_b):
    """SE różnicy sum log-wiarygodności (test-parowany, per-para): d_i = a_i-b_i,
    SE(sum d) = sd(d_i) * sqrt(n)."""
    d = ll_a - ll_b
    n = len(d)
    se = float(np.std(d, ddof=1) * np.sqrt(n)) if n > 1 else float("nan")
    return float(d.sum()), se


def evaluate_model(name, w, p, k, n_params, train_rows, train_samples, test_rows,
                    test_samples, m0_test_ll_rows, hard_rows, hard_samples):
    train_ll = total_loglik(w, p, k, train_rows, train_samples)
    test_ll_rows = loglik_rows(w, p, k, test_rows, test_samples)
    test_ll = float(test_ll_rows.sum())
    diff, se = paired_diff_se(test_ll_rows, m0_test_ll_rows)

    pi_hard = pi_batch(w, hard_samples)
    r = (1.0 - pi_hard) * p
    S = geometric_sum(r, k)
    predicted_playable_hard = float(np.mean(pi_hard * S))

    return {
        "name": name,
        "n_params": n_params,
        "k": k,
        "p": p,
        "weights": w.tolist(),
        "train_loglik": train_ll,
        "test_loglik": test_ll,
        "test_loglik_diff_vs_m0": diff,
        "test_loglik_diff_se": se,
        "predicted_playable_hard": predicted_playable_hard,
    }


# ---------------------------------------------------------------------------
# szacunek skutku dla benchmarku (kryterium 3): partie lookahead-ntuple
# ---------------------------------------------------------------------------


def sample_boards_from_bench_games(spec=BENCH_POLICY_SPEC, n_episodes=BENCH_N_EPISODES,
                                    move_cap=BENCH_MOVE_CAP, seed_base=BENCH_SEED_BASE):
    """Plansze w chwili odświeżenia tacki (`placements` wielokrotność 3, jak w
    `docs/data/z6-pary.json`) z `n_episodes` partii `lookahead-ntuple:<wagi>`
    (dowolne wagi z `ntuple/`, tu `BENCH_WEIGHTS`) -- ten sam silnik co
    `tools/collect_states.py`, tylko bez zapisu pliku."""
    from benchmark import build_policy, load_config
    from game import Game

    config = load_config()
    policy = build_policy(spec, config)
    boards = []
    for ep in range(n_episodes):
        seed = ("z6_model:%r:%r" % (seed_base, ep))
        game = Game(seed=seed)
        policy.reset(seed)
        while not game.done and game.placements < move_cap:
            actions = game.available_actions()
            if not actions:
                break
            game.step(policy.act(game, actions))
            if game.placements % 3 == 0:
                boards.append([row[:] for row in game.board.grid])
    return boards


def _sample_tray_shapes(rng, w):
    type_idx = rng.choice(N_TYPES, size=3, p=w)
    shapes = []
    for t in type_idx:
        pose_choices = PIECE_TYPES[t]
        pose = pose_choices[rng.integers(0, len(pose_choices))]
        shapes.append(PIECE_POOL[pose].shape)
    return shapes


def estimate_bench_impact(boards, w0, w_best, p_best, k_best, reps=BENCH_MC_REPS,
                           seed=IMPORTANCE_SEED):
    """Na planszach z prawdziwych partii: jak często M0 daje NIEukładalną tacke
    kontra najlepszy model (z jego procesem odrzucania, jeśli p_best>0)."""
    rng = np.random.default_rng(seed)
    n_unplayable_m0 = 0
    n_unplayable_best = 0
    n_draws = 0
    for board in boards:
        for _ in range(reps):
            n_draws += 1
            shapes0 = _sample_tray_shapes(rng, w0)
            if not tray_playable(board, shapes0):
                n_unplayable_m0 += 1

            attempt = 0
            while True:
                attempt += 1
                shapes_b = _sample_tray_shapes(rng, w_best)
                ok = tray_playable(board, shapes_b)
                if ok:
                    break
                if attempt >= k_best or rng.random() >= p_best:
                    break
            if not ok:
                n_unplayable_best += 1
    return {
        "n_boards": len(boards),
        "reps_per_board": reps,
        "n_draws": n_draws,
        "unplayable_rate_m0": n_unplayable_m0 / n_draws if n_draws else None,
        "unplayable_rate_best": n_unplayable_best / n_draws if n_draws else None,
    }


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main():
    pairs = load_pairs()
    rows = build_rows(pairs)
    annotate_playability(rows)

    train_rows = [r for r in rows if not is_test_id(r["id"])]
    test_rows = [r for r in rows if is_test_id(r["id"])]

    print(f"pary: {len(rows)} (uczące: {len(train_rows)}, testowe: {len(test_rows)})")

    all_samples = precompute_importance_samples(rows)
    idx_by_id = {r["id"]: i for i, r in enumerate(rows)}
    train_idx = np.array([idx_by_id[r["id"]] for r in train_rows])
    test_idx = np.array([idx_by_id[r["id"]] for r in test_rows])

    def subset_samples(idx):
        return {k: v[idx] for k, v in all_samples.items()}

    train_samples = subset_samples(train_idx)
    test_samples = subset_samples(test_idx)

    hard_rows = [r for r in rows if r["fill"] >= FILL_HARD_THRESHOLD]
    hard_idx = np.array([idx_by_id[r["id"]] for r in hard_rows])
    hard_samples = subset_samples(hard_idx)
    observed_playable_hard = float(np.mean([r["playable"] for r in hard_rows])) if hard_rows else None
    print(f"plansze trudne (zapełnienie >= {FILL_HARD_THRESHOLD}): {len(hard_rows)}/{len(rows)}, "
          f"obserwowana grywalność = {observed_playable_hard}")

    w0 = fit_m0()
    w1 = fit_m1(train_rows)
    m2_simple = fit_m2_simple(train_rows, train_samples, w0)
    m2_fit = fit_m2(train_rows, train_samples, w1)

    m0_test_ll_rows = loglik_rows(w0, 0.0, 1, test_rows, test_samples)

    results = []
    results.append(evaluate_model("M0", w0, 0.0, 1, 0, train_rows, train_samples,
                                   test_rows, test_samples, m0_test_ll_rows,
                                   hard_rows, hard_samples))
    results.append(evaluate_model("M1", w1, 0.0, 1, N_TYPES - 1, train_rows, train_samples,
                                   test_rows, test_samples, m0_test_ll_rows,
                                   hard_rows, hard_samples))
    # #217 kryterium 2: M2 z wagami M0 zamrożonymi (tylko p,k -- "prostszy") kontra
    # M2 z wagami dopasowanymi RAZEM z p,k ("M2-fit", to, co #211 nazywało "M2").
    results.append(evaluate_model("M2-simple", m2_simple["w"], m2_simple["p"], m2_simple["k"], 1,
                                   train_rows, train_samples, test_rows, test_samples,
                                   m0_test_ll_rows, hard_rows, hard_samples))
    results.append(evaluate_model("M2-fit", m2_fit["w"], m2_fit["p"], m2_fit["k"], N_TYPES,
                                   train_rows, train_samples, test_rows, test_samples,
                                   m0_test_ll_rows, hard_rows, hard_samples))

    print()
    for res in results:
        print(f"{res['name']}: n_params={res['n_params']} k={res['k']} p={res['p']:.4f} "
              f"train_ll={res['train_loglik']:.2f} test_ll={res['test_loglik']:.2f} "
              f"diff_vs_M0={res['test_loglik_diff_vs_m0']:.2f} (se={res['test_loglik_diff_se']:.2f}) "
              f"pred_playable_hard={res['predicted_playable_hard']:.4f}")

    # Decyzja kryterium 2: prostszy (wagi M0) wygrywa, chyba że dopasowane wagi
    # biją go na teście o WIĘCEJ NIŻ 1 SE różnicy parowanej (nie SE każdego z
    # osobna -- to by zawyżało próg, patrz `paired_diff_se`).
    simple_res = next(r for r in results if r["name"] == "M2-simple")
    fit_res = next(r for r in results if r["name"] == "M2-fit")
    simple_ll_rows = loglik_rows(np.array(simple_res["weights"]), simple_res["p"], simple_res["k"],
                                  test_rows, test_samples)
    fit_ll_rows = loglik_rows(np.array(fit_res["weights"]), fit_res["p"], fit_res["k"],
                               test_rows, test_samples)
    fit_vs_simple_diff, fit_vs_simple_se = paired_diff_se(fit_ll_rows, simple_ll_rows)
    fit_wins = fit_vs_simple_diff > fit_vs_simple_se
    chosen_name = "M2-fit" if fit_wins else "M2-simple"
    chosen = fit_res if fit_wins else simple_res
    print(f"\nM2-fit vs M2-simple na teście: diff={fit_vs_simple_diff:.2f} (se={fit_vs_simple_se:.2f}) "
          f"-> {'dopasowane wagi wygrywają o >1 SE' if fit_wins else 'wagi M0 wystarczą (prostszy)'}")
    print(f"wybrany model kryterium 2: {chosen_name} (k={chosen['k']}, p={chosen['p']:.4f})")

    best = max(results, key=lambda r: r["test_loglik"])
    print(f"\nnajlepszy na teście (log-wiarygodność, informacyjnie): {best['name']}")

    print(f"\n=== kryterium 3: skutek dla benchmarku ({BENCH_N_EPISODES} partii "
          f"{BENCH_POLICY_SPEC}) ===")
    boards = sample_boards_from_bench_games()
    w_chosen = np.array(chosen["weights"])
    impact = estimate_bench_impact(boards, w0, w_chosen, chosen["p"], chosen["k"])
    print(impact)

    return {
        "n_pairs": len(rows),
        "n_train": len(train_rows),
        "n_test": len(test_rows),
        "observed_playable_hard": observed_playable_hard,
        "results": results,
        "best_test_loglik": best["name"],
        "fit_vs_simple_diff": fit_vs_simple_diff,
        "fit_vs_simple_se": fit_vs_simple_se,
        "chosen": chosen_name,
        "bench_impact": impact,
    }


if __name__ == "__main__":
    main()
