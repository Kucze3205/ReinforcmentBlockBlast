# Detektory okien na żywej planszy (#311)

`python3 tools/detektory_na_planszy.py [--lista]` — klatki `NNN_state.png` z s1, s2, s3, po których most wykonał ruch
(wpis `move` w `chunkK_moves.jsonl`), trafienia każdego `is_*_screen`. Każde trafienie to fałszywe okno.

Przed (liczby trafień; klatek: s1 512, s2 182, s3 12): `is_home_screen` 123/24/0, `is_splash_screen` 19/0/0, reszta 0.
Po: wszystkie liczniki 0.

Przyczyny:
- `is_splash_screen`: czerwone i fioletowe klocki w wierszach 0–1 planszy w `SPLASH_LOGO_BOX` (np. s3 partia-1 `final.png`:
  0.049/0.037). Dodano warunek: pod logo (`SPLASH_FLAT_BOX`) czysty gradient — odchyłka 4 na 4 prawdziwych ekranach startowych,
  najmniej 74 na klatkach planszy (próg 20).
- `is_home_screen`: jasne niebo skórki daje w pasku stanu ~1.0 białych pikseli (prawdziwy launcher 0.076). Dodano górny próg 0.5.

Uwaga: klatek s3 z ruchem jest tylko 12 (zrzuty zapisywane rzadko); trzy partie z kryteriów sprawdza test wprost.

## Cykl 47 (#314)

Klatek z ruchem: s1 512, s2 182, s3 61 (doszły partie 4, 6, 8). Trafienia wszystkich `is_*_screen`: 0/0/0.
Partia 8 `kawalek_3` (fałszywy `ekran_startowy` od `n=9`, grała na `a5cd123`, bez #311): wszystkie klatki
`000–009_state.png` dają `is_splash_screen` = `is_home_screen` = `False`, w tym 009. Klatka 009 nie ma ruchu, więc
pilnuje jej test `test_live_board_s3_partia8_is_not_splash_nor_home`. `bridge.py` bez zmian.

## Cykl 49 (#321)

Klatek z ruchem: s1 512, s2 182, s3 258, s4 187 (`SERIE` w `tools/detektory_na_planszy.py` obejmuje teraz s4). Trafienia
wszystkich `is_*_screen`: 0/0/0/0. Jedyne trafienie (`is_ad_screen` na s4 partia-4 `067_state.png`) to prawdziwa reklama
wideo po ruchu (następny wpis `reklama_wideo`); narzędzie pomija klatki, po których następny wpis to `reklama_*`.
Koło fortuny z X (s4 p.4 `068_state.png`, `final.png`; p.6 `final.png`): `is_interactive_ad_screen` = True, `bridge.py`
bez zmian; `INTERACTIVE_AD_CLOSE` leży na kółku X (s4) i na >> (s3). Test: `tests/test_bridge_reklama_interaktywna.py`.
