#!/usr/bin/env python3
"""
#249: czy prawdziwa apka daje wyłącznie układalne tacki? Pomiar z istniejących logów mostu
(`bridge/runs/*/*.jsonl`), bez emulatora. Nie zmienia mostu, polityki, generatora ani symulatora.

Dla każdego wiersza z trzema niepustymi slotami tacki (chwila pojawienia się tacki) woła
`board.tray_playable` na zalogowanej planszy. Kształty są przycinane do bounding boxa
(logi trzymają je w macierzach 5x6 z zerowym dopełnieniem, a `tray_playable` przesuwa
kształt względem lewego górnego rogu macierzy). Nierozpoznany kształt (poza `PIECE_POOL`)
albo plansza niespójna z `observed` poprzedniego wiersza (gdy ten ma `ok`) to wpisy
"nieoceniane", liczone osobno z powodem. Kolejne identyczne wiersze (ta sama plansza i
tacka — ponowienie po `ok=false`, chunk-loop) liczone są raz; reszta to `powtorzenie`.

Końce partii: wiersz z `koniec_partii: true` (ekran końca gry odczytany przez most) albo
`end: "brak legalnego ruchu wg odczytu"` (most nie widzi legalnego ruchu; to NIE jest
potwierdzona śmierć — bywa artefaktem odczytu). Dla każdego sprawdzana jest ostatnia
tacka pojawiona się w tym samym pliku przed końcem: czy była układalna w całości.
"""
import glob
import json
import os
import sys
from collections import Counter, defaultdict

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from board import tray_playable  # noqa: E402
from pieces import PIECE_POOL  # noqa: E402

RUNS_DIR = os.path.join(REPO_ROOT, "bridge", "runs")
OUTPUT_PATH = os.path.join(REPO_ROOT, "docs", "data", "249-most-tacki.json")
END_NO_MOVE = "brak legalnego ruchu wg odczytu"
CHUNK_MOVES = 60  # rozmiar kawałka z issue (kawałki w logach mają 30 lub mniej)


def trim(shape):
    rows = [i for i, r in enumerate(shape) if any(r)]
    cols = [j for j in range(len(shape[0])) if any(r[j] for r in shape)]
    if not rows:
        return None
    return [[1 if shape[i][j] else 0 for j in range(cols[0], cols[-1] + 1)] for i in range(rows[0], rows[-1] + 1)]


def known_shapes():
    return {tuple(map(tuple, trim(p.shape))) for p in PIECE_POOL}


def full_tray(tray):
    return isinstance(tray, list) and len(tray) == 3 and all(t is not None for t in tray)


def valid_board(b):
    return isinstance(b, list) and len(b) == 8 and all(isinstance(r, list) and len(r) == 8 for r in b)


def evaluate(row, prev, known):
    """-> (status, powod). status: ukladalna | nieukladalna | nieoceniana."""
    board, tray = row.get("board"), row.get("tray")
    if not valid_board(board):
        return "nieoceniana", "zla_wielkosc_planszy"
    shapes = []
    for s in tray:
        t = trim(s) if isinstance(s, list) and s and isinstance(s[0], list) else None
        if t is None or tuple(map(tuple, t)) not in known:
            return "nieoceniana", "ksztalt_nierozpoznany"
        shapes.append(t)
    if prev is not None and prev.get("ok") and prev.get("observed") != board:
        return "nieoceniana", "plansza_niezgodna_z_poprzednim_observed"
    res = tray_playable(board, shapes)
    if res is None:
        return "nieoceniana", "budzet_wezlow_wyczerpany"
    return ("ukladalna" if res else "nieukladalna"), None


def is_end(row):
    if row.get("koniec_partii"):
        return "ekran_konca_gry"
    if row.get("end") == END_NO_MOVE:
        return "brak_legalnego_ruchu_wg_odczytu"
    return None


