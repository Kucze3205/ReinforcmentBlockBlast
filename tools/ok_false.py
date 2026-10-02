#!/usr/bin/env python3
"""Klasyfikacja wpisów `"ok": false` z materiału serii (#333). Nic nie naprawia.

    python3 tools/ok_false.py [KATALOG_SERII] [--out PLIK.md]

Przechodzi po `docs/seria/s*/partia-*/chunk*_moves.jsonl` i każdy wpis z ruchem i `"ok": false` wrzuca do jednej grupy
(różnica `observed` vs `expected`, pole po polu):
  - `duchy_w_czyszczonych`: tylko nadmiar (observed=1, expected=0), i to wyłącznie w liniach wyczyszczonych tym ruchem
    (typowo baner „Combo N" czytany jako klocki);
  - `nadmiar_gdzie_indziej`: tylko nadmiar, przynajmniej jedno pole poza liniami wyczyszczonymi tym ruchem;
  - `brak_pol`: tylko brak (observed=0, expected=1);
  - `mieszane`: i nadmiar, i brak.
Osobna kolumna `ruch_nieprzyjety` liczy wpisy, w których `observed` == `board` (plansza się nie ruszyła).
Dla pierwszej grupy liczy, w ilu przypadkach duch dotrwał do decyzji następnego ruchu (kolejny wpis z ruchem w tym samym
pliku ma te pola w `board`) i w ilu przypadkach ruch potwierdza tacka tego następnego wpisu (`tray_consumed`).
"""
import argparse
import glob
import json
import os
import sys
from itertools import permutations

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))

import bridge
from board import TRAY_PLAYABLE_NODE_BUDGET as TRAY_BUDZET, Board, _tray_dfs_playable as tray_dfs_playable
from pieces import PIECE_POOL, Piece

GRUPY = ("duchy_w_czyszczonych", "nadmiar_gdzie_indziej", "brak_pol", "mieszane")


def klasyfikuj(r):
    """-> (grupa, nadmiar, brak, czyszczone) dla wpisu z ruchem i `ok: false`."""
    board = Board()
    board.grid = [row[:] for row in r["board"]]
    m = r["move"]
    shape = r["tray"][m["slot"]]
    cleared = bridge.cleared_cells(board, Piece(shape, "slot", -1), m["x"], m["y"])
    exp, obs = r["expected"], r["observed"]
    nadmiar = [(y, x) for y in range(8) for x in range(8) if obs[y][x] and not exp[y][x]]
    brak = [(y, x) for y in range(8) for x in range(8) if exp[y][x] and not obs[y][x]]
    if nadmiar and brak:
        grupa = "mieszane"
    elif brak:
        grupa = "brak_pol"
    elif nadmiar:
        grupa = "duchy_w_czyszczonych" if all(p in cleared for p in nadmiar) else "nadmiar_gdzie_indziej"
    else:  # ok=false bez różnicy pól nie istnieje w logu mostu
        grupa = "mieszane"
    return grupa, nadmiar, brak, cleared


