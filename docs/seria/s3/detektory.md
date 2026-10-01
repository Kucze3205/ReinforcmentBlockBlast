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
