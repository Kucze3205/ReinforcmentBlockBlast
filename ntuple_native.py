"""
Ładowanie rdzenia natywnego N-tuple (`ntuple_native.c`, #184) i jego opakowanie.

Rdzeń jest kompilowany przy pierwszym użyciu (`cc`, albo kompilator ze zmiennej
`CC`) do katalogu `.ntuple_native/` obok źródeł (w `.gitignore`), pod nazwą z
skrótu źródła — zmiana `ntuple_native.c` daje nowy plik, stary nie jest używany.
Kompilacja idzie do pliku tymczasowego i `os.replace`, więc równoległe procesy
(`benchmark.py --jobs`) nie widzą połowicznego pliku.

Brak kompilatora, nieudana kompilacja, nieudany test zgodności sumy albo
`NTUPLE_NATIVE=0` w środowisku: `available()` zwraca `False` i `ntuple.py`
liczy wszystko po staremu, w czystym Pythonie.

Zgodność bitowa z Pythonem stoi na tym, że rdzeń sumuje wagi tym samym
algorytmem co `sum()` interpretera: od 3.12 CPython sumuje floaty
kompensacyjnie (Neumaier), wcześniej zwykłym dodawaniem. Tryb jest wykrywany
próbą (`_python_sum_mode`), a po załadowaniu biblioteki `_self_check` porównuje
rdzeń z `sum()` na losowych wagach różnych rzędów wielkości — przy jakiejkolwiek
różnicy rdzeń nie jest używany.
"""
import ctypes
import hashlib
import os
import random
import subprocess
import sys
import tempfile

ENV_FLAG = "NTUPLE_NATIVE"
_HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(_HERE, "ntuple_native.c")
BUILD_DIR = os.path.join(_HERE, ".ntuple_native")
CFLAGS = ["-O2", "-shared", "-fPIC", "-fno-fast-math", "-ffp-contract=off"]

BOARD_SIZE = 8

c_u64 = ctypes.c_uint64
c_i32 = ctypes.c_int32
c_i64 = ctypes.c_int64
c_dbl = ctypes.c_double
P = ctypes.POINTER


class Ctx(ctypes.Structure):
    _fields_ = [
        ("n_patches", c_i32),
        ("sum_mode", c_i32),
        ("n_stages", c_i32),
        ("n_thresholds", c_i32),
        ("thresholds", P(c_i32)),
        ("stage_base", P(c_i64)),
        ("run_end", P(c_i32)),
        ("run_src", P(ctypes.c_uint8)),
        ("run_dst", P(ctypes.c_uint8)),
        ("run_mask", P(ctypes.c_uint32)),
        ("w_off", P(c_i64)),
        ("w", P(c_dbl)),
    ]


class State(ctypes.Structure):
    _fields_ = [
        ("bits", c_u64),
        ("gain", c_i64),
        ("score", c_dbl),
        ("used", c_i32),
        ("combo", c_i32),
        ("cc", c_i32),
        ("placed", c_i32),
        ("first", c_i32),
        ("pad", c_i32),
    ]


class Search(ctypes.Structure):
    _fields_ = [
        ("masks", P(c_u64)),
        ("hs", P(c_i32)),
        ("ws", P(c_i32)),
        ("n_slots", c_i32),
        ("present", c_i32),
        ("base", c_i32),
        ("c0", c_i32),
        ("levels", c_i32),
        ("lmax", c_i32),
        ("pp", P(c_i64)),
        ("cp_lo", P(c_i64)),
        ("cp_hi", P(c_i64)),
        ("fcb", c_i64),
        ("path_placed", c_i32),
        ("beam", c_i32),
        ("root_acts", P(ctypes.c_int8)),
        ("n_root", c_i32),
        ("error", c_i32),
    ]


_lib = None
_tried = False
_sum_mode = None


def enabled():
    """`False`, gdy `NTUPLE_NATIVE=0` — wtedy rdzeń nie jest nawet kompilowany."""
    return os.environ.get(ENV_FLAG, "1") != "0"


def _python_sum_mode():
    """1: `sum()` kompensacyjne (Neumaier, CPython >= 3.12), 0: zwykłe dodawanie."""
    probe = sum(x for x in (1e100, 1.0, -1e100))
    if probe == 1.0:
        return 1
    if probe == 0.0:
        return 0
    return None


def _compile():
    with open(SOURCE, "rb") as fh:
        src = fh.read()
    cc = os.environ.get("CC", "cc")
    tag = hashlib.sha256(src + " ".join([cc] + CFLAGS).encode()).hexdigest()[:16]
    path = os.path.join(BUILD_DIR, "ntuple_native-%s.so" % tag)
    if os.path.exists(path):
        return path
    os.makedirs(BUILD_DIR, exist_ok=True)
    fd, tmp = tempfile.mkstemp(suffix=".so", dir=BUILD_DIR)
    os.close(fd)
    try:
        subprocess.run(
            [cc] + CFLAGS + ["-o", tmp, SOURCE, "-lm"],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        )
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    return path


