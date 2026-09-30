"""Buduje `bridge_digits_ink.npz` — wzorce cyfr HUD dla odczytu z rozdzielenia tło/tusz (#294).

Średnia płócien glifów (`bridge._hud_canvases` na masce `bridge._hud_ink_unmixed`) z zrzutów, których
wartość licznika jest znana: 13 zrzutów 01eb4dd z tabeli `tests/test_read_score_7cyfr.py` (skórka oryginalna,
cyfry 0-9) i zrzuty s1 (`docs/seria/s1/`, odczyt wzrokowy) z kolorów teal, różowej i domyślnej.
Wzorce są jednolite dla wszystkich skórek, bo apka używa tego samego kroju cyfr (sprawdza to
`tests/test_bridge_skorki.py`: każdy glif s1 leży blisko wzorca z 01eb4dd).

    python3 tools/wzorce_hud.py
"""
import os
import sys

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bridge  # noqa: E402

RUN = os.path.join(ROOT, "bridge", "runs", "01eb4dd")
S1 = os.path.join(ROOT, "docs", "seria", "s1")

ZRZUTY = {  # ścieżka względem ROOT -> widoczna wartość licznika
    **{os.path.join("bridge", "runs", "01eb4dd", f"chunk{n}_final.png"): v for n, v in {
        4: 157704, 5: 170276, 6: 202829, 7: 267874, 8: 371248, 9: 513389, 10: 684052, 11: 881444,
        12: 1124408, 13: 1399270, 16: 1887842, 17: 1916865, 18: 1967415}.items()},
    os.path.join("docs", "seria", "s1", "partia-4", "kawalek_1", "final.png"): 5499,
    os.path.join("docs", "seria", "s1", "partia-6", "kawalek_1", "final.png"): 19935,
    os.path.join("docs", "seria", "s1", "partia-2", "kawalek_1", "final.png"): 26949,
    os.path.join("docs", "seria", "s1", "partia-7", "kawalek_2", "final.png"): 42199,
}


def glify(rel, value):
    img = np.asarray(Image.open(os.path.join(ROOT, rel)).convert("RGB")).astype(float)
    x0, y0, x1, y1 = bridge.SCORE_BOX
    soft = bridge._hud_ink_unmixed(img[y0:y1, x0:x1])
    canvases = bridge._hud_canvases(soft, soft > bridge.HUD_INK_MASK)
    text = str(value)
    if canvases is None or len(canvases) != len(text):
        raise SystemExit(f"{rel}: {None if canvases is None else len(canvases)} glifów, oczekiwano {len(text)}")
    return list(zip(text, canvases))


def main():
    by = {}
    for rel, value in ZRZUTY.items():
        for d, canvas in glify(rel, value):
            by.setdefault(d, []).append(canvas)
    missing = sorted(set("0123456789") - set(by))
    if missing:
        raise SystemExit(f"brak cyfr: {missing}")
    out = {d: (np.mean(c, axis=0) * 255).round().astype(np.uint8) for d, c in by.items()}
    np.savez_compressed(os.path.join(ROOT, bridge.DIGIT_INK_TEMPLATES_FILE), **out)
    for d in sorted(by):
        print(d, len(by[d]), "glifów")


if __name__ == "__main__":
    main()
