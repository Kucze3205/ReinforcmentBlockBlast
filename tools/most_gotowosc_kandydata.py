#!/usr/bin/env python3
"""
#260: gotowość mostu na politykę-kandydata (`--policy`), pomiar offline bez emulatora.
Nie zmienia mostu, polityk, symulatora ani generatora.

Odtwarza ścieżkę decyzji `bridge.main`: `build_policy(spec, {"torch_seed": 0})`, `policy.reset(seed)`,
`Piece(macierz, "slot<i>", -1)` z zalogowanej tacki, `legal_moves`, `make_game_stub(board, pieces)`,
`policy.act(game, moves)` — na stanach (plansza + tacka) z `bridge/runs/*/chunk*_moves.jsonl`.
Stany brane są z wierszy z polem `move` (te, w których most faktycznie decydował); wiersze końca
partii (`koniec_partii`, `end`) są pomijane — ich `tray` to śmieci z nakładki (#249). Identyczne
stany (plansza + tacka; ponowienia po `ok=false`) liczone raz.

Stan combo: dziennik mostu nie niesie `combo`, a `make_game_stub` podaje `combo=0`,
`combo_counter=COMBO_COUNTER_BASE`. Rekonstrukcja: reguły `scoring.py`/`Game.apply_placement` na sekwencji
zalogowanych ruchów (kolejność plików w przebiegu naturalna, reset na początku przebiegu i po wierszu
końca partii). Stan jest `wiarygodny`, dopóki łańcuch nie zerwał się (ruch `ok=false` albo plansza wiersza
różna od `observed` poprzedniego). Dla stanów, gdzie rekonstrukcja różni się od zaślepki, liczona jest druga
decyzja z rekonstrukcją i porównywana z pierwszą.
"""
import argparse
import glob
import json
import os
import re
import statistics
import sys
import time
from collections import Counter

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from benchmark import build_policy  # noqa: E402
from board import Board  # noqa: E402
from bridge import legal_moves, make_game_stub, run_id  # noqa: E402
from pieces import Piece  # noqa: E402
from scoring import COMBO_COUNTER_BASE, FULL_CLEAR_BONUS, clear_points, placement_points  # noqa: E402

RUNS_DIR = os.path.join(REPO_ROOT, "bridge", "runs")
DEFAULT_POLICY = ("lookahead-ntuple:ntuple/survival-adce-400k.json"
                  "@beam=128,samples=0,complete=1,gain_weight=100000")
OUTPUT_PATH = os.path.join(REPO_ROOT, "docs", "data", "260-most-gotowosc.json")