def _bind(lib):
    ctx_p = P(Ctx)
    lib.nt_value_bits.argtypes = [ctx_p, c_u64]
    lib.nt_value_bits.restype = c_dbl
    lib.nt_indices.argtypes = [ctx_p, c_u64, P(c_i32)]
    lib.nt_indices.restype = None
    lib.nt_value_idx.argtypes = [ctx_p, P(c_i32), c_i32]
    lib.nt_value_idx.restype = c_dbl
    lib.nt_update.argtypes = [ctx_p, P(c_i32), c_dbl, c_i32]
    lib.nt_update.restype = None
    lib.nt_afterstates.argtypes = [
        ctx_p, c_u64, P(c_u64), P(c_i32), P(c_i32), ctypes.c_int, P(ctypes.c_int8), ctypes.c_int,
        ctypes.c_int, c_dbl, P(c_dbl), P(c_i32), P(ctypes.c_int8), P(c_i32), P(c_i32),
    ]
    lib.nt_afterstates.restype = ctypes.c_int
    lib.nt_afterstate_indices.argtypes = [
        ctx_p, c_u64, c_u64, ctypes.c_int, ctypes.c_int, P(c_i32), P(c_i32),
    ]
    lib.nt_afterstate_indices.restype = None
    lib.nt_search.argtypes = [
        ctx_p, P(Search), c_u64, c_i32, c_i32, P(State), ctypes.c_int, P(c_i64), P(c_i32),
    ]
    lib.nt_search.restype = ctypes.c_int


def library():
    """Załadowana biblioteka rdzenia albo `None` (zapasowa ścieżka: czysty Python)."""
    global _lib, _tried, _sum_mode
    if not enabled():
        return None
    if _tried:
        return _lib
    _tried = True
    mode = _python_sum_mode()
    if mode is None:
        return None
    try:
        lib = ctypes.CDLL(_compile())
        _bind(lib)
    except (OSError, subprocess.CalledProcessError, AttributeError) as exc:
        print("ntuple_native: rdzen niedostepny (%s), licze w Pythonie" % exc, file=sys.stderr)
        return None
    _sum_mode = mode
    _lib = lib
    if not _self_check():
        print("ntuple_native: rdzen niezgodny z sum() Pythona, licze w Pythonie", file=sys.stderr)
        _lib = None
    return _lib


def available():
    return library() is not None


def _self_check():
    """Rdzeń vs `sum()` na losowym układzie i wagach o skrajnie różnych rzędach wielkości."""
    rng = random.Random(184)
    layout = tuple(
        tuple(rng.sample(range(64), rng.randint(1, 9))) for _ in range(60)
    )
    weights = [
        [rng.choice((1.0, -1.0)) * rng.random() * 10.0 ** rng.randint(-20, 20)
         for _ in range(1 << len(positions))]
        for positions in layout
    ]
    core = Core(layout, [weights])
    for _ in range(300):
        bits = rng.getrandbits(64)
        idx = [
            sum(((bits >> pos) & 1) << i for i, pos in enumerate(positions))
            for positions in layout
        ]
        expected = sum(table[i] for table, i in zip(weights, idx))
        if core.value_bits(bits) != expected or core.indices_list(bits) != idx:
            return False
    return True


def _runs(positions):
    """Łata jako ciągłe przebiegi `(bit planszy, bit indeksu, długość)`: kolejne
    pozycje łaty leżące na kolejnych bitach planszy czyta jedno przesunięcie."""
    runs = []
    for i, pos in enumerate(positions):
        if runs:
            src, dst, length = runs[-1]
            if pos == src + length and i == dst + length:
                runs[-1] = (src, dst, length + 1)
                continue
        runs.append((pos, i, 1))
    return runs


def piece_geometry(piece):
    """`(maska w lewym-górnym rogu, wysokość, szerokość)` klocka jak widzi go
    `Board.can_place_piece`, albo `None`, gdy kształt wykracza poza `shape[0]`
    (poszarpany) — wtedy rdzeń nie liczy tej decyzji."""
    shape = piece.shape
    h, w = len(shape), len(shape[0])
    if h > BOARD_SIZE or w > BOARD_SIZE:
        return None
    mask = 0
    for dy, row in enumerate(shape):
        for dx, cell in enumerate(row):
            if cell:
                if dx >= w:
                    return None
                mask |= 1 << (dy * BOARD_SIZE + dx)
    return mask, h, w


