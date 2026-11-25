# 03 — Format pliku save (`ER0000.sl2` / `ER0000.co2`)

Wszystko poniżej **zweryfikowane** na Twoich save'ach z 2026-11-23 (6 postaci w `.sl2`
i 6 w `.co2`) skryptem [scripts/er_save_probe.py](scripts/er_save_probe.py).

## Kontener

- Plik **nie jest zaszyfrowany** (inaczej niż w Dark Souls 3). Kontener `BND4`.
- 12 wpisów, każdy zaczyna się od 16 bajtów **MD5 z reszty wpisu** (wszystkie sumy się zgadzają —
  przy zapisie trzeba by je przeliczyć, ale my tylko czytamy).

| Wpis | Offset w pliku | Rozmiar | Zawartość |
|---|---|---|---|
| `USER_DATA000`…`009` | `0x300 + i * 0x280010` | `0x280010` | 10 slotów postaci |
| `USER_DATA010` | `0x19003A0` | `0x60010` | profil: SteamID, aktywne sloty, podsumowania postaci |
| `USER_DATA011` | `0x19603B0` | `0x240020` | (nie badane — prawdopodobnie regulation/inne) |

Nagłówek wpisu BND4 (0x20 bajtów, od `0x40`): `+0x08` u64 rozmiar, `+0x10` u32 offset danych,
`+0x14` u32 offset nazwy (UTF-16).

## `USER_DATA010` — profil (offsety od początku danych, po MD5)

| Offset | Co |
|---|---|
| `+0x04` | u64 SteamID |
| `+0x1954` | `bool[10]` — które sloty są zajęte |
| `+0x195E + i*0x24C` | podsumowanie postaci `i` (0x24C B): `+0x00` imię UTF-16 (0x20 B + 2 B terminator), `+0x22` u32 poziom, `+0x26` u32 czas gry w sekundach, `+0x2A` u32 pamięć run, `+0x2E` u32 MapID, `+0x32` u32 PlaceName ID (nazwa miejsca z ekranu ładowania), `+0x36` wygląd twarzy (0x124), `+0x15A` ekwipunek (0xE8), `+0x242` typ ciała, `+0x243` klasa, `+0x244` dar startowy. ✅ zweryfikowane (np. grandes: 71,1 h; finali: 219,1 h) |

## Slot postaci (offsety od początku danych slotu, po MD5)

| Offset | Co | Pewność |
|---|---|---|
| `+0x00` | u32 wersja slotu (np. 100, 151, 220, 262 — rośnie z patchami) | ✅ |
| `+0x04` | MapID ostatniego zapisu, 4 bajty `[DD, CC, BB, AA]` → `mAA_BB_CC_DD` (np. `m60_46_39_..`, `m11_00_00_00` = Leyndell) | ✅ |
| `+0x20` | **GaItem map** — 0x1400 wpisów (0x13FE gdy wersja ≤ 81), zmienna długość: `u32 handle, u32 item_id`, + 13 B gdy `handle & 0xF0000000 == 0x80000000` (broń), + 8 B gdy `== 0x90000000` (zbroja) | ✅ |
| koniec GaItem | **PlayerGameData** (0x1B0 B), imię UTF-16 na `+0x94` | ✅ |
| … | ekwipunek, magia, wygląd, skrzynia… (stały rozmiar) | nie badane |
| `R` | **lista odblokowanych regionów**: `u32 count`, `count × u32 region_id` (np. 1001001, 1800090, 600000…) — zmienna długość | ✅ |
| `R + 4 + 4*count` | `RideGameData` (Torrent: pozycja float XYZ…) — od tego miejsca stały rozmiar aż do flag | ✅ |
| `flagi − 0x1A` | preambuła: u32 **liczba śmierci**, i32 typ postaci, u8 sesja online, u32 typ postaci online, u32 **ostatnia łaska** (`bonfireEntityId + 1000` z BonfireWarpParam), u8 not_alone, u32 licznik czasu, u32 random_appear_lot_slot | ✅ (Ser Davick: 8 śmierci; finali: 744) |
| **`koniec_regionów + 0x1CA5E`** | **blok flag zdarzeń, `0x1BF99F` bajtów** (= 14 667 bloków × 125 B) | ✅ |
| koniec flag | bajt `0x00` (terminator), potem 5 bloków `i32 size + dane`: field_area, world_area (`CHR `), world_geom_man (`MOEG`), world_geom_man2 (`FOEG`), rend_man | ✅ |
| po rend_man | **PlayerCoordinates** (0x3D B): `float[3]` pozycja, `+0x0C` MapID, `+0x10` `float[4]` obrót, `+0x21` pozycja zapisana w multi | ✅ |

