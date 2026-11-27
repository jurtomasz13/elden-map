# Ekstraktor zasobów Elden Ring

Wyciąga z twojej instalacji gry (tylko do odczytu) prawdziwą mapę świata, ikony przedmiotów, ekrany ładowania
i dane (przedmioty, łaski, wizerunki bossów) z polskimi nazwami z gry. Niczego nie pobiera z internetu: klucze RSA
są w `eldenring.exe`, dekompresję robi `oo2core_6_win64.dll` z folderu gry, a AES Windows CNG (`bcrypt.dll`).

```powershell
python tools/extract/run_all.py
```

Wymaga Pythona 3.14+ (moduł `compression.zstd`) i Node 18+. Pełny przebieg trwa ok. 2–3 min. Pierwszy raz trwa
dłużej, bo trzeba odszyfrować nagłówki archiwów (cache w `assets/cache`).

Ścieżka gry jest w `bhd.py` (`GAME_DIR`).

## Wynik (`assets/`, poza repozytorium)

| Ścieżka | Co |
|---|---|
| `assets/map/M00/{z}/{x}/{y}.png` | Ziemie Pomiędzy: piramida kafli 256 px, zoom 0–6 (L0 = 10496 px) |
| `assets/map/M10/...` | Królestwo Cienia (DLC) |
| `assets/map/M01/...`, `M11/...` | mapy podziemi (bazowa gra / DLC) |
| `assets/map/meta.json` | rozmiary i zakres zoomu |
| `assets/icons/<iconId>.png` | 2499 ikon przedmiotów, 256 px, przezroczyste tło |
| `assets/loading/<n>.png` | 35 grafik z ekranów ładowania (1280 px) |
| `assets/data/items.json` | 3648 przedmiotów: kategoria, rodzaj (`kind`, ta sama reguła co dla skarbów na mapie), id, nazwa PL/EN, iconId, DLC; ten sam przedmiot pod kilkoma numerami to jeden wpis z `alt_ids`; przedmioty moda Seamless Coop (8380001–8380012, `kind: seamless`), gdy mod jest w folderze gry |
| `assets/data/bosses.json` | wizerunki (remembrances) bossów → iconId |
| `assets/data/graces.json` | 422 łaski: flaga, nazwa, kraina, pozycja, piksele na mapie |
| `assets/data/map_transform.json` | przeliczenie współrzędnych gry → piksele mapy |

## Pliki

| Plik | Rola |
|---|---|
| `bhd.py` | klucze RSA z exe, odszyfrowanie nagłówków BHD5 |
| `archive.py` | spis plików BHD5, hash ścieżek, AES, DCX (KRAK/ZSTD/DFLT) |
| `formats.py` | BND4, BXF4, TPF, FMG |
| `params.py` | `regulation.bin` (AES-256-CBC + ZSTD) i teksty |
| `dds.mjs` | dekoder BC1/3/4/5/7 → PNG (bez zależności) |
| `extract_map.py` + `build_tiles.mjs` | kafle mapy w wariancie „pełna mapa” → piramida |
| `extract_map_pieces.py` + `build_map_pieces.mjs` | zasięg fragmentów mapy (maska) i flagi, żeby mapa odkrywała się jak w grze |
| `extract_icons.py` + `build_icons.mjs` | ikony przedmiotów, ikony miejsc na mapie, ekrany ładowania, spis przedmiotów |
| `extract_data.py` | łaski + przeliczenie współrzędnych |
| `overlay_test.mjs`, `fit_offset.mjs` | narzędzia do weryfikacji/kalibracji przeliczenia |
| `msb.py` + `extract_world.py` | pliki map i skrypty zdarzeń: wszyscy bossowie, miejsca/lochy, przedmioty na mapie, NPC ([docs/10](../../docs/10-world-data.md)) |
| `flver.py` + `export_model.py` + `render.mjs` | modele 3D (FLVER2 z `chrbnd`, tekstury z `texbnd`, albedo z MATBIN) → programowy render PNG z przezroczystym tłem; `node render.mjs <katalog> <out.png> [rozmiar] [obrót] [full\|bust]` |
| `render_portraits.py` | portrety bossów bez ikony i postaci (NPC) → `assets/renders/<model>.png` / `npc_<CharaInit>.png` + pole `render` w `bosses_all.json` i `npcs.json` |
| `render_character.py` | portret głowy postaci gracza (twarz, włosy, kolory z save'a + hełm) → `assets/renders/char_<plik>_<slot>.png`; wymaga działającego backendu |
| `extract_curves.py` | krzywe statystyk (CalcCorrectGraph) → `stat_curves.json`, z nich miękkie progi atrybutów |
| `extract_damage.py` | dane do liczenia siły ataku broni gracza (EquipParamWeapon, ReinforceParamWeapon, AttackElementCorrectParam, krzywe) → `weapon_calc.json` |
| `extract_sources.py` | skąd zdobyć przedmioty: kupcy (ShopLineupParam + skrypty rozmów), łup z przeciwników, zdarzenia, bossowie → `item_sources.json`; sklep i usługi każdej postaci → `talks.json` |
| `extract_warps.py` | teleporty ze skryptów zdarzeń (bramy, skrzynie-pułapki, przejścia) → `warps.json` |
| `extract_landmarks.py` | posągi Wielkich run przy Boskich Wieżach (`restore`) i Wędrowne Mauzolea → dopisane do `pois.json` |
| `extract_summons.py` | znaki przywołania postaci ze skryptów zdarzeń → `summons.json` |
| `quest_spoilers.py` | wersje kroków questów bez spoilerów (stosowane też w `build_quests.py`) |
| `contact_sheet.mjs` | podgląd: kilka PNG w jednej siatce |
| `build_quests.py` | questy NPC (`assets/data/quests.json`); `--verify` sprawdza flagi na postaciach przez backend ([docs/09](../../docs/09-quests.md)). Działa osobno od `run_all.py`, bo korzysta z pobranych danych społeczności |

Formaty i ustalenia opisuje [docs/08-assets.md](../../docs/08-assets.md).