class Core:
    """Wagi jednej `NTupleValue` (wszystkich jej etapów, #203) w buforze C i
    operacje rdzenia na nich.

    Bufor wag jest kopią list z `NTupleValue._stage_weights` — jedna lista na
    etap, każda w dawnym kształcie (lista tablic po łatach); `push`/`pull`
    przenoszą wartości w obie strony bez żadnej konwersji (float Pythona to
    `double`). `thresholds` ma `len(stage_weights) - 1` progów rosnąco;
    domyślne `()` z jednym etapem liczy bitowo jak przed #203."""

    def __init__(self, layout, stage_weights, thresholds=()):
        lib = _lib
        self.lib = lib
        self.n_patches = len(layout)
        self.n_stages = len(stage_weights)
        self.thresholds = tuple(thresholds)
        runs = [_runs(p) for p in layout]
        n_runs = sum(len(r) for r in runs)
        self._run_end = (c_i32 * self.n_patches)()
        self._run_src = (ctypes.c_uint8 * max(n_runs, 1))()
        self._run_dst = (ctypes.c_uint8 * max(n_runs, 1))()
        self._run_mask = (ctypes.c_uint32 * max(n_runs, 1))()
        k = 0
        for p, patch_runs in enumerate(runs):
            for src, dst, length in patch_runs:
                self._run_src[k] = src
                self._run_dst[k] = dst
                self._run_mask[k] = (1 << length) - 1
                k += 1
            self._run_end[p] = k
        self.sizes = [1 << len(p) for p in layout]
        self.offsets = []
        off = 0
        for size in self.sizes:
            self.offsets.append(off)
            off += size
        self.stage_size = off
        self._w_off = (c_i64 * self.n_patches)(*self.offsets)
        self._stage_base = (c_i64 * self.n_stages)(*(s * off for s in range(self.n_stages)))
        self._thresholds = (c_i32 * max(len(self.thresholds), 1))(*self.thresholds)
        self.w = (c_dbl * max(self.n_stages * off, 1))()
        self.ctx = Ctx(
            self.n_patches, _sum_mode, self.n_stages, len(self.thresholds), self._thresholds,
            self._stage_base, self._run_end, self._run_src, self._run_dst,
            self._run_mask, self._w_off, self.w,
        )
        self.ctx_ref = ctypes.byref(self.ctx)
        self.IdxArray = c_i32 * self.n_patches
        self.push(stage_weights)
        # Bufory wielokrotnego użytku na decyzję treningu (do 3 slotów tacki i
        # 3*64 akcji na slot to z zapasem więcej, niż daje plansza 8x8).
        self._masks = (c_u64 * 8)()
        self._hs = (c_i32 * 8)()
        self._ws = (c_i32 * 8)()
        self._cap = 0
        self._ensure_actions(256)

    # -- wagi --------------------------------------------------------------

    def push(self, stage_weights):
        """Listy (po jednej na etap) -> bufor. `False`, gdy liczba etapów albo
        kształt tablic się nie zgadza, albo waga nie jest dokładnie `float`
        (`sum()` traktuje int inaczej niż float) — wtedy rdzeń nie może liczyć
        tych wag bitowo tak samo."""
        if len(stage_weights) != self.n_stages:
            return False
        for weights in stage_weights:
            if len(weights) != self.n_patches:
                return False
            for table, size in zip(weights, self.sizes):
                if len(table) != size or not all(type(v) is float for v in table):
                    return False
        for s, weights in enumerate(stage_weights):
            base = s * self.stage_size
            for table, size, off in zip(weights, self.sizes, self.offsets):
                self.w[base + off:base + off + size] = table
        return True

    def pull(self, stage_weights):
        """Bufor -> listy, w miejscu (te same obiekty list, nowe wartości)."""
        for s, weights in enumerate(stage_weights):
            base = s * self.stage_size
            for table, size, off in zip(weights, self.sizes, self.offsets):
                table[:] = self.w[base + off:base + off + size]

    # -- ocena i aktualizacja ---------------------------------------------

    def value_bits(self, bits):
        return self.lib.nt_value_bits(self.ctx_ref, bits)

    def indices_list(self, bits):
        out = self.IdxArray()
        self.lib.nt_indices(self.ctx_ref, bits, out)
        return list(out)

    def as_idx(self, idxs):
        """Indeksy łat jako tablica C: przepuszcza `IdxArray`, listę sprawdza jak
        zrobiłby to odczyt `table[i]` w Pythonie (ujemne od końca, poza — błąd)."""
        if isinstance(idxs, self.IdxArray):
            return idxs
        idxs = list(idxs)
        if len(idxs) < self.n_patches:
            # zip() w Pythonie ucina do krótszego — tu nie ma odpowiednika.
            return None
        out = self.IdxArray()
        for p, (i, size) in enumerate(zip(idxs, self.sizes)):
            if -size <= i < 0:
                i += size
            elif not 0 <= i < size:
                raise IndexError("list index out of range")
            out[p] = i
        return out

    def value_idx(self, idx, stage=0):
        return self.lib.nt_value_idx(self.ctx_ref, idx, stage)

    def update(self, idx, delta, stage=0):
        self.lib.nt_update(self.ctx_ref, idx, delta, stage)

    # -- stany następcze (trening) ------------------------------------------

    def _ensure_actions(self, n):
        if n <= self._cap:
            return
        self._cap = max(n, 2 * self._cap)
        self._acts = (ctypes.c_int8 * (3 * self._cap))()
        self._vals = (c_dbl * self._cap)()
        self._lines = (c_i32 * self._cap)()
        self._empty = (ctypes.c_int8 * self._cap)()

    def set_tray(self, pieces):
        """Geometria klocków tacki w buforach rdzenia; `False`, gdy nieobsługiwana."""
        if len(pieces) > 8:
            return False
        for s, piece in enumerate(pieces):
            if piece is None:
                self._masks[s] = 0
                self._hs[s] = BOARD_SIZE + 1
                self._ws[s] = BOARD_SIZE + 1
                continue
            geom = piece_geometry(piece)
            if geom is None:
                return False
            self._masks[s], self._hs[s], self._ws[s] = geom
        self._n_slots = len(pieces)
        return True

    def afterstates(self, bits, actions, r_const=None):
        """Wartości stanów następczych akcji `actions` na tacce z `set_tray`.

        Z `r_const` zwraca `(numer najlepszej akcji wg r_const + V, jej indeksy
        łat, jej etap #203)`; bez — `(wartości, linie, czy_pusta)` jako tablice C
        (wartości już liczone z etapu każdego stanu z osobna). `None`, gdy
        któraś akcja jest nielegalna."""
        n = len(actions)
        self._ensure_actions(n)
        acts = self._acts
        k = 0
        for a in actions:
            acts[k], acts[k + 1], acts[k + 2] = a
            k += 3
        if r_const is not None:
            best_idx = self.IdxArray()
            best_stage = c_i32()
            best = self.lib.nt_afterstates(
                self.ctx_ref, bits, self._masks, self._hs, self._ws, self._n_slots, acts, n,
                1, r_const, self._vals, self._lines, self._empty, best_idx, ctypes.byref(best_stage),
            )
            if best < 0:
                return None
            return best, best_idx, best_stage.value
        res = self.lib.nt_afterstates(
            self.ctx_ref, bits, self._masks, self._hs, self._ws, self._n_slots, acts, n,
            0, 0.0, self._vals, self._lines, self._empty, None, None,
        )
        if res < 0:
            return None
        return self._vals, self._lines, self._empty

    def afterstate_indices(self, bits, action):
        """Indeksy łat i etap (#203) stanu następczego jednej akcji."""
        s, x, y = action
        out = self.IdxArray()
        stage = c_i32()
        self.lib.nt_afterstate_indices(self.ctx_ref, bits, self._masks[s], x, y, out, ctypes.byref(stage))
        return out, stage.value

    # -- przeszukanie wiązką (lookahead-ntuple) -----------------------------

    def search(self, bits, geoms, present, combo, combo_counter, base, levels, lmax,
               pp, cp_lo, cp_hi, fcb, path_placed, beam, root_actions):
        """Przeszukanie wiązką w rdzeniu; `(lista State, expanded)` albo `None`
        (akcja korzenia nielegalna, tabela punktów za wąska — licz po staremu)."""
        n_slots = len(geoms)
        masks = (c_u64 * n_slots)(*(g[0] for g in geoms))
        hs = (c_i32 * n_slots)(*(g[1] for g in geoms))
        ws = (c_i32 * n_slots)(*(g[2] for g in geoms))
        if root_actions is None:
            roots, n_root = None, -1
        else:
            n_root = len(root_actions)
            roots = (ctypes.c_int8 * max(3 * n_root, 1))()
            k = 0
            for a in root_actions:
                roots[k], roots[k + 1], roots[k + 2] = a
                k += 3
        S = Search(
            masks, hs, ws, n_slots, present, base, combo, levels, lmax,
            (c_i64 * n_slots)(*pp), (c_i64 * len(cp_lo))(*cp_lo), (c_i64 * len(cp_hi))(*cp_hi),
            fcb, 1 if path_placed else 0, beam, roots, n_root, 0,
        )
        cap = max(1, min(beam, 64))
        expanded = c_i64()
        need = c_i32()
        while True:
            out = (State * cap)()
            n = self.lib.nt_search(
                self.ctx_ref, ctypes.byref(S), bits, combo, combo_counter, out, cap,
                ctypes.byref(expanded), ctypes.byref(need),
            )
            if n == -2:
                cap = need.value
                continue
            if n < 0:
                return None
            return out[:n], expanded.value
