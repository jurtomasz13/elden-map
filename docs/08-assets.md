# Zasoby z plików gry (mapa, ikony, dane)

Narzędzie: [tools/extract](../tools/extract/README.md), uruchomienie: `python tools/extract/run_all.py`.
Wszystko pochodzi z lokalnej instalacji gry użytkownika (wersja pliku 2.7.2.0, z DLC), tylko odczyt.
Wyniki w `assets/` są w `.gitignore`: to grafiki FromSoftware, nie publikujemy ich.

## Łańcuch odczytu

1. Klucze RSA: 5 bloków `-----BEGIN RSA PUBLIC KEY-----` (PKCS#1) w `eldenring.exe`, po jednym
   na archiwum `Data0–3` i `DLC`. Który klucz pasuje, sprawdzamy po magii `BHD5` po odszyfrowaniu.
2. Nagłówek BHD5: surowe RSA (`pow(c, e, n)`) blokami po 256 B, wynik 255 B na blok.
   Cache odszyfrowanych nagłówków: `assets/cache/*.bhd5`.
3. Spis plików: kubełki → wpisy po 40 B: `u64 hash, i32 rozmiar_z_paddingiem, i32 rozmiar,
   i64 offset_w_BDT, i64 offset_SHA, i64 offset_klucza_AES`. Około 120 tys. plików.
4. Hash ścieżki: 64-bit, `h = h * 0x85 + znak`, małe litery, `/` na początku.
   Np. `/menu/71_maptile.tpfbdt`, `/menu/low/00_solo.tpfbhd`, `/msg/polpl/item.msgbnd.dcx`.
5. AES: klucz 16 B + lista zakresów `[start, end)` w BDT, AES-128-ECB tylko na tych zakresach
   (Windows CNG `bcrypt.dll` przez ctypes).
6. DCX: `KRAK` (Oodle Kraken, `oo2core_6_win64.dll` z folderu gry), `ZSTD` (Python 3.14
   `compression.zstd`), `DFLT` (zlib).
7. Kontenery: BND4, BXF4 (nagłówek `.tpfbhd` + dane `.tpfbdt`), TPF (tekstury DDS),
   FMG v2 (teksty). Uwaga: bajt formatu bindera bywa zapisany z odwróconą kolejnością bitów, więc
   parser próbuje obu wariantów i wybiera ten, w którym offsety mieszczą się w danych.
8. Tekstury: DDS w BC7 (`DXGI 98`), mapy 256×256, ikony 512×512 (`/menu/low`) lub 1024×1024
   (`/menu/hi`). Dekoder BC7 napisany od zera w JS (`dds.mjs`), z kontrolą spójności tablic podziału.

## Mapa świata

- Plik: `/menu/71_maptile.tpfbhd/.tpfbdt` (Data0), 28 469 kafli
  `MENU_MapTile_M<mapa>_L<poziom>_<x>_<y>_<bity>`.
- Mapy: `M00` Ziemie Pomiędzy, `M01` podziemia, `M10` Królestwo Cienia (DLC), `M11` podziemia DLC.
- Poziomy: L0 41×41 kafli (10 496 px), L1 31×31, L2 11×11, L3 6×6, L4 3×3. Używamy L0 i sami
  robimy piramidę zoom 0–6 (zoom 6 = L0).
- Oś Y kafli rośnie w górę (północ): przy składaniu odwracamy.
- Bity wariantu = zebrane fragmenty mapy. `00000000` to pusty pergamin. Pełna mapa to maska
  z `/menu/71_maptile.mtmskbnd.dcx` (XML, `id = poziom*10000 + x*100 + y`, `mask = ...`).
  Wybieramy wariant równy masce albo jej największy podzbiór. Bez tego wychodzą zdublowane
  i testowe (deweloperskie) kafle.
- Mapa odkryta jak w grze (tryb „Mój postęp”): bit `i` wariantu = `i`-ty wiersz `WorldMapPieceParam`
  danej mapy (M00: wiersze 0–69, M01: 100–199, M10: 1000–1069), flaga zebrania pod `+0x04`
  (62010–62053, 62004–62009 morze, 62060–62065 podziemia, 62080–62084 DLC).
  `extract_map_pieces.py` zapisuje dla każdego kafla i bitu parę wariantów różniących się tylko tym bitem,
  `build_map_pieces.mjs` porównuje je (bloki 8×8 px) i składa `assets/map/<M>/pieces.png` (1312 px; kanały
  R,G,B = bity 0–23) oraz `assets/map/blank.png` (pusta faktura). Strona zakrywa tą fakturą (CSS `mask-image`)
  miejsca, których nie odsłania żaden zebrany fragment. Flagi: `assets/data/map_pieces.json`.
- Obszar mapy (jak w grze: dalej nie da się przesunąć ani oddalić): `+0x08` 4×f32 [lewo, prawo, góra, dół]
  w pikselach mapy, suma prostokątów otwartych fragmentów + okolice miejsc, w których byłeś (łaski, zebrane
  przedmioty, pokonani bossowie, śmierci, pozycja). Wiersze 70 / 1070 (flagi 62000 / 62002) to obszar startowy
  gry i DLC. 62002 ustawia się po wejściu do DLC, więc wtedy pojawia się mapa Królestwa Cieni. Podziemia nie
  mają obszaru startowego, mapa pojawia się po pierwszej łasce lub wizycie. `+0x18` (63xxx) w save'ach nigdy
  nie jest ustawiona, więc ją pomijamy. Sprawdzone na żywo (podstawione zapisy): fragment, nowa łaska w Caelid,
  pierwsza łaska w podziemiach i wejście do DLC aktualizują mapę bez przeładowania strony.

## Przeliczenie współrzędnych gry → piksele mapy

```
px = gx*256 + x + 128 - OX        (piksele L0, 0..10496, od lewej)
py = 10496 - (gz*256 + z + 128 - OZ)   (od góry)
```
`gx/gz` = komórka siatki `m60_gx_gz_00` / `m61_...`, `x/z` = pozycja lokalna (jak w save:
PlayerCoordinates + MapID, patrz [03](03-format-save.md)). Skala 1 px = 1 m.

| Mapa | area | OX | OZ |
|---|---|---|---|
| M00 Ziemie Pomiędzy | 60 | 7168 | 6144 |
| M10 Królestwo Cienia | 61 | 7168 | 6144 |

Jeden wzór dla obu map (2026-11-25): kafle L0 mapy pokrywają się 1:1 z komórkami siatki świata,
OX = 28·256, OZ = 24·256 dla m60 i m61. Sprawdzone w pełnym przybliżeniu na wyraźnych budowlach:
w podstawce most do Boskiej Wieży Pogrobna, Burzowa Brama, Kościół Elleha; w DLC Fort Napomnienia,
Katedra Manusa Metyra, Wieża Rabbatha, Kościół Błogosławieństwa, ruiny Unte, Kościół Pąka, schody Rauh,
brama Zamku Ensis, Belurat i Donżon Cienia. Wcześniejsze stałe z dopasowania zgrubnego (`fit_offset.mjs`,
siatka co 32 px, kryterium „łaska nie w morzu”) były błędne: M00 OZ 6112 (32 px za wysoko), M10 OX 7008 /
OZ 6048 (160 px na wschód, 96 px na północ). Przedmioty Szczeliny i Szczeliny Kamiennego Sarkofagu „w morzu”
to podziemne jaskinie pod wybrzeżem, tak ma być.

Lochy legacy i podziemia: `WorldMapLegacyConvParam` (zob. `10-world-data.md`); podziemia M01 używają tego
samego przeliczenia co M00.

## Ikony i przedmioty

- `/menu/low/00_solo.tpfbhd/bdt`: `MENU_Knowledge_<iconId>` (512 px), `MENU_Load_<n>` (ekrany ładowania).
- `regulation.bin`: AES-256-CBC (IV = pierwsze 16 B), klucz jak w narzędziach społeczności
  (np. SoulsFormats), sprawdzony: po odszyfrowaniu jest nagłówek `DCX`. Potem ZSTD, a w środku
  BND4 z 194 plikami `.param`.
- PARAM (ER, 64-bit): `u16 liczba_wierszy` @0x0A, wiersze od 0x40 po 24 B (`i32 id, pad, i64 offset_danych, ...`).
- Pole `iconId` (u16) ustalone empirycznie (największe pokrycie istniejących ikon i najwięcej
  różnych wartości), potwierdzone nazwami:

| Parametr | offset iconId | uwagi |
|---|---|---|
| EquipParamGoods | 0x30 | przedmioty, czary (czary też są „goods”), wizerunki, klucze |
| EquipParamWeapon | 0xBE | bierzemy tylko bazowe wiersze (`id % 10000 == 0`) |
| EquipParamProtector | 0xA6 | (0xA8 to wersja żeńska) |
| EquipParamAccessory | 0x26 | talizmany |
| EquipParamGem | 0x34 | popioły wojny (ikony powtarzają się wg typu) |

- Statystyki (`items.json` → `stats`), offsety ustalone na znanych przedmiotach (Sztylet, Długi miecz,
  Claymore, Rzeki Krwi, Relikwiarzowy miecz, Bolt of Gransax, pieczęcie, Kometa Azura):

| Parametr | Pole | Offset |
|---|---|---|
| EquipParamWeapon | waga (f32) | 0x10 |
| | obrażenia u16: fizyczne / magiczne / ogień / błyskawice | 0xC8 / 0xCA / 0xCC / 0xCE |
| | obrażenia święte u16 | 0x18C |
| | skalowanie f32: siła / zręczność / inteligencja / wiara | 0x24 / 0x28 / 0x2C / 0x30 |
| | skalowanie tajemności f32 | 0x19C |
| | wymagania u8: siła / zręczność / inteligencja / wiara | 0xF2 / 0xF3 / 0xF4 / 0xF5 |
| | wymaganie tajemności u8 | 0x195 |
| EquipParamProtector | waga (f32) | 0x24 |
| | współczynniki obrażeń f32 (absorpcja = 1 − x): fiz., cięcie, obuch, pchnięcie, magia, ogień, błyskawice | 0xE4 … 0xFC (co 4) |
| | święte | 0x11C |
| Magic (ID = ID goods czaru) | koszt PF (s16) | 0x10 |
| | wymaganie inteligencji / wiary (u8) | 0x22 / 0x23 |

  Skalowanie w makiecie na litery jak w grze: S ≥ 175, A ≥ 140, B ≥ 90, C ≥ 60, D ≥ 25, E > 0.
- Opis z gry (`info`): krótkie teksty `GoodsInfo`, `AccessoryInfo`, `ProtectorInfo`, `GemInfo` (PL).
  Notkę „Do czego służy” generuje makieta z kategorii i statystyk (`usageNote` w `mockup/app.js`).
- Nazwy: `/msg/polpl/item.msgbnd.dcx` (+ `_dlc01`, `_dlc02`). Są oficjalne polskie nazwy z gry
  (np. „Butelka szkarłatnych łez”, „Wizerunek Gwiezdnej Plagi”) i angielskie (`engus`) do dopasowań.
- Ikony bossów = ikony wizerunków (remembrances): goods 2950–2964 (gra bazowa) i
  2002900–2002910 (DLC), mapowanie w `assets/data/bosses.json`.
- Kółka questów: ikony przedmiotów kojarzonych z NPC, np. Odłamek Alexandra (talizman 1231,
  ikona 18871), Pierwotny błyskamień Sellen (goods 8144, ikona 3072).

Ikony miejsc na mapie: atlasy `SB_MapCursor`, `SB_MapCursor_02`, `SB_MapCursor_03_dlc` (BC7 2048×1024)
z `/menu/hi/01_common.tpf.dcx`, współrzędne wycinków `MENU_MAP_<id>` w plikach `.layout` (XML) z
`/menu/hi/01_common.sblytbnd.dcx`. `extract_icons.py` zapisuje atlasy i `layout.json` do `assets/cache/mapicons`,
`build_icons.mjs` wycina 97 ikon do `assets/map/icons/<id>.png`. Ikona 48 to Twierdza Okrągłego Stołu.

## Rzadkość i żywioły przedmiotów (ramki w UI)

Ustalone porównaniem znanych przedmiotów (2026-11-23), zapisywane w `items.json` jako `rarity` i `stats.status`:

| Parametr | Rzadkość (u8) | Wartości |
|---|---|---|
| `EquipParamWeapon` | `+0x240` | 0 amunicja/brak, 1 zwykły, 2 rzadki, 3 legendarny (złote tło w grze; Czarny nóż, Bluźniercze ostrze…) |
| `EquipParamProtector` | `+0xD7` | 3 = np. zbroja Pana Elden, Radahna |
| `EquipParamAccessory` | `+0x41` | 3 = np. Ikona Radagona, Pieczęć Marysi |
| `EquipParamGoods` | `+0x78` | 3 = Wielkie runy, Butelka cudownego fizyku |
| `EquipParamGem` | `+0x32` | 3 = np. Fale ciemności |

Statusy broni: `EquipParamWeapon +0x44/+0x48/+0x4C` = spEffectBehaviorId0–2 → wiersz `SpEffectParam`,
w nim kumulacja (i32): trucizna `+0xCC`, szkarłatna zgnilizna `+0xD0`, krwotok `+0xD4`, plaga śmierci `+0xD8`,
odmrożenie `+0x1A8`, sen `+0x338`, szaleństwo `+0x33C` (np. Uchigatana krwotok 45, Wielki miecz Ciemnego Księżyca mróz 55).
Żywioły z obrażeń (magia/ogień/błyskawica/święte). Nasycenie broni z ekwipunku w save'ie: `(id % 10000) / 100`
(4 ogniste, 5 płomiennej sztuki, 6 błyskawiczne, 7 uświęcone, 8 magiczne, 9 mroźne, 10 zatrute, 11 krwawe, 12 okultystyczne).

Typ broni: `EquipParamWeapon +0x1A6` u16 wepType (1 sztylet, 3 miecz prosty, 5 wielki miecz, 7 kolosalny, 9 zakrzywiony,
13 katana, 15 kłujący, 17 topór, 21 młot, 25 włócznia, 29 halabarda, 39 bicz, 50/51/53 łuki, 55 kusza, 57 kostur,
61 pieczęć, 65/67/69 tarcze, 81–86 amunicja, 87 pochodnia, 88–95 typy DLC) → `stats.class`.
Slot zbroi: `EquipParamProtector +0xD6` (0 głowa, 1 tułów, 2 ręce, 3 nogi) → `stats.slot`.
W widoku Przedmioty: grupowanie (domyślnie rzadkość, poza tym typ, skalowanie, żywioł/status, posiadanie), sortowanie
(rzadkość, nazwa, kolejność gry, atak, waga, wymagania, ochrona, koszt PF), filtry (szukaj, posiadane/brakujące, DLC, żywioł).

UI łączy oba wymiary: kolor ramki = rzadkość (stal / srebro / złoto z ozdobnymi rogami), rogi ramki i „klejnoty”
= dwa najsilniejsze żywioły/statusy (np. legendarny + mróz + magia).

## Krzywe statystyk i miękkie progi (`stat_curves.json`)

`regulation.bin` → `CalcCorrectGraph` (wiersz 0x50 B: `+0x00` 5×f32 progi, `+0x14` 5×f32 wartości, `+0x28` 5×f32 wykładniki).
Wiersze: 100 PŻ ← Witalność (25/40/60 → 800/1450/1900), 101 PS ← Umysł (15/35/60), 104 wytrzymałość ← Wytrwałość
(15/30/50), 220 udźwig ← Wytrwałość (8/25/60 → 45/72/120/160), 0 skalowanie fizyczne (18/60/80), 4 skalowanie żywiołów
(20/50/80), 6 statusy ← Tajemność (25/45/60). Sprawdzone na save'ach (np. Witalność 11 → 434 PŻ, Umysł 12 → 85 PS).
Nie każdy próg to cap: frontend porównuje przyrost na punkt przed i po progu. Spadek = miękki próg (podświetlenie
„blisko progu”, gdy brakuje ≤ 3 pkt), wzrost = przyspieszenie (PŻ po 25, PS po 15 i 35, Tajemność po 25).

## Rangi bossów (frontend)

Wielki run (6 półbogów) · Legenda (wizerunek albo ≥ 300 tys. / DLC ≥ 380 tys. run) · Wielki boss (główny loch: m10,
m11, m13–m16, m19, DLC m20–m28, albo ≥ 70 tys. / DLC ≥ 200 tys.) · Boss · Pomniejszy (< 5 tys. / DLC < 75 tys.) ·
Ledwo boss (< 1,5 tys. run, np. Łata, Tricia, Szalony Dyniogłowy). Progi dobrane na rozkładzie run z `GameAreaParam`.

## Modele 3D → portrety (bossowie i postacie)

- Model: `/chr/cXXXX.chrbnd.dcx` → `cXXXX.flver` (FLVER2, wersja 0x2001A; parser `tools/extract/flver.py`:
  pozycja typ 0x02/0x03, normalna 0x10/0x11/0x13/0x2F jako `(b-127)/127` lub 0x1A jako short, UV 0x15/0x16 jako short/2048;
  faceset bez flag LOD `0x83000000`, paski trójkątów obsłużone).
- Tekstury: `/chr/cXXXX_h.texbnd.dcx` (zapasowo `_l`). Nazwa albedo nie jest w FLVER (ER używa MATBIN):
  materiał `C[cXXXX]_nazwa.matxml` → `/material/allmaterial*.matbinbnd.dcx` → pierwsza ścieżka `*_a.tif`.
  Część postaci dzieli tekstury z modelem-wzorcem (Rycerz Godricka c4311 → `c4310_*`), więc szukamy też w texbnd
  postaci z prefiksu nazwy tekstury.
- Meshe wariantów (`#NN#`) według maski wyświetlania postaci; siatki efektów ataków (`_Arts_` w nazwie, np. kwiat
  Malenii o średnicy 19 m) pomijane. Render: `render.mjs` (z-bufor, przezroczystość z alfy tekstury poza skórą,
  światła, cienie, kadr „bust” = górna część faktycznie narysowanej sylwetki).
- Poza: modele są zapisane w pozie spoczynkowej szkieletu (ludzie i humanoidy w pozie T albo A). `flver.py` czyta
  kości (pozycja, obrót, skala, rodzic) i wagi wierzchołków (4 × u8 indeksy, 4 × u8 wagi), `export_model.arm_turns`
  liczy położenia stawów i opuszcza ramiona do ok. 78° poniżej poziomu, obracając wszystko pod `L_/R_UpperArm` wokół
  barku; wierzchołki idą za kośćmi według wag. Hierarchia kości jest łączona po nazwach ze wszystkich części jednej
  postaci (w pliku tułowia palce nie mają rodzica, rękawice mają tylko kości dłoni). Modele bez tych kości (zwierzęta,
  smoki) zostają w pozie spoczynkowej, ogony też.
- Bossowie: model z nazwy części MSB (`c4340_9000`) dla encji bossa, zapasowo wróg o tej samej nazwie z NpcParam.
  Portret ma każdy z 209 bossów (ludzcy złożeni z części, opisane niżej).
- Bossowie ludzcy (`c0000`: Leda, Łata, Hrabia Ymir): w MSB dane wroga `+0x18` = `CharaInitID`.
  `CharaInitParam`: `+0x20` hełm, `+0x24` zbroja, `+0x28` rękawice, `+0x2C` nogi (ID z EquipParamProtector),
  `+0x10`/`+0x18` bronie. `FaceParam` ma wiersz o tym samym ID: `+0x00` model twarzy, `+0x01` skóra RGB, kolejne
  bajty jak w FaceData z save'a (cienie, policzki, oczy), `+0x3C` model włosów (`hr_a_NNNN`), `+0x3D` włosy RGB.
  Gdy część bossa nie ma CharaInit (Leda: atrapa `10003000`), bierzemy imiennika z tej samej mapy (`chara_init` w
  `bosses_all.json`). Render: `render_character.render_npc` → `assets/renders/npc_<CharaInitID>.png`: cała postać
  w zbroi z CharaInitParam (`-1` = pusty slot, wtedy „goła” część), płeć z `+0xE4` (0 = kobieta), kadr popiersia.

## Portret postaci gracza (głowa i cała postać)

`tools/extract/render_character.py` → `assets/renders/char_<sl2|co2>_<slot>.png` (głowa) i `char_<…>_<slot>_full.png`
(cała postać w założonej zbroi, strona postaci), ok. 3 s na postać. Backend rysuje je od nowa po zmianie zbroi, wyglądu
albo renderera (`erbackend/portraits.py`); gdy renderu brak, UI pokazuje ikonę hełmu (dla całej postaci: głowę).
Cała postać stoi w pozycji spoczynkowej szkieletu (poza T), bo części nie mają animacji.

- FaceData w save'ie (blok `FACE`, wersja 4, rozmiar 0x120, szukany w slocie; offsety od magii):
  `+0x0C` model twarzy v → plik `/parts/fg_a_01{(v%100)//10}{v%10}` (0→0100, 20→0120, 101→0101, 151→0151;
  tak samo koduje `FaceParam +0x00`: wartości 0–52 i 100–152),
  `+0x10` włosy → `/parts/hr_a_NNNN`, `+0x18` brwi, `+0x1C` zarost, `+0x30..` 64 bajty kształtu twarzy (morfy FaceGen, pomijane),
  `+0xB3` skóra RGB, `+0xDB` tęczówka RGB, `+0xF6` włosy RGB, `+0xFC` zarost RGB, `+0x102` brwi RGB.
- Zbroja: `EquipParamProtector +0xA4` u16 model → `/parts/{hd,bd,am,lg}_{m,f}_NNNN` (wersja `_f` tylko dla części
  modeli); „gołe” sloty (10000, 100000, 200000, 300000) też mają model (np. `bd_m_1140`). Bajty `+0x132+NN` (NN 0–95, Paramdex `invisibleFlag_SexVerNN`)
  = ukryj meshe `#NN#`: w portrecie głowy flagi hełmu działają na twarz i włosy (kaptur ukrywa segmenty włosów 60–65),
  w całej postaci, jak w grze, flagi wszystkich czterech części na wszystkie części (wysoki kołnierz ukrywa kolczugę
  hełmu). Materiały części: `export_model.material_layers`, ta sama funkcja co dla modeli postaci (wzór tkaniny,
  pasma futra z tekstury `Hair`, mapa normalnych).
- Pliki twarzy zawierają całe ciało (materiały `_Body`/`SSStest`); portret głowy bierze tylko `_Face`, cała postać
  także skórę ciała.
  Albedo twarzy = `FG_A_xxxx_a` z TPF części, barwione kolorem skóry z save'a.
- Włosy nie mają albedo, gra barwi je w shaderze. Maska pasm = kanał alfa mapy normalnych
  `AAT500_PCHair_n` / `PCHair3_n` z `/parts/common_body.tpf.dcx`; kolor z FaceData.
  Futro/pióropusze hełmów (materiał z „Hair” w części `HD_`) mają własne albedo.
- Brak: morfów twarzy (twarz ma kształt bazowy szablonu), oczu i brwi; przy zamkniętych hełmach twarz bywa widoczna przez wizjer.

## Łaski (`graces.json`)

`BonfireWarpParam`: `+0x04` flaga odwiedzenia (71000+), `+0x08` entity ID łaski,
`+0x14` PlaceName krainy, `+0x30` PlaceName łaski, `+0x20..0x22` area/gx/gz, `+0x24` pozycja XYZ.
Na mapach świata 225 z 422 łask; reszta jest w lochach legacy i podziemiach.

## Czego jeszcze nie ma

- Przeliczenia dla podziemi i lochów legacy (Stormveil, Leyndell itd.).
- Pozycji przedmiotów na mapie (wymaga MSB map + ItemLotParam_map).
- Portretów NPC (gra ich nie ma; w zamian ikony przedmiotów). Możliwy render modeli `c0000` (części zbroi + twarz).

## Ukryte statystyki przedmiotów (2026-11-25): `extract_effects.py` → `item_effects.json`

Talizman (`EquipParamAccessory` +0x4C..+0x58 resident, +0x04 refId), zbroja (`EquipParamProtector` +0x28/+0x2C/+0x30),
broń w ręce (`EquipParamWeapon` +0x50/+0x54/+0x58) → `SpEffectParam` (912 B). Układ pól odczytany z publicznych
definicji parametrów (Paramdex, bez licencji; w projekcie tylko przesunięcia, pliki nie są dołączane); zgodność
sprawdzona rozmiarami wierszy wszystkich pięciu parametrów i znanymi przesunięciami statusów.
- Zadawane obrażenia: `atkEnemyDmgCorrectRate_*` (+0x2A0..+0x2B0, przeciw wrogom) × `…AttackRate` × `…AttackPowerRate`;
  otrzymywane: `defEnemyDmgCorrectRate_*` (+0x274..) × `…DamageCutRate`. Wartości dla PvP (`…Player…`) pomijamy.
- Warunek rodzaju ataku: `magicSubCategoryChange` (+0x13A/+0x13B/+0x328): 100 ładowane, 101 z wierzchowca,
  102 z wyskoku, 103 kontry po bloku, 104 ostatni cios serii, 105/113/118 strzały i bełty, 106/116 ryki i zionięcia,
  108 garnki, 109 perfumy, 110 ładowane czary, 111/112 popioły wojny; `stateInfo` (+0x156) 111 krytyki, 197 kontrataki.
- Warunek stanu: `conditionHp` (+0x04, PŻ ≤ X%), `conditionHpRate` (+0x1F0, 100 = pełne PŻ),
  `invocationConditionsStateChange1` (+0x2B8): 379 krwotok, 380 trucizna/zgnilizna, 480 sen, 495 szaleństwo w pobliżu.
- Pozostałe: mnożniki PŻ/PS/energii, obrony, równowagi (+0x1B4), run (+0xF4), udźwigu (+0xE4), kosztów PS, flaszek
  (+0x2F4/+0x304), atrybuty (+0x31E.., s8), odporności (+0x1FC.., s32), odkrywanie (+0x1F8 ×100), regeneracja
  energii (+0xB8, s32), PŻ/PS co `motionInterval`. Efekty pochodne (+0x124/+0x128/+0x12C/+0x174) dziedziczą warunek.