def natural(path):
    import re
    return [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", os.path.basename(path))]


def analyse():
    known = known_shapes()
    trays, ends = [], []
    per_run = defaultdict(Counter)
    moves_per_chunk = []  # (run, plik, postawienia)
    for run in sorted(os.listdir(RUNS_DIR)):
        files = sorted(glob.glob(os.path.join(RUNS_DIR, run, "*.jsonl")), key=natural)
        for path in files:
            with open(path, encoding="utf-8") as f:
                rows = [json.loads(l) for l in f if l.strip()]
            fname = os.path.basename(path)
            moves_per_chunk.append((run, fname, sum(1 for r in rows if "move" in r), sum(1 for r in rows if r.get("ok"))))
            last_tray = None
            last_sig = None
            placed_since = 0  # udane postawienia z ostatniej tacki (wiersze po jej pojawieniu się)
            for i, row in enumerate(rows):
                kind = is_end(row)
                if kind is None and full_tray(row.get("tray")):
                    sig = (json.dumps(row.get("board")), json.dumps(row["tray"]))
                    prev = rows[i - 1] if i else None
                    if sig == last_sig:
                        per_run[run]["powtorzenie"] += 1
                    else:
                        status, why = evaluate(row, prev, known)
                        rec = {"run": run, "plik": fname, "wiersz": i, "status": status, "powod": why,
                               "tray_cells": [sum(map(sum, s)) for s in row["tray"]],
                               "board_filled": sum(map(sum, row["board"])) if valid_board(row["board"]) else None}
                        trays.append(rec)
                        per_run[run][status] += 1
                        last_tray = rec
                        placed_since = 0
                    last_sig = sig
                if kind is None and "move" in row and row.get("ok"):
                    placed_since += 1
                if kind:
                    # wiersz końca to odczyt nakładki ekranu końca gry (kształty-śmieci), nie tacka apki
                    per_run[run]["wiersz_konca_gry_pominiety"] += 1
                    if last_tray is None:
                        klasa = "brak_tacki_w_pliku"
                    elif last_tray["status"] != "ukladalna" and last_tray["status"] != "nieukladalna":
                        klasa = "ostatnia_tacka_nieoceniona"
                    elif last_tray["status"] == "nieukladalna":
                        klasa = "smierc_wymuszona_przez_apke"
                    elif placed_since >= 3:
                        klasa = "ostatnia_tacka_ulozona_smiertelna_tacka_niewidoczna"
                    else:
                        klasa = "smierc_w_trakcie_ukladalnej_tacki_chybienie_lub_blad_odczytu"
                    end = {"run": run, "plik": fname, "wiersz": i, "rodzaj": kind,
                           "wynik_koncowy": row.get("wynik_koncowy"), "klasa": klasa, "postawien_z_ostatniej_tacki": placed_since,
                           "ostatnia_tacka": None if last_tray is None else
                           {"wiersz": last_tray["wiersz"], "status": last_tray["status"], "powod": last_tray["powod"]}}
                    ends.append(end)
    return trays, ends, per_run, moves_per_chunk


def d550_summary(known):
    path = os.path.join(RUNS_DIR, "d550db3", "pomiar.json")
    if not os.path.exists(path):
        return None
    lookup = {p.name: trim(p.shape) for p in PIECE_POOL}
    c = Counter()
    for pr in json.load(open(path))["pairs"]:
        try:
            shapes = [lookup[p["name"]] for p in pr["tray"]]
        except (KeyError, TypeError):
            c["nieoceniana_nierozpoznany"] += 1
            continue
        r = tray_playable(pr["board"], shapes)
        c["nieoceniana_budzet" if r is None else ("ukladalna" if r else "nieukladalna")] += 1
    return dict(c)


def cost_estimate(per_chunk_logged, max_ok_per_run):
    """Postawienia na 1 mln pkt apki: 141 pkt/postawienie (#241, beam=128,complete=1) razy przelicznik
    apka/wzór (docs/punktacja-apka-vs-wzor.md: 1,43-4,68x). Sesja verifiera = przebieg `bridge/runs/<run>`;
    jej pojemność: największa liczba udanych postawień w jednym przebiegu z logów."""
    target, pps = 1_000_000, 141.0
    rows = {}
    for label, ratio in (("bez_przelicznika_1.00x", 1.0), ("1.43x", 1.43), ("4.68x", 4.68)):
        placements = target / (pps * ratio)
        rows[label] = {"pkt_apki_na_postawienie": round(pps * ratio, 1),
                       "postawienia": round(placements),
                       "kawalki_po_60": -(-round(placements) // CHUNK_MOVES),
                       "sesje_verifiera_wg_max_przebiegu": round(placements / max_ok_per_run, 2)}
    return {"pkt_na_postawienie_wzor": pps, "cel_pkt": target, "max_udanych_postawien_w_przebiegu": max_ok_per_run,
            "warianty": rows}


def main():
    trays, ends, per_run, chunks = analyse()
    total = Counter(t["status"] for t in trays)
    reasons = Counter(t["powod"] for t in trays if t["powod"])
    total_placed = sum(c[2] for c in chunks)
    total_ok = sum(c[3] for c in chunks)
    out = {
        "tacki_ogolem_unikalne": len(trays),
        "podzial": dict(total),
        "nieoceniane_powody": dict(reasons),
        "per_run": {r: dict(c) for r, c in per_run.items()},
        "koniec_partii": ends,
        "d550db3_pary_z_pomiar_json": d550_summary(known_shapes()),
        "przepustowosc": {
            "postawienia_zalogowane_wiersze_z_move": total_placed,
            "postawienia_ok": total_ok,
            "kawalki": len(chunks),
            "postawien_na_kawalek_srednio": round(total_placed / len(chunks), 2) if chunks else None,
            "znaczniki_czasu_w_logach": False,
            "per_kawalek": [{"run": r, "plik": f, "wiersze_z_move": m, "ok": o} for r, f, m, o in chunks],
        },
        "tacki": trays,
    }
    run_moves = defaultdict(lambda: [0, 0])
    for r, _f, m, o in chunks:
        run_moves[r][0] += m
        run_moves[r][1] += o
    out["przepustowosc"]["per_run_wiersze_z_move_i_ok"] = dict(run_moves)
    out["koszt_1mln"] = cost_estimate(out["przepustowosc"]["postawien_na_kawalek_srednio"],
                                      max(v[1] for v in run_moves.values()))
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print("tacki:", len(trays), dict(total), dict(reasons))
    print("per_run:")
    for r, c in sorted(per_run.items()):
        print(" ", r, dict(c))
    print("d550db3:", out["d550db3_pary_z_pomiar_json"])
    print("konce:", len(ends))
    for e in ends:
        print(" ", e["run"], e["plik"], e["wiersz"], e["rodzaj"], e["wynik_koncowy"], e["klasa"],
              e["postawien_z_ostatniej_tacki"], e["ostatnia_tacka"])
    print("klasy koncow:", dict(Counter(e["klasa"] for e in ends)))
    print("przepustowosc:", total_placed, total_ok, len(chunks))


if __name__ == "__main__":
    main()