def przejdz(plik):
    """Zlicza grupy w jednym pliku; -> (słownik liczników, lista przypadków pierwszej grupy)."""
    with open(plik, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    ruchy = [r for r in rows if "move" in r and "observed" in r]
    cnt = dict.fromkeys(GRUPY, 0)
    cnt.update(ok_false=0, ruchow=len(ruchy), ruch_nieprzyjety=0, duch_dotrwal=0, tacka_potwierdza=0, bez_nastepnego=0)
    for k, r in enumerate(ruchy):
        if r.get("ok") is not False:
            continue
        cnt["ok_false"] += 1
        cnt["ruch_nieprzyjety"] += r["observed"] == r["board"]
        grupa, nadmiar, _, _ = klasyfikuj(r)
        cnt[grupa] += 1
        if grupa != "duchy_w_czyszczonych":
            continue
        if k + 1 >= len(ruchy):
            cnt["bez_nastepnego"] += 1
            continue
        nast = ruchy[k + 1]
        if all(nast["board"][y][x] for y, x in nadmiar):
            cnt["duch_dotrwal"] += 1
        pieces = [Piece(s, "slot", -1) if s else None for s in r["tray"]]
        if bridge.tray_consumed(pieces, r["move"]["slot"], [(s,) if s else None for s in nast["tray"]]):
            cnt["tacka_potwierdza"] += 1
    return cnt


def zbierz(katalog):
    """-> {seria: liczniki} dla `katalog/s*/partia-*/chunk*_moves.jsonl`."""
    out = {}
    for seria in sorted(d for d in os.listdir(katalog) if d.startswith("s") and d[1:].isdigit()):
        razem = None
        for plik in sorted(glob.glob(os.path.join(katalog, seria, "partia-*", "chunk*_moves.jsonl"))):
            c = przejdz(plik)
            razem = c if razem is None else {k: razem[k] + c[k] for k in razem}
        if razem is not None:
            out[seria] = razem
    return out


def tabela(wyniki):
    kol = ("ruchow", "ok_false") + GRUPY + ("ruch_nieprzyjety",) + ("duch_dotrwal", "tacka_potwierdza", "bez_nastepnego")
    suma = {k: sum(w[k] for w in wyniki.values()) for k in kol}
    linie = ["| seria | " + " | ".join(kol) + " |", "|---|" + "---|" * len(kol)]
    for seria, w in list(wyniki.items()) + [("**suma**", suma)]:
        linie.append(f"| {seria} | " + " | ".join(str(w[k]) for k in kol) + " |")
    return "\n".join(linie), suma


# --- podgrupy mechanizmu (#335) -------------------------------------------------------------------------------------
# Dla trzech grup spoza `duchy_w_czyszczonych`. Najpierw nazwy całych wpisów (cała plansza odczytu pasuje do wzorca),
# potem etykiety pól: nadmiar -> `zakryte_wraca` (pole zakryte w poprzednim kroku) | `serce` | `napis` | `baner`
# (w czyszczonej linii albo wiersz nad czyszczonym), brak -> `dawny_duch` | `napis` | `klocek_niepelny`. Nazwa podgrupy
# to rodzaje etykiet połączone `+`; pole bez etykiety daje `niewyjasnione` (przy >= DUZA_ROZNICA pól `niewyjasnione_duze`).
# Nic z tego nie wchodzi do mostu — to opis materiału, nie reguła odczytu.

WIERSZE_NAPISU = (3, 4, 5)  # napis pochwały („Perfect!") wisi na środku planszy, na wierszu 4 (state.png s4/p1/k22/055)
DUZA_ROZNICA = 10  # tyle różniących się pól i brak etykiety: `niewyjasnione_duze` (m.in. ekran reklamy/koła czytany jak plansza)
SERCE_MIN_POL = 4  # serce animacji „Combo N" (różowe, środek planszy: s5/p8/k1/049, s1/p5/k2/010) czytane jak klocki
SERCE_WIERSZE, SERCE_KOLUMNY = (1, 6), (1, 6)
RODZAJE = ("baner", "serce", "napis", "dawny_duch", "zakryte_wraca", "klocek_niepelny")


def _sym(board, shape, x, y):
    b = Board()
    b.grid = [row[:] for row in board]
    p = Piece(shape, "slot", -1)
    return bridge.simulate(b, p, x, y) if b.can_place_piece(p, x, y) else None


def _wiersze_czyszczone(cleared):
    return {y for y in range(8) if all((y, c) in cleared for c in range(8))}


def _wsteczny_slad(ruchy, k, y, x, ma_obserwacje, ma_oczekiwanie):
    """Idąc wstecz po ciągłych wpisach (n-1, n-2, …) szuka wpisu, w którym `observed` w (y, x) == `ma_obserwacje`, a
    `expected` == `ma_oczekiwanie`; przerywa, gdy pole w `board` ma już wartość inną niż w obecnym wpisie `k`."""
    j = k - 1
    stan = ruchy[k]["board"][y][x]
    while j >= 0 and ruchy[j]["n"] == ruchy[j + 1]["n"] - 1:
        p = ruchy[j]
        if p["observed"][y][x] == ma_obserwacje and p["expected"][y][x] == ma_oczekiwanie:
            return True
        if p["board"][y][x] != stan:
            return False
        j -= 1
    return False


def _dawny_duch(ruchy, k, y, x):
    """Pole (y, x) planszy wpisu `k` jest duchem z wcześniejszego kroku: idąc wstecz trafiamy na wpis, w którym
    `observed`=1, a `expected`=0, i pole przez cały czas było w `board`."""
    return ruchy[k]["board"][y][x] == 1 and _wsteczny_slad(ruchy, k, y, x, 1, 0)


def _zakryte_wraca(ruchy, k, y, x):
    """Odbicie `_dawny_duch`: pole puste w `board` wpisu `k` było wcześniej zakryte (`observed`=0, `expected`=1)."""
    return ruchy[k]["board"][y][x] == 0 and _wsteczny_slad(ruchy, k, y, x, 0, 1)


def _cele_klocka(r):
    m = r["move"]
    shape = r["tray"][m["slot"]]
    return {(m["y"] + i, m["x"] + j) for i, row in enumerate(shape) for j, v in enumerate(row) if v}


def nazwa_calosci(r):
    """Nazwa wpisu, gdy cały `observed` jest planszą z innym klockiem/miejscem/bez ruchu; inaczej None.
    `inny_klocek` tylko gdy odczyt ma pola poza klockiem z tacki (inaczej to klocek niepełny, patrz `etykiety`)."""
    obs, board, m = r["observed"], r["board"], r["move"]
    if obs == board:
        return "plansza_bez_zmian"
    if not any(any(row) for row in obs):
        return "odczyt_pusty"  # klatka przejściowa: pusta plansza przy niepustej (następny odczyt wraca do `expected`)
    shape = r["tray"][m["slot"]]
    for y in range(8):
        for x in range(8):
            if (x, y) != (m["x"], m["y"]) and _sym(board, shape, x, y) == obs:
                return "klocek_obok_celu"
    _, nadmiar, _, _ = klasyfikuj(r)
    if not nadmiar:
        return None
    for p in PIECE_POOL:
        if p.shape == shape:
            continue
        for y in range(8):
            for x in range(8):
                if _sym(board, p.shape, x, y) == obs:
                    return "inny_klocek"
    return None


ODCZYT_BLEDNY = ("baner", "serce", "napis", "klocek_niepelny", "plansza_bez_zmian", "odczyt_pusty", "duchy_w_czyszczonych")
ODCZYT_PRAWDZIWY = ("dawny_duch", "zakryte_wraca", "klocek_obok_celu")  # `expected` niesie błąd albo klocek spadł obok


def odczyt_bledny(nazwa):
    """'tak': nazwa podgrupy ma rodzaj, w którym odczyt widzi obcy obiekt jako klocek albo klocek jako puste (baner,
    serce, napis, klocek zakryty efektem); 'nie': wszystkie rodzaje to echo wcześniejszego kroku albo klocek obok celu
    (odczyt oddaje prawdę); 'nieznane': `inny_klocek` i `niewyjasnione*` bez rodzaju błędnego."""
    czesci = nazwa.split("+")
    if any(c in ODCZYT_BLEDNY for c in czesci):
        return "tak"
    return "nie" if all(c in ODCZYT_PRAWDZIWY for c in czesci) else "nieznane"


def etykiety(r, ruchy=None, k=None):
    """-> (etykiety nadmiaru, etykiety braku); `None` w liście = pole bez wyjaśnienia."""
    _, nadmiar, brak, cleared = klasyfikuj(r)
    wiersze = _wiersze_czyszczone(cleared)
    napis = any(y == 4 for y, _ in nadmiar + brak)
    klocek = _cele_klocka(r)
    wraca = {p for p in nadmiar if ruchy is not None and _zakryte_wraca(ruchy, k, *p)}
    reszta = [p for p in nadmiar if p not in wraca]
    serce = (len(reszta) >= SERCE_MIN_POL and len({y for y, _ in reszta}) >= 3
             and all(SERCE_WIERSZE[0] <= y <= SERCE_WIERSZE[1] and SERCE_KOLUMNY[0] <= x <= SERCE_KOLUMNY[1]
                     for y, x in reszta))
    en, eb = [], []
    for y, x in nadmiar:
        if (y, x) in wraca:
            en.append("zakryte_wraca")
        elif serce:
            en.append("serce")
        elif napis and y in WIERSZE_NAPISU:
            en.append("napis")
        elif (y, x) in cleared:
            en.append("baner")
        elif (y + 1) in wiersze:
            en.append("baner_nad")
        else:
            en.append(None)
    for y, x in brak:
        if ruchy is not None and _dawny_duch(ruchy, k, y, x):
            eb.append("dawny_duch")
        elif napis and y in WIERSZE_NAPISU:
            eb.append("napis")
        elif (y, x) in klocek:
            eb.append("klocek_niepelny")
        else:
            eb.append(None)
    return en, eb


def podgrupa(r, ruchy=None, k=None):
    """-> (grupa, podgrupa) dla wpisu `ok: false` spoza `duchy_w_czyszczonych` (dla niej podgrupa = grupa).
    Nazwa całego wpisu, jeśli pasuje; inaczej rodzaje etykiet pól połączone `+` (kolejność jak w
    RODZAJE); pole bez etykiety => `niewyjasnione`, a przy >= DUZA_ROZNICA różniących się polach `niewyjasnione_duze`."""
    grupa, nadmiar, brak, _ = klasyfikuj(r)
    if grupa == "duchy_w_czyszczonych":
        return grupa, grupa
    calosc = nazwa_calosci(r)
    if calosc:
        return grupa, calosc
    en, eb = etykiety(r, ruchy, k)
    wszystkie = en + eb
    if None in wszystkie:
        return grupa, "niewyjasnione_duze" if len(wszystkie) >= DUZA_ROZNICA else "niewyjasnione"
    rodzaje = {"baner" if e in ("baner", "baner_nad") else e for e in wszystkie}
    return grupa, "+".join(e for e in RODZAJE if e in rodzaje)


def wpisy_podgrup(plik):
    """Lista słowników dla wpisów `ok: false` z pliku: grupa, podgrupa, n, plik, `dotrwal`, `tacka`, następny wpis.
    `dotrwal` = pola różnicy w `board` następnego wpisu z ruchem mają wartość z `observed` (czyli polityka podjęła
    na nich decyzję); `tacka` = tacka następnego wpisu potwierdza przyjęcie ruchu; oba None bez następnego wpisu."""
    with open(plik, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    ruchy = [r for r in rows if "move" in r and "observed" in r]
    out = []
    for k, r in enumerate(ruchy):
        if r.get("ok") is not False:
            continue
        grupa, pod = podgrupa(r, ruchy, k)
        _, nadmiar, brak, _ = klasyfikuj(r)
        w = {"grupa": grupa, "podgrupa": pod, "n": r["n"], "plik": plik, "wpis": r, "nastepny": None,
             "dotrwal": None, "tacka": None, "pola": nadmiar + brak}
        if k + 1 < len(ruchy):
            nast = ruchy[k + 1]
            w["nastepny"] = nast
            w["dotrwal"] = all(nast["board"][y][x] == r["observed"][y][x] for y, x in w["pola"])
            pieces = [Piece(s, "slot", -1) if s else None for s in r["tray"]]
            w["tacka"] = bridge.tray_consumed(pieces, r["move"]["slot"], [(s,) if s else None for s in nast["tray"]])
        out.append(w)
    return out


def wszystkie_wpisy(katalog):
    """{seria: lista wpisów podgrup} dla `katalog/s*/partia-*/chunk*_moves.jsonl`."""
    out = {}
    for seria in sorted(d for d in os.listdir(katalog) if d.startswith("s") and d[1:].isdigit()):
        out[seria] = []
        for plik in sorted(glob.glob(os.path.join(katalog, seria, "partia-*", "chunk*_moves.jsonl"))):
            out[seria] += wpisy_podgrup(plik)
    return out


def zrzut_stanu(w):
    """Ścieżka `NNN_state.png` ze stanem po ruchu wpisu `w` (n+1) w `kawalek_K` pliku `chunkK_moves.jsonl`, albo None."""
    katalog = os.path.dirname(w["plik"])
    k = os.path.basename(w["plik"]).split("_")[0][len("chunk"):]
    sciezka = os.path.join(katalog, f"kawalek_{k}", f"{w['n'] + 1:03d}_state.png")
    return sciezka if os.path.exists(sciezka) else None


def przyklady(wpisy, ile=3):
    """{(grupa, podgrupa): [(ścieżka zrzutu, n wpisu)]} — wpisy z `dotrwal`, dla których zrzut istnieje."""
    out = {}
    for ws in wpisy.values():
        for w in ws:
            if not w["dotrwal"] or w["grupa"] == "duchy_w_czyszczonych":
                continue
            z = zrzut_stanu(w)
            if z and len(out.setdefault((w["grupa"], w["podgrupa"]), [])) < ile:
                out[(w["grupa"], w["podgrupa"])].append((os.path.relpath(z, REPO_ROOT), w["n"], sorted(w["pola"])))
    return out


def tabela_podgrup(wpisy):
    """Markdown: liczba wpisów per podgrupa i seria; `dotrwal` i `tacka` w sumie."""
    serie = list(wpisy)
    licz = {}
    for seria, ws in wpisy.items():
        for w in ws:
            if w["grupa"] == "duchy_w_czyszczonych":
                continue
            c = licz.setdefault((w["grupa"], w["podgrupa"]), {s: 0 for s in serie} | {"dotrwal": 0, "tacka": 0})
            c[seria] += 1
            c["dotrwal"] += bool(w["dotrwal"])
            c["tacka"] += bool(w["tacka"])
    linie = ["| grupa | podgrupa | " + " | ".join(serie) + " | suma | dotrwal | tacka_potwierdza |",
             "|---|---|" + "---|" * (len(serie) + 3)]
    for (g, p), c in sorted(licz.items(), key=lambda t: (GRUPY.index(t[0][0]), -sum(t[1][s] for s in serie), t[0][1])):
        suma = sum(c[s] for s in serie)
        linie.append(f"| {g} | {p} | " + " | ".join(str(c[s]) for s in serie) + f" | {suma} | {c['dotrwal']} | {c['tacka']} |")
    return "\n".join(linie), licz


# --- wpływ na decyzję -----------------------------------------------------------------------------------------------


def _plansza(grid):
    b = Board()
    b.grid = [row[:] for row in grid]
    return b


def _gra(grid, tray, polityka):
    """-> (wybór (slot, x, y) albo None, czy tacka jest do ułożenia w całości, lista legalnych ruchów)."""
    board = _plansza(grid)
    pieces = [Piece(s, f"slot{i}", -1) if s else None for i, s in enumerate(tray)]
    ruchy = bridge.legal_moves(board, pieces)
    shapes = [s for s in tray if s]
    ulozenie = False
    for perm in permutations(range(len(shapes))):
        wynik, _ = tray_dfs_playable(board.grid, [shapes[i] for i in perm], 0, TRAY_BUDZET)
        if wynik:
            ulozenie = True
            break
    if not ruchy:
        return None, ulozenie, ruchy
    return tuple(polityka.act(bridge.make_game_stub(board, pieces), ruchy)), ulozenie, ruchy


def decyzja(w, polityka):
    """Dla wpisu z `dotrwal`: polityka na planszy następnego wpisu (odczyt, to widziała) i na tej samej planszy z polami
    różnicy podmienionymi na `expected` tego wpisu, z tą samą tacką. -> {rozni, odczyt_bez_ulozenia, expected_ma}."""
    nast, r = w["nastepny"], w["wpis"]
    odczyt = nast["board"]
    exp = [row[:] for row in odczyt]
    for y, x in w["pola"]:
        exp[y][x] = r["expected"][y][x]
    a, ua, _ = _gra(odczyt, nast["tray"], polityka)
    b, ub, legalne_exp = _gra(exp, nast["tray"], polityka)
    return {"rozni": a != b, "odczyt_bez_ulozenia_expected_ma": (not ua) and ub, "ulozenie_odczyt": ua, "ulozenie_exp": ub,
            "nielegalny_na_expected": a is not None and a not in legalne_exp, "odczyt_bez_ruchu": a is None}


def zbuduj_polityke(spec=None):
    import przegrana_serii
    p, blad = przegrana_serii.build_policy(spec or przegrana_serii.default_policy_spec())
    if p is None:
        raise RuntimeError(blad)
    return p


def tabela_decyzji(wpisy, polityka):
    """Markdown: per podgrupa liczby z `decyzja` na wpisach z `dotrwal` i następnym wpisem."""
    licz = {}
    for ws in wpisy.values():
        for w in ws:
            if not w["dotrwal"]:
                continue
            d = decyzja(w, polityka)
            c = licz.setdefault((w["grupa"], w["podgrupa"]), dict.fromkeys(("dotrwal", "rozni", "tylko_odczyt_bez_ulozenia", "nielegalny"), 0))
            c["dotrwal"] += 1
            c["rozni"] += d["rozni"]
            c["tylko_odczyt_bez_ulozenia"] += d["odczyt_bez_ulozenia_expected_ma"]
            c["nielegalny"] += d["nielegalny_na_expected"]
    linie = ["| grupa | podgrupa | odczyt_bledny | dotrwal | decyzja_inna | odczyt_bez_ulozenia_a_expected_ma | "
             "ruch_odczytu_nielegalny_na_expected |", "|---|---|---|---|---|---|---|"]
    for (g, p), c in sorted(licz.items(), key=lambda t: (GRUPY.index(t[0][0]), -t[1]["dotrwal"], t[0][1])):
        linie.append(f"| {g} | {p} | {odczyt_bledny(p)} | {c['dotrwal']} | {c['rozni']} | {c['tylko_odczyt_bez_ulozenia']} | {c['nielegalny']} |")
    return "\n".join(linie), licz


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("katalog", nargs="?", default=os.path.join(REPO_ROOT, "docs", "seria"))
    ap.add_argument("--out", default=None)
    ap.add_argument("--podgrupy", action="store_true", help="tabele podgrup mechanizmu (#335) zamiast tabeli grup")
    ap.add_argument("--przyklady", action="store_true", help="z --podgrupy: wypisz zrzuty stanu dla podgrup")
    ap.add_argument("--decyzje", action="store_true", help="z --podgrupy: dolicz wpływ na decyzję polityki rekordu")
    args = ap.parse_args(argv)
    if args.podgrupy:
        wpisy = wszystkie_wpisy(args.katalog)
        if args.przyklady:
            for (g, p), lista in sorted(przyklady(wpisy).items()):
                for sc, n, pola in lista:
                    print(f"{g}/{p}: {sc} n={n} pola={pola}")
            return 0
        tekst = tabela_podgrup(wpisy)[0]
        if args.decyzje:
            tekst += "\n\n" + tabela_decyzji(wpisy, zbuduj_polityke())[0]
    else:
        tekst, _ = tabela(zbierz(args.katalog))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(tekst + "\n")
    print(tekst)
    return 0


if __name__ == "__main__":
    sys.exit(main())