Pełna kolejność pól (wg [dokumentacji er-save-manager](https://elden-ring-save-manager.readthedocs.io/en/main/technical/save-file-structure/)):
`version, map_id, play_time_ms(u64), unk(16), gaitem_map*, player_game_data(0x1B0), sp_effects, equip…,
inventory_held(0x9010), …, acquired_projectiles*, …, face_data(0x12F), storage_box(0x6010), gestures(0x100),
unlocked_regions*, horse(0x28), has_bloodstain(1), blood_stain(0x44), clear_count(4), unk(4),
menu_profile_save_load*, trophy_equip_data(0x34), gaitem_game_data(0x1B588), tutorial_data*, 3×u8,
[preambuła wyżej], event_flags(0x1BF99F), terminator(1), 5×lista*, player_coordinates(0x3D), …, steam_id, dlc(0x32), …`
(`*` = zmienna długość). Między regionami a flagami są pola o zmiennej długości (menu, tutorial),
ale na Twoich save'ach odległość wynosi stałe `0x1CA5E`.

**Szukanie listy regionów: parsowanie po kolei (od 2026-11-23).** Pierwsza wersja szukała listy
heurystycznie i nie działała dla nowej postaci, która ma 1 region. Teraz:
`koniec GaItem + 0x94CC` → `u32 count` pocisków (acquired_projectiles, `count × 8` bajtów) →
`+ 0x62E7` → lista regionów. Na 7 postaciach daje dokładnie te same pozycje co heurystyka.

### Pozycja gracza → współrzędne globalne

Na mapach świata otwartego (`m60` = Ziemie Pomiędzy, `m61` = DLC) pozycja jest **lokalna względem
kafla** `mAA_XX_ZZ_00`. Wg dokumentacji er-save-manager: `globalna = kafel * 256 + 128 + lokalna`
(dla osi X i Z; ⚠️ niezweryfikowane). Na Twoich postaciach: grandes `(-73.4, 86.8, 40.2)` na
`m60_46_39`, boink `(-19.4, 386.2, 3.3)` na `m61_49_43`.

### Jak potwierdziłem offset flag (dwie niezależne drogi)

1. **Od końca:** we wszystkich slotach na pozycji `koniec_regionów + 0x1DC3FD` jest bajt `0x00`,
   a po nim `u32` = 0x04 / 0x10 / 0x14 / 0x18, i dokładnie o tyle przesuwa się znacznik `CHR `
   w danym slocie. `0x1DC3FD − 0x1BF99F = 0x1CA5E`.
2. **Od tabeli CE:** offsety flag z CT nałożone na ten blok dają sensowne wyniki:

| Grupa flag (CT) | grandes (148) | boink (180) | prophet (176) | finali (221) | Mokki (152) | Ser Davick (13) |
|---|---|---|---|---|---|---|
| Łaski DLC | 0/105 | 32/105 | 0/105 | **104/105** | 0/105 | 0/105 |
| Osełki (Whetblades) | 9/13 | 13/13 | 11/13 | 13/13 | 11/13 | 1/13 |
| Ashes of War | 35/116 | 73/116 | 77/116 | 110/116 | 23/116 | **0/116** |
| Bossowie (głównie DLC) | 1/354 | 42/354 | 2/354 | 136/354 | 2/354 | 3/354 |

Postać na 13 poziomie nie ma prawie nic, postać na 221 ma prawie całe DLC → offsety pasują.

## Wnioski dla projektu

- Z save'a mamy **ten sam blok flag co w pamięci** → jedna logika „co jest zaliczone”.
- Odczyt: znajdź listę regionów (heurystyka w skrypcie), dodaj `0x1CA5E`, czytaj `0x1BF99F` bajtów.
- Lista regionów sama w sobie to gotowa warstwa mapy („odkryte obszary”).
- Seamless Coop (`.co2`) ma identyczny format.