def natural(path):
    return [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", os.path.basename(path))]


def is_end(row):
    return bool(row.get("koniec_partii") or row.get("end"))


def valid_board(b):
    return isinstance(b, list) and len(b) == 8 and all(isinstance(r, list) and len(r) == 8 for r in b)


def valid_tray(t):
    if not (isinstance(t, list) and len(t) == 3):
        return False
    live = [s for s in t if s is not None]
    return 1 <= len(live) <= 3 and all(isinstance(s, list) and s and isinstance(s[0], list) for s in live)


def make_board(grid):
    board = Board()
    board.grid = [row[:] for row in grid]
    return board


def make_pieces(tray):
    return [Piece(s, f"slot{i}", -1) if s else None for i, s in enumerate(tray)]


def advance_combo(combo, counter, grid, tray, move):
    """Reguły `Game.apply_placement` po zalogowanym ruchu -> (combo, licznik)."""
    pieces = make_pieces(tray)
    after = make_board(grid)
    after.place_piece(pieces[move["slot"]], move["x"], move["y"])
    rows, cols = after.check_full_lines()
    remaining = sum(1 for i, p in enumerate(pieces) if p is not None and i != move["slot"])
    if rows or cols:
        return combo + 1, COMBO_COUNTER_BASE + remaining
    if counter <= 1:
        return 0, COMBO_COUNTER_BASE
    return combo, counter - 1


def move_gain(combo, grid, tray, move):
    """Punkty za ruch wg `scoring.py` przy zadanym `combo` (przed ruchem)."""
    pieces = make_pieces(tray)
    after = make_board(grid)
    piece = pieces[move["slot"]]
    after.place_piece(piece, move["x"], move["y"])
    rows, cols = after.check_full_lines()
    gained = placement_points(piece)
    if rows or cols:
        gained += clear_points(combo + 1, len(rows) + len(cols))
    after.clear_lines(rows, cols)
    if not any(any(r) for r in after.grid):
        gained += FULL_CLEAR_BONUS
    return gained


def score_check(rows_state):
    """Zgodność przyrostu wyniku z ekranu (`score` następnego wiersza) z punktacją: rekonstrukcja
    combo kontra zaślepka (combo=0). Tylko wiersze wiarygodne i `ok`, z następnym wierszem w pliku."""
    c = Counter()
    for rows, i, combo, reliable in rows_state:
        row, nxt = rows[i], rows[i + 1] if i + 1 < len(rows) else None
        if not (reliable and row.get("ok") and nxt and "move" in nxt and not is_end(nxt)
                and isinstance(row.get("score"), int) and isinstance(nxt.get("score"), int)):
            continue
        delta = nxt["score"] - row["score"]
        c["porownane"] += 1
        c["rekonstrukcja_zgodna"] += delta == move_gain(combo, row["board"], row["tray"], row["move"])
        c["zaslepka_zgodna"] += delta == move_gain(0, row["board"], row["tray"], row["move"])
        c["roznica_modeli_i_wynik_zgodny_z_rekonstrukcja"] += (
            move_gain(0, row["board"], row["tray"], row["move"]) != move_gain(combo, row["board"], row["tray"], row["move"])
            and delta == move_gain(combo, row["board"], row["tray"], row["move"]))
        c["roznica_modeli"] += move_gain(0, row["board"], row["tray"], row["move"]) != move_gain(
            combo, row["board"], row["tray"], row["move"])
    return c


def collect_states():
    """-> (lista unikalnych stanów, licznik pominiętych)."""
    states, seen, skipped = [], set(), Counter()
    checks = Counter()
    for run in sorted(os.listdir(RUNS_DIR)):
        files = sorted(glob.glob(os.path.join(RUNS_DIR, run, "chunk*_moves.jsonl")), key=natural)
        combo, counter, reliable, prev_obs = 0, COMBO_COUNTER_BASE, True, None
        fresh = True  # łańcuch od początku partii: pierwsza plansza musi być pusta
        for path in files:
            with open(path, encoding="utf-8") as f:
                rows = [json.loads(line) for line in f if line.strip()]
            pending = []
            for i, row in enumerate(rows):
                if is_end(row):
                    skipped["wiersz_konca_partii"] += 1
                    combo, counter, reliable, prev_obs = 0, COMBO_COUNTER_BASE, True, None
                    fresh = True
                    continue
                if "move" not in row:
                    skipped["bez_ruchu"] += 1
                    continue
                board, tray = row.get("board"), row.get("tray")
                if not valid_board(board) or not valid_tray(tray):
                    skipped["niepoprawny_stan"] += 1
                    reliable = False
                    continue
                if fresh and not any(any(r) for r in board):
                    fresh = False
                elif fresh:
                    fresh, reliable = False, False  # przebieg zaczyna się w środku partii: combo nieznane
                if prev_obs is not None and prev_obs != board:
                    reliable = False
                sig = (json.dumps(board), json.dumps(tray), combo, counter)
                if sig in seen:
                    skipped["powtorzenie"] += 1
                else:
                    seen.add(sig)
                    states.append({"run": run, "plik": os.path.basename(path), "wiersz": i, "board": board,
                                   "tray": tray, "policy_log": row.get("policy"),
                                   "decision_ms_log": row.get("decision_ms"),
                                   "combo": combo, "counter": counter, "reliable": reliable})
                if row.get("ok") or row.get("observed") != board:
                    pending.append((rows, i, combo, reliable))
                    combo, counter = advance_combo(combo, counter, board, tray, row["move"])
                if not row.get("ok"):
                    # `ok=false` z niezmienioną planszą: ruch nie wszedł, combo bez zmiany (wiarygodne)
                    reliable = reliable and row.get("observed") == board
                prev_obs = row.get("observed")
            checks.update(score_check(pending))
    return states, skipped, checks


def decide(policy, grid, tray, combo=None, counter=None):
    board = make_board(grid)
    pieces = make_pieces(tray)
    moves = legal_moves(board, pieces)
    game = make_game_stub(board, pieces)
    if combo is not None:
        game.combo, game.combo_counter = combo, counter
    t0 = time.perf_counter()
    action = policy.act(game, moves)
    ms = (time.perf_counter() - t0) * 1000
    return action, moves, ms


def pct(values, q):
    values = sorted(values)
    return values[min(len(values) - 1, int(round(q * (len(values) - 1))))] if values else None


def dist(values):
    if not values:
        return None
    return {"n": len(values), "mediana": round(statistics.median(values), 2),
            "p95": round(pct(values, 0.95), 2), "max": round(max(values), 2)}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--policy", default=DEFAULT_POLICY)
    ap.add_argument("--limit", type=int, default=0, help="tylko pierwsze N stanów (0 = wszystkie)")
    ap.add_argument("--out", default=OUTPUT_PATH)
    args = ap.parse_args()

    states, skipped, checks = collect_states()
    if args.limit:
        states = states[:args.limit]
    policy = build_policy(args.policy, {"torch_seed": 0})
    if hasattr(policy, "reset"):
        policy.reset(run_id(os.environ))

    exceptions, illegal, times, by_tray = [], [], [], Counter()
    times_by_tray = {1: [], 2: [], 3: []}
    combo_diff = combo_changed = 0
    rel = {"stany": 0, "roznica_stanu": 0, "decyzja_zmieniona": 0}
    changed_examples, nondeterministic = [], 0
    for k, st in enumerate(states):
        live = sum(1 for s in st["tray"] if s)
        by_tray[live] += 1
        try:
            action, moves, ms = decide(policy, st["board"], st["tray"])
        except Exception as exc:  # noqa: BLE001 - pomiar: łapiemy wszystko i raportujemy
            exceptions.append({"run": st["run"], "plik": st["plik"], "wiersz": st["wiersz"],
                               "wyjatek": f"{type(exc).__name__}: {exc}"})
            continue
        times.append(ms)
        times_by_tray[live].append(ms)
        if tuple(action) not in set(moves):
            illegal.append({"run": st["run"], "plik": st["plik"], "wiersz": st["wiersz"], "akcja": list(action)})
        differs = (st["combo"], st["counter"]) != (0, COMBO_COUNTER_BASE)
        if st["reliable"]:
            rel["stany"] += 1
        if differs:
            combo_diff += 1
            rel["roznica_stanu"] += st["reliable"]
            try:
                action2, _m, _t = decide(policy, st["board"], st["tray"], st["combo"], st["counter"])
            except Exception as exc:  # noqa: BLE001
                exceptions.append({"run": st["run"], "plik": st["plik"], "wiersz": st["wiersz"],
                                   "wyjatek": "rekonstrukcja combo: " + f"{type(exc).__name__}: {exc}"})
                continue
            if tuple(action2) != tuple(action):
                combo_changed += 1
                rel["decyzja_zmieniona"] += st["reliable"]
                if len(changed_examples) < 10:
                    changed_examples.append({"run": st["run"], "plik": st["plik"], "wiersz": st["wiersz"],
                                             "combo": st["combo"], "licznik": st["counter"],
                                             "akcja_zaslepka": list(action), "akcja_rekonstrukcja": list(action2)})
        elif k % 25 == 0:
            again, _m, _t = decide(policy, st["board"], st["tray"])
            nondeterministic += tuple(again) != tuple(action)
        if k % 100 == 0:
            print(f"{k}/{len(states)}", flush=True)

    logged = [s["decision_ms_log"] for s in states if s["decision_ms_log"] is not None]
    log_by_policy = {}
    for s in states:
        if s["decision_ms_log"] is not None:
            log_by_policy.setdefault(s["policy_log"], []).append(s["decision_ms_log"])
    out = {
        "polityka": args.policy,
        "stany": len(states),
        "stany_wg_liczby_klockow_na_tacce": {str(k): v for k, v in sorted(by_tray.items())},
        "pominiete": dict(skipped),
        "wyjatki": len(exceptions),
        "wyjatki_lista": exceptions[:20],
        "nielegalne_akcje": len(illegal),
        "nielegalne_lista": illegal[:20],
        "czas_decyzji_ms": dist(times),
        "czas_decyzji_ms_wg_klockow_na_tacce": {str(k): dist(v) for k, v in times_by_tray.items()},
        "czas_decyzji_ms_w_logach": dist(logged),
        "czas_decyzji_ms_w_logach_wg_polityki": {k: dist(v) for k, v in log_by_policy.items()},
        "combo": {
            "stany_gdzie_rekonstrukcja_rozna_od_zaslepki": combo_diff,
            "decyzje_zmienione_przez_stan_combo": combo_changed,
            "udzial_zmienionych_w_stanach_z_roznica": round(combo_changed / combo_diff, 4) if combo_diff else None,
            "udzial_zmienionych_we_wszystkich_stanach": round(combo_changed / len(states), 4) if states else None,
            "tylko_stany_wiarygodne": rel,
            "niedeterminizm_na_probce_bez_roznicy": nondeterministic,
            "zgodnosc_przyrostu_wyniku_z_ekranu": dict(checks),
            "przyklady": changed_examples,
        },
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print(json.dumps({k: v for k, v in out.items() if k not in ("wyjatki_lista", "nielegalne_lista")},
                     indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
