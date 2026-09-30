#!/usr/bin/env python3
"""Diagnoza przegranej z serii weryfikacyjnej (#292). Nic nie naprawia, niczego nie gra na emulatorze.

    python3 tools/przegrana_serii.py KATALOG [--polityka SPEC] [--out PLIK.json]

Czyta `KATALOG/pomiar.json` i pliki ruchów z listy `kawalki` (format `docs/seria-skrypt.md`).
Dla `zakonczenie: przegrana` odtwarza z logu ostatnią tackę i wypisuje werdykt:

  tacka_nieukladalna  tacka, przy której partia się skończyła, nie dawała się ułożyć w całości
                      (przegląd wyczerpujący) — generator apki zagrałby przeciw #249
  slepa_plamka        ułożenie istniało, a polityka w symulatorze na zalogowanych stanach wybiera
                      dokładnie te ruchy co most — przeszukanie polityki go nie znajduje
  rozjazd_mostu       polityka w symulatorze gra inaczej niż most na tej samej planszy i tacce,
                      albo odczyt mostu sam sobie przeczy (ok=false przed ostatnim ruchem,
                      koniec mimo legalnego ruchu wg odczytu)
  nieoceniane         log nie niesie stanu potrzebnego do werdyktu (powód w polu `powod`)

Wiersz `koniec_partii` to odczyt nakładki ekranu końca (plansza i kształty-śmieci), więc stan końcowy
bierzemy z ostatniego wiersza z ruchem: `expected` (plansza po ruchu; `observed` ostatniego ruchu bywa
już nakładką) i tacka bez postawionego klocka; nowszy most niesie to też w polu `przed_koncem`.
Jeśli ostatnia tacka została ułożona w całości, tacka, przy której padła gra, nie była widoczna
w logu — werdykt `nieoceniane` (`nowa_tacka_niezalogowana`).

Dla innego `zakonczenie` niż `przegrana` kończy komunikatem i kodem 0.
"""
import argparse
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (REPO_ROOT, os.path.join(REPO_ROOT, "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

import bridge
import most_tacki_ukladalne as mtu
from board import Board
from pieces import Piece

RECORD_PATH = os.path.join(REPO_ROOT, "bench", "record.json")
VERDICTS = ("tacka_nieukladalna", "slepa_plamka", "rozjazd_mostu", "nieoceniane")


def default_policy_spec():
    with open(RECORD_PATH, encoding="utf-8") as f:
        return json.load(f)["arms"]["candidate"]["spec"]


def load_rows(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def split_trays(moves):
    """Wiersze z ruchem -> lista tacek (każda: lista wierszy). Nowa tacka = pełna trójka innej pary
    plansza+tacka niż poprzednia (ponowienie po nieudanym ruchu nie otwiera nowej)."""
    trays, last_sig = [], None
    for r in moves:
        if mtu.full_tray(r.get("tray")):
            sig = json.dumps([r.get("board"), r["tray"]])
            if sig != last_sig:
                trays.append([])
            last_sig = sig
        if trays:
            trays[-1].append(r)
    return trays


def state_before_end(end_row, last_move):
    """(plansza po ostatnim ruchu, tacka po nim) — z `przed_koncem`, inaczej z wiersza ostatniego ruchu."""
    pk = end_row.get("przed_koncem")
    if pk and mtu.valid_board(pk.get("board")) and isinstance(pk.get("tray"), list) and len(pk["tray"]) == 3:
        return pk["board"], pk["tray"]
    slot = last_move["move"]["slot"]
    tray = [None if j == slot else s for j, s in enumerate(last_move["tray"])]
    return last_move["expected"], tray


def to_pieces(tray):
    return [Piece(s, f"slot{i}", -1) if s else None for i, s in enumerate(tray)]


def to_board(grid):
    b = Board()
    b.grid = [row[:] for row in grid]
    return b


def build_policy(spec):
    """(polityka, błąd). Specyfikacje ze ścieżkami względnymi rozwiązujemy od korzenia repo."""
    cwd = os.getcwd()
    try:
        os.chdir(REPO_ROOT)
        policy = bridge.build_policy(spec, {"torch_seed": 0})
        if hasattr(policy, "reset"):
            policy.reset(0)
        return policy, None
    except Exception as e:
        return None, repr(e)
    finally:
        os.chdir(cwd)


def policy_diffs(policy, rows):
    """Dla każdego zalogowanego ruchu: co wybrałaby polityka na tej samej planszy i tacce (stan sprzed ruchu)."""
    diffs = []
    for r in rows:
        if not (mtu.valid_board(r.get("board")) and isinstance(r.get("tray"), list) and len(r["tray"]) == 3):
            continue
        board, pieces = to_board(r["board"]), to_pieces(r["tray"])
        moves = bridge.legal_moves(board, pieces)
        if not moves:
            continue
        i, x, y = policy.act(bridge.make_game_stub(board, pieces), moves)
        got = {"slot": i, "x": x, "y": y}
        if got != r["move"]:
            diffs.append({"n": r.get("n"), "most": r["move"], "polityka": got})
    return diffs


def diagnose(pomiar, rows, policy_spec, policy_factory=build_policy):
    """-> słownik wyniku: `werdykt`, `powod`, `dane`."""
    def result(verdict, reason, **data):
        return {"werdykt": verdict, "powod": reason, "dane": data}

    ends = [i for i, r in enumerate(rows) if r.get("koniec_partii")]
    if not ends:
        return result("nieoceniane", "brak_wiersza_koniec_partii")
    end_row = rows[ends[-1]]
    start = ends[-2] + 1 if len(ends) > 1 else 0
    moves = [r for r in rows[start:ends[-1]] if "move" in r and "expected" in r]
    trays = split_trays(moves)
    if not trays:
        return result("nieoceniane", "brak_ruchow_z_pelna_tacka")

    known = mtu.known_shapes()
    last = trays[-1]
    final_move = last[-1]
    board_end, tray_end = state_before_end(end_row, final_move)
    if not mtu.valid_board(board_end):
        return result("nieoceniane", "zla_wielkosc_planszy")
    remaining = [s for s in tray_end if s]

    # rozjazd odczytu: ok=false przed ostatnim ruchem (ostatni ma `observed` z nakładki ekranu końca)
    earlier = moves[:-1]
    in_scope = {id(r) for t in trays[-2:] for r in t}
    ok_false = [r.get("n") for r in earlier if r.get("ok") is False and id(r) in in_scope]

    def shapes_of(tray_rows):
        out = []
        for s in tray_rows[0]["tray"]:
            t = mtu.trim(s) if isinstance(s, list) and s and isinstance(s[0], list) else None
            if t is None or tuple(map(tuple, t)) not in known:
                return None
            out.append(t)
        return out

    data = {"ostatnie_n": final_move.get("n"), "plansza_po_ostatnim_ruchu": board_end,
            "tacka_po_ostatnim_ruchu": tray_end, "ok_false_n": ok_false}
    if ok_false:
        return result("rozjazd_mostu", "ok_false_przed_ostatnim_ruchem", **data)

    if remaining:
        # gra skończyła się w trakcie tacki: reszta tacki nie mieści się na planszy
        legal = bridge.legal_moves(to_board(board_end), to_pieces(tray_end))
        data["legalne_ruchy_po_ostatnim"] = len(legal)
        if legal:
            return result("rozjazd_mostu", "koniec_mimo_legalnego_ruchu_wg_odczytu", **data)
        dying, previous = last, (trays[-2] if len(trays) > 1 else None)
    else:
        data["nowa_tacka"] = "niezalogowana"
        dying, previous = None, last

    diffs, policy_err = {}, None
    policy = None
    if previous is not None or dying is not None:
        policy, policy_err = policy_factory(policy_spec)
    if policy is not None:
        for name, tr in (("poprzednia", previous), ("ostatnia", dying)):
            if tr is not None:
                diffs[name] = policy_diffs(policy, tr)
    data["polityka"] = policy_spec
    if policy_err:
        data["polityka_blad"] = policy_err
    data["roznice_polityki"] = diffs

    if dying is None:
        return result("nieoceniane", "nowa_tacka_niezalogowana", **data)

    shapes = shapes_of(dying)
    if shapes is None:
        return result("nieoceniane", "ksztalt_nierozpoznany", **data)
    start_board = dying[0]["board"]
    if not mtu.valid_board(start_board):
        return result("nieoceniane", "zla_wielkosc_planszy", **data)
    playable = mtu.tray_playable(start_board, shapes)
    data["tacka_smierci"] = {"n": dying[0].get("n"), "plansza": start_board, "tacka": dying[0]["tray"],
                             "ukladalna": playable}
    if playable is None:
        return result("nieoceniane", "budzet_wezlow_wyczerpany", **data)
    if not playable:
        return result("tacka_nieukladalna", "przeglad_wyczerpujacy_bez_ukladu", **data)
    if policy is None:
        return result("nieoceniane", "polityka_niedostepna", **data)
    if any(diffs.values()):
        return result("rozjazd_mostu", "polityka_w_symulatorze_gra_inaczej", **data)
    return result("slepa_plamka", "uklad_istnial_polityka_zgodna_z_mostem", **data)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("katalog", help="katalog partii serii (pomiar.json, chunkN_moves.jsonl)")
    ap.add_argument("--polityka", default=None, help="spec polityki (domyślnie: bench/record.json, candidate.spec)")
    ap.add_argument("--out", default=None, help="zapisz wynik jako JSON")
    args = ap.parse_args(argv)

    pomiar_path = os.path.join(args.katalog, "pomiar.json")
    with open(pomiar_path, encoding="utf-8") as f:
        pomiar = json.load(f)
    zakonczenie = pomiar.get("zakonczenie")
    if zakonczenie != "przegrana":
        print(f"zakonczenie: {zakonczenie} — brak przegranej do diagnozy")
        return 0

    rows = []
    for name in pomiar.get("kawalki", []):
        path = os.path.join(args.katalog, name)
        if not os.path.exists(path):
            print(f"uwaga: brak pliku ruchów {name}", file=sys.stderr)
            continue
        rows.extend(load_rows(path))

    spec = args.polityka or default_policy_spec()
    out = diagnose(pomiar, rows, spec)
    out["polityka_serii"] = pomiar.get("polityka")
    out["wynik_koncowy"] = pomiar.get("wynik_koncowy")
    out["zrzut_konca"] = pomiar.get("zrzut_konca")
    if out["polityka_serii"] and out["polityka_serii"] != spec:
        print(f"uwaga: seria grała {out['polityka_serii']!r}, diagnoza używa {spec!r}", file=sys.stderr)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=1, ensure_ascii=False)
            f.write("\n")
    print(f"werdykt: {out['werdykt']} ({out['powod']})")
    for k, v in out["dane"].items():
        if k.startswith("plansza") or k == "tacka_smierci":
            continue
        print(f"  {k}: {json.dumps(v, ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
