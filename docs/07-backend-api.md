# Backend: API i warstwa danych

Backend: [backend/](../backend/) (Python, tylko biblioteka standardowa, tylko odczyt save'a).
Start: `python backend\server.py` → `http://127.0.0.1:8765`. Szczegóły uruchomienia i testów:
[backend/README.md](../backend/README.md).

Wszystkie przykłady poniżej pochodzą z prawdziwych save'ów użytkownika (2026-11-23), skrócone `"..."`.

## Zasady ogólne

- Tylko `GET` (+ `OPTIONS` dla CORS). Odpowiedzi `application/json; charset=utf-8`, `Cache-Control: no-store`.
- CORS: nagłówek `Access-Control-Allow-Origin` jest odsyłany tylko dla originów
  `http(s)://localhost:*`, `http(s)://127.0.0.1:*`, `http(s)://[::1]:*`. Strona otwarta jako `file://`
  (origin `null`) nie dostanie CORS, więc frontend trzeba serwować z lokalnego serwera (np. `python -m http.server`).
- Host: żądania z nagłówkiem `Host` innym niż localhost/127.0.0.1/[::1] dostają `403` (ochrona przed DNS rebinding).
- Błędy: `{"error": "opis po polsku"}` ze statusem `400` (zły parametr), `404` (brak pliku/slotu/endpointu),
  `503` (save nie dał się odczytać).
- Czas: ISO 8601 z lokalną strefą, milisekundy (`"2026-11-23T18:14:04.758+01:00"`).
- Parametr `file`: `sl2` (oficjalna gra) albo `co2` (Seamless Coop). `slot`: 0–9.
  Gdy pominięte → aktywny plik/slot (patrz `active`).

### `active`: aktywny plik/slot

```json
{"file": "co2", "slot": 6, "reason": "profile_last_slot", "since": "2026-11-23T18:20:29.294+01:00"}
```

`reason`: `profile_last_slot` (na starcie: plik z najnowszym `mtime`, slot „ostatnio wczytana postać”
z profilu `USER_DATA010+0x1334`; sprawdzone na 2 plikach, pewność średnia) albo `last_written`
(slot, który zmienił się w ostatnim zapisie save'a). `null`, gdy brak save'ów.

## Endpointy

### `GET /api/health`

```json
{"ok": true, "version": "0.1.0", "save_dir": "C:\\Users\\...\\EldenRing\\<SteamID64>",
 "time": "2026-11-23T18:20:31.372+01:00",
 "files": {"sl2": {"loaded": true, "error": null}, "co2": {"loaded": true, "error": null}},
 "active": {"file": "co2", "slot": 6, "reason": "profile_last_slot", "since": "..."},
 "endpoints": ["/api/characters", "..."]}
```

### `GET /api/characters`

Lista postaci z obu plików (z podsumowań w profilu, więc tanio, bez parsowania slotów).

```json
{
  "save_dir": "C:\\Users\\<użytkownik>\\AppData\\Roaming\\EldenRing\\<SteamID64>",
  "active": {"file": "co2", "slot": 6, "reason": "profile_last_slot", "since": "2026-11-23T18:20:29.294+01:00"},
  "files": [
    {
      "file": "sl2",
      "path": "C:\\Users\\<użytkownik>\\AppData\\Roaming\\EldenRing\\<SteamID64>\\ER0000.sl2",
      "written_at": "2026-11-23T17:52:55.788+01:00",
      "last_slot": 1,
      "characters": [
        {"slot": 0, "name": "grandes", "level": 148, "playtime_s": 255928, "runes_memory": 9182319, "map_id": "m60_46_39_16"},
        {"slot": 1, "name": "boink", "level": 180, "playtime_s": 277906, "runes_memory": 14592293, "map_id": "m61_49_43_00"},
        "..."
      ]
    },
    {"file": "co2", "path": "...ER0000.co2", "written_at": "2026-11-23T18:14:04.758+01:00", "last_slot": 6, "characters": ["..."]}
  ]
}
```

Plik, którego nie udało się wczytać, ma zamiast `written_at/characters` pole `"error"`.
Brakujący plik nie występuje w `files`.

### `GET /api/state?file=sl2|co2&slot=N`

Pełny stan postaci + statusy z warstwy danych. Przykład (prawdziwy save, dane świata z 2026-11-23):
`?file=co2&slot=1` (boink). Cały stan to ~1 MB (3458 przedmiotów, 419 łask, 213 bossów + ekwipunek), więc
zwykle warto podać `sections`, czyli listę sekcji po przecinku, np. `?sections=bosses,progress,progress_detail`
(~86 KB). `character` i `save` są zawsze. `item_kind` zawęża listę `items` (np. `item_kind=acquired_flag`: tylko
osełki i popioły; ~3400 skarbów z map to ~1 MB, a ich stan strona i tak czyta przez `/api/flags`); `progress` się nie zmienia.
Strona (`mockup/`) pobiera: `sections=position,bloodstain,regions,inventory,equipment,stats,items,bosses,warnings,progress_detail&item_kind=acquired_flag`
(~280 KB), a przełącznik postaci tylko `sections=equipment` (~2 KB).

```json
{
  "character": {
    "slot": 1, "name": "boink", "level": 180, "playtime_s": 278345, "runes_memory": 14592293,
    "deaths": 330,
    "last_grace": {"entity_id": 1042362951, "grace_id": "grace-76101", "name": "Pierwszy krok", "map_id": "m60_42_36_00"},
    "body_type": {"id": 1, "name": "A"},
    "archetype": {"id": 9, "name": "wretch"},
    "starting_gift": {"id": 3, "name": "golden_seed"}
  },
  "position": {
    "map_id": "m60_42_36_00", "x": -35.56, "y": 90.926, "z": -73.424,
    "global": {"x": 10844.44, "z": 9270.576, "verified": true},
    "map": {"map": "M00", "px": 3676.4, "py": 7337.4, "approx": false}
  },
  "map_id": "m60_42_36_00",
  "bloodstain": {"map_id": "m61_49_44_00", "x": -99.996, "y": 359.637, "z": -51.285,
                 "global": {"x": 12572.004, "z": 11340.715, "verified": true}, "runes": 6222},
  "regions_unlocked": [1001001, 1001002, 1001000, 1800090, 1800010, 1800001, "..."],
  "regions": [
    {"id": 1001001, "name": "Kaplica Oczekiwania", "region": "Zamek Burzowego Całunu", "subregion": "Kaplica Oczekiwania",
     "map_id": "m10_01_00_00", "kind": "dungeon"},
    {"id": 6101000, "name": "Burzowe Wzgórze", "region": "Pogrobno", "subregion": "Burzowe Wzgórze", "map_id": "m60", "kind": "overworld"},
    "..."],
  "equipment": {"head": null, "chest": {"id": 930100}, "...": "patrz „Założony ekwipunek”"},
  "inventory": {"weapons": ["..."], "armor": ["..."], "talismans": ["..."], "goods": ["..."], "ashes": ["..."],
                "key_items": ["..."], "totals": {"...": 0}},
  "bosses": [
    {"id": "boss-10000800", "name": "Godrick, Zszywaniec", "region": "Limgrave", "location": null,
     "defeated": true, "dlc": false, "required": null, "hints": null, "confidence": "high",
     "discovered": true, "discovered_by": "defeated", "attempts": null,
     "flag": 10000800, "name_en": "Godrick the Grafted", "region_pl": "Jeziorna Liurnia",
     "map_id": "m10_00_00_00", "runes": 20000},
    {"id": "boss-21010800", "name": "Messmer Palownik", "region": "Scadu Altus", "location": "Shadow Keep",
     "defeated": false, "dlc": true, "required": true,
     "hints": "Szczyt Shadow Keep — przez Specimen Storehouse w górę do Dark Chamber Entrance. Daje Messmer's Kindling.",
     "confidence": "verified", "discovered": true, "discovered_by": "area_grace", "attempts": null,
     "flag": 21010800, "name_en": "Messmer the Impaler", "region_pl": "Donżon cienia",
     "map_id": "m21_01_00_00", "runes": 400000},
    {"id": "boss-41020800", "name": "Płaczka", "region": "Gravesite Plain", "location": "Lamenter's Gaol",
     "defeated": false, "dlc": true, "required": false, "hints": null, "confidence": "verified",
     "discovered": true, "discovered_by": "area_grace", "attempts": 0,
     "flag": 41020800, "name_en": "Lamenter", "region_pl": "Cmentarna Równina", "map_id": "m41_02_00_00", "runes": 160000},
    "..."
  ],
  "graces": [
    {"id": "grace-76101", "name": "Pierwszy krok", "region": "Pogrobno", "area": null, "visited": true, "dlc": false,
     "discovered": true, "discovered_by": "visited", "flag": 76101, "name_en": null, "map_id": "m60_42_36_00"},
    {"id": "grace-76800", "name": "Cmentarna Równina", "region": "Gravesite Plain", "area": "Gravesite Plain",
     "visited": true, "dlc": true, "discovered": true, "discovered_by": "visited",
     "flag": 76800, "name_en": "Gravesite Plain", "map_id": "m61_46_40_00"},
    "..."
  ],
  "items": [
    {"id": "item-65610", "name": "Żelazne ostrze", "category": "key_item", "collected": true, "dlc": false,
     "location": null, "discovered": true, "discovered_by": "collected", "flag": 65610, "kind": "map_lot",
     "map_id": "m10_00_00_00"},
    {"id": "ash-of-war-assassin-s-gambit", "name": "Ash of War: Assassin's Gambit", "category": "ash_of_war",
     "collected": false, "dlc": false, "location": null, "discovered": false, "discovered_by": null,
     "flag": 65880, "kind": "acquired_flag", "map_id": null},
    "..."
  ],
  "quests": [
    {"id": "blaidd", "name": "Blaidd, Półwilk", "npc": "Blaidd, Półwilk", "dlc": false,
     "steps": [
       {"id": "s1", "text": "Spotkaj Blaidda (wycie w Las Mgieł) i pomóż mu w Wieczne więzienie rycerza bez pana — pokonaj Darriwila.",
        "done": true, "where": "Wieczne więzienie rycerza bez pana"},
       {"id": "s2", "text": "Pokonaj Radahna (Blaidd pomaga na festiwalu w Zamek Lwiej Grzywy).", "done": false,
        "where": "Zamek Lwiej Grzywy"},
       "..."],
     "completed": false, "next": "Weź udział w festiwalu w Zamek Lwiej Grzywy i pokonaj Radahna.",
     "next_where": "Zamek Lwiej Grzywy", "region": "Pogrobno", "icon": 10126, "missable": false,
     "confidence": "low", "discovered": true, "discovered_by": "started"},
    "..."
  ],
  "warnings": [],
  "progress": {
    "bosses": {"done": 157, "total": 213},
    "graces": {"done": 327, "total": 419},
    "items": {"done": 2146, "total": 3463},
    "quests": {"done": 26, "total": 45}
  },
  "progress_detail": {
    "bosses": {"base": {"done": 147, "total": 170}, "dlc": {"done": 10, "total": 43}},
    "bosses_required": {"done": 5, "total": 10},
    "graces": {"base": {"done": 295, "total": 314}, "dlc": {"done": 32, "total": 105}},
    "items": {"base": {"done": 1887, "total": 2491}, "dlc": {"done": 259, "total": 972}},
    "map_treasures": {"done": 2061, "total": 3336},
    "items_by_category": {"ammo": {"done": 48, "total": 67}, "armor": {"done": 45, "total": 63}, "...": {}},
    "quests": {"base": {"done": 24, "total": 32}, "dlc": {"done": 2, "total": 13}}
  },
  "save": {
    "file": "co2", "path": "C:\\Users\\<użytkownik>\\AppData\\Roaming\\EldenRing\\<SteamID64>\\ER0000.co2",
    "written_at": "2026-11-23T18:14:04.758+01:00", "slot_md5": "6726d0f3488dfd7f23fb2191d2831cfb",
    "is_active": false
  }
}
```
(liczby z chwili pisania; dane świata są przebudowywane, np. liczba questów rośnie)

Pola:

| Pole | Opis |
|---|---|
| `character.playtime_s` | czas gry w sekundach (z profilu) |
| `character.runes_memory` | „pamięć run”, czyli suma run zdobytych w całej grze (z profilu), nie runy przy sobie |
| `character.deaths` | liczba śmierci (preambuła przed blokiem flag) |
| `character.last_grace` | `entity_id` = surowa wartość z save'a (`last_rested_grace` = encja łaski + 1000); `grace_id`, `name` (PL), `map_id` z `graces.json` (dopasowanie po `last_grace_id`); `null`, gdy nieznana |
| `position` | `x,y,z` = współrzędne lokalne kafla/mapy `map_id` (z `PlayerCoordinates`). `global` tylko dla `m60_*`/`m61_*`: `kafel*256 + 128 + lokalna` (X i Z), zweryfikowane (`verified: true`): to ten sam wzór, którym liczone są `px/py` w `assets/data`, a backend odtwarza je z 0 rozbieżnościami na 225 łaskach i 3379 skarbach |
| `position.map` / `bloodstain.map` | piksele mapy strony: `{map: "M00"/"M10", px, py, approx}`, także w lochach (przez `WorldMapLegacyConvParam`; małe lochy = punkt wejścia, `approx: true`); `null`, gdy nie da się przeliczyć. To samo w `/api/deaths` (`deaths[].position.map`) |
| `map_id` | mapa z nagłówka slotu (zwykle = `position.map_id`) |
| `bloodstain` | ostatnia plama krwi: `{map_id, x, y, z, global, runes}`; `runes` = `null`, gdy run nie ma / odzyskane. `null`, gdy postać jeszcze nie zginęła. Układ struktury: patrz „Miejsca śmierci” |
| `regions_unlocked` | surowe ID z save'a (= ID wierszy `PlayRegionParam`) |
| `regions` | to samo z nazwami: `{id, name, region, subregion, map_id, kind: "overworld"/"dungeon"}`, patrz „Regiony i krainy” |
| `bosses[].defeated` | flaga pokonania (`flag`) z `data/bosses.json` |
| `bosses[]`, nowe pola | `flag`, `name_en`, `region_pl`, `map_id`, `runes`; `name` jest teraz po polsku (z plików gry) |
| `bosses[].required` | `true` potrzebny do napisów końcowych gry / końca DLC (10 bossów), `false` opcjonalny (kuratorowane DLC), `null` nie oznaczono |
| `bosses[].confidence` | pewność mapowania flaga → boss (patrz niżej) |
| `graces[].visited` | łaska odkryta (można się do niej teleportować); nowe pola: `flag`, `name_en` (tylko DLC z tabeli CE), `map_id` |
| `items[].collected` | skarb podniesiony z mapy (`kind: "map_lot"`, flaga z ItemLotParam_map) albo przedmiot zdobyty (`kind: "acquired_flag"`, osełki/popioły z tabeli CE); nowe pola: `flag`, `kind`, `map_id` |
| `items[].category` | rodzaj skarbu: `consumable, material, golden_rune, smithing_stone, weapon, somber_stone, talisman, key_item, cookbook, ammo, armor, upgrade, dlc_blessing, stonesword_key, spirit_ash, golden_seed, incantation, map_fragment, note, sorcery, bell_bearing, ash_of_war, sacred_tear, crystal_tear, memory_stone, whetblade` |
| `progress_detail` | postęp z podziałem gra podstawowa / DLC, bossowie obowiązkowi, skarby z map, przedmioty wg kategorii |
| `character.body_type / archetype / starting_gift` | z podsumowania postaci w profilu (`+0x242/+0x243/+0x244`), `{id, name}`, patrz „Założony ekwipunek” |
| `equipment` | co postać ma założone (jak na ekranie wczytywania), patrz „Założony ekwipunek” |
| `inventory` | co postać posiada (przy sobie + w skrzyni), także kupione / z wrogów, patrz „Ekwipunek” |
| `*.discovered` / `discovered_by` | tryb bez spoilerów, patrz sekcja „Tryb bez spoilerów” |
| `bosses[].attempts` | liczba prób (śmierci na arenie przed pokonaniem) albo `null`, patrz „Miejsca śmierci” |
| `warnings[]` | ostrzeżenia „zanim zabijesz…”, patrz niżej |
| `quests[]` | `{id, name, npc, dlc, steps:[{id, text, done, where}], completed, next, next_where, region, icon, missable, confidence, discovered, discovered_by}`; `next` / `next_where` = „co dalej” i gdzie (pierwszy niezaliczony krok) |
| `save.slot_md5` | MD5 slotu z pliku; zmienia się przy każdym zapisie tej postaci (przydatne do cache) |
| `save.is_active` | czy to aktywny plik/slot |

### `GET /api/flags?ids=76800,20000800&file=co2&slot=1`

Odczyt dowolnych flag po ID (maks. 1000 na żądanie). `null` = ID spoza tabeli bloków.

```json
{"file": "co2", "slot": 1, "flags": {"76800": true, "20000800": true, "9140": true}}
```

### Wpisy kroniki

Baza historii zapisuje zmiany postaci jako wpisy. Strona dostaje je dniami z `/api/days` (`days[].events`), a na żywo
w zdarzeniu SSE `chronicle`. Każdy wpis ma `id`, `ts`, `kind`, `ref_id`, `name`, `data` i `character`:

| `kind` | `ref_id` | `name` | `data` |
|---|---|---|---|
| `boss_defeated` | id bossa | nazwa bossa | `{flag}` |
| `grace_discovered` | id łaski | nazwa łaski | `{flag}` |
| `item_collected` | id przedmiotu | nazwa | `{flag}` |
| `item_obtained` | `kategoria:id` (np. `talisman:1000`) | `null` (nazwę dopisuje strona) | `null` |
| `quest_step` | id questa | nazwa questa | `{step_id, text}` |
| `level_up` | `null` | `"Poziom 181"` | `{from, to}` |
| `map_changed` | nowy `map_id` | nowy `map_id` | `{from, to, from_area, to_area}` |

`ts` = czas zapisu pliku save, w którym zmiana się pojawiła (gra zapisuje co ~60 s, więc to nie jest
dokładna chwila zdarzenia). `map_changed`: świat otwarty (`m60`, `m61`) liczy się jako jeden obszar:
przejście między kaflami nie jest zdarzeniem; zdarzeniem jest wejście/wyjście z lochu, legacy dungeonu itp.
(obszar = `mAA_BB`). Cofnięcia flag (np. NG+) nie trafiają do kroniki (są tylko w SSE `save.reverted`).

### `GET /api/deaths?file=&slot=&limit=`

Prawdziwy przykład (boink, postać zastana przy pierwszym uruchomieniu, więc jest tylko wpis `baseline`):

```json
{
  "character": {"file": "co2", "slot": 1, "name": "boink"},
  "deaths_total": 330,
  "bloodstain": {"map_id": "m61_49_44_00", "x": -99.996, "y": 359.637, "z": -51.285,
                 "global": {"x": 12572.004, "z": 11340.715, "verified": true}, "runes": 6222},
  "recorded": 0,
  "deaths": [
    {"id": 8, "ts": "2026-11-23T18:14:04.758+01:00", "deaths_total": 330, "delta": 0,
     "position": {"map_id": "m61_49_44_00", "x": -99.996, "y": 359.637, "z": -51.285},
     "runes": 6222, "baseline": true, "character": {"file": "co2", "slot": 1, "name": "boink"}}
  ]
}
```
Zarejestrowana śmierć (test na kopii): `{"id": 13, "ts": "…", "deaths_total": 1, "delta": 1, "position": {"map_id": "m41_02_00_00", "x": 12.5, "y": 30.25, "z": -40.0}, "runes": 1234, "baseline": false, "character": {…}}`.

- `deaths`: najnowsze najpierw. `recorded` = liczba śmierci zarejestrowanych przez backend (bez `baseline`).
- `baseline: true`: plama krwi zastana przy pierwszym zobaczeniu postaci (czas śmierci nieznany, `ts` = czas zapisu).
- `delta`: o ile wzrósł licznik od poprzedniego zapisu (przy kilku śmierciach między zapisami znamy tylko miejsce ostatniej).
- `position: null`: licznik wzrósł, ale plama krwi się nie przesunęła (np. śmierć bez run), więc miejsce jest nieznane.

### `GET /api/session?file=&slot=`

Bieżąca lub ostatnia sesja. Sesja = ciąg zapisów save'a tej postaci bez przerwy dłuższej niż 600 s.
Przykład (test na kopii: jeden zapis z pokonanym bossem, nową łaską i śmiercią):

```json
{
  "character": {"file": "co2", "slot": 6, "name": "chuj"},
  "gap_s": 600,
  "session": {
    "active": true,
    "started_at": "2026-11-23T18:30:01.562+01:00", "ended_at": "2026-11-23T18:30:01.562+01:00",
    "wall_duration_s": 0.0, "playtime_s": 0, "saves": 1,
    "bosses": [{"id": "boss-41020800", "name": "Płaczka", "ts": "2026-11-23T18:30:01.562+01:00"}],
    "graces": [{"id": "grace-74102", "name": "Loch płaczki", "ts": "2026-11-23T18:30:01.562+01:00"}],
    "items": [], "quest_steps": [], "maps": [],
    "deaths": 1,
    "death_points": [{"map_id": "m41_02_00_00", "x": 12.5, "y": 30.25, "z": -40.0}],
    "levels": {"from": 8, "to": 8, "gained": 0},
    "runes_gained": 0,
    "based_on_previous_save": true
  }
}
```

| Pole | Opis |
|---|---|
| `active` | ostatni zapis był mniej niż 600 s temu |
| `started_at` / `ended_at` | czas pierwszego / ostatniego zapisu w sesji (gra zapisuje co ~60 s, więc faktyczny start był do ~1 min wcześniej) |
| `wall_duration_s` | `ended_at − started_at` |
| `playtime_s` | przyrost czasu gry wg licznika gry (dokładniejszy niż zegar) |
| `deaths`, `levels`, `runes_gained` | różnica względem zapisu sprzed sesji (`based_on_previous_save: true`) albo względem pierwszego zapisu sesji (`false`, np. pierwsza obserwacja postaci) |
| `bosses/graces/items/quest_steps/maps` | zdarzenia kroniki z czasu sesji (`quest_steps`: `{quest_id, quest, step_id, text, ts}`) |
| `items_obtained` | klucze `kategoria:id` przedmiotów zdobytych bez flagi (kupione, z przeciwników, wytworzone) |
| `death_points` | miejsca śmierci w sesji (tylko te ze znaną pozycją) |

`session: null`: brak zapisów tej postaci w bazie.

### `GET /api/data/{bosses|graces|items|quests}`

Surowa zawartość pliku danych (`_meta` + `entries`), np. do pokazania wskazówek/notatek bez stanu.

### `GET /api/events`: Server-Sent Events

```js
const es = new EventSource("http://127.0.0.1:8765/api/events");
es.addEventListener("save", e => { const d = JSON.parse(e.data); /* odśwież /api/state */ });
```

Zdarzenia (`event:` / `data:` JSON, `id:` rosnące od 1, `retry: 3000`; co 15 s komentarz `: keepalive`):

Zdarzenie `hello` przychodzi od razu po połączeniu:
```json
{"time": "2026-11-23T18:20:46.207+01:00", "active": {"file": "co2", "slot": 6, "reason": "profile_last_slot", "since": "..."},
 "save_dir": "C:\\Users\\..."}
```

Zdarzenie `save` przychodzi po każdym zapisie save'a, osobno dla każdego zmienionego slotu (diff względem
poprzedniego zapisu tej postaci zapamiętanego w bazie historii). Przykład z testu
(kopia `.co2` w katalogu tymczasowym, slotowi 6 ustawiono 4 flagi i podmieniono plik jak robi to gra):
```json
{
  "file": "co2", "slot": 6, "written_at": "2026-11-23T18:20:46.279+01:00",
  "character": {"slot": 6, "name": "chuj", "level": 8, "playtime_s": 459, "runes_memory": 594, "deaths": 0},
  "position": {"map_id": "m60_42_36_00", "x": -16.29, "y": 91.134, "z": -48.6,
               "global": {"x": 10863.71, "z": 9295.4, "verified": true}},
  "bloodstain": null,
  "new_character": false,
  "changed_flags": [{"id": 9140, "value": true}, {"id": 65610, "value": true},
                    {"id": 76800, "value": true}, {"id": 20000800, "value": true}],
  "changed_flags_total": 4, "truncated": false,
  "completed": {
    "bosses": [{"id": "boss-20000800", "name": "Boska bestia, Tańczący Lew", "flag": 20000800}],
    "graces": [{"id": "grace-76800", "name": "Gravesite Plain", "flag": 76800}],
    "items": [{"id": "item-65610", "name": "Żelazne ostrze", "flag": 65610}],
    "quest_steps": []
  },
  "reverted": {"bosses": [], "graces": [], "items": [], "quest_steps": []},
  "deaths_delta": 0, "level_delta": 0, "regions_added": [], "map_changed": null,
  "active": {"file": "co2", "slot": 6, "reason": "last_written", "since": "2026-11-23T18:20:47.165+01:00"}
}
```

- `changed_flags`: wszystkie zmienione bity (posortowane po ID), maks. 500; `truncated: true`, gdy więcej
  (`changed_flags_total` podaje pełną liczbę). `id` może być `null` dla bitu spoza tabeli bloków.
  Uwaga: gra przy każdym zapisie przełącza też flagi techniczne (np. 9800→9807, pary flag mapy),
  więc frontend powinien patrzeć głównie na `completed`.
- `completed` / `reverted`: wpisy z warstwy danych, których flaga przeszła na `true` / `false`.
  `quest_steps`: `{quest_id, quest, step_id, text}`. Wpisy `items` mają też `contents[{cat, id, count}]` (zawartość skarbu).
- `new_character: true`: postać widziana pierwszy raz (nowa postać albo pierwsza obserwacja); wtedy diff jest pusty.
- `map_changed`: `{from, to}` przy zmianie obszaru (zasady jak w kronice) albo `null`.
- `bloodstain`: aktualna plama krwi (jak w `/api/state`).

Zdarzenie `chronicle` przychodzi zaraz po `save`, gdy zapis dodał wpisy do kroniki albo śmierci (wpisy jak w „Wpisy kroniki” i śmierci jak w `/api/deaths`):
```json
{"character": {"file": "co2", "slot": 6, "name": "chuj"},
 "events": [{"id": 1, "ts": "2026-11-23T18:30:18.331+01:00", "kind": "boss_defeated", "ref_id": "boss-41020800",
             "name": "Płaczka", "data": {"flag": 41020800}, "character": {"file": "co2", "slot": 6, "name": "chuj"}}, "..."],
 "deaths": [{"id": 13, "ts": "2026-11-23T18:30:18.331+01:00", "deaths_total": 1, "delta": 1,
             "position": {"map_id": "m41_02_00_00", "x": 12.5, "y": 30.25, "z": -40.0}, "runes": 1234,
             "baseline": false, "character": {"file": "co2", "slot": 6, "name": "chuj"}}]}
```
- Gdy plik się zmienił, ale żaden slot nie: `{"file": "co2", "slot": null, "written_at": "...", "note": "...", "active": {...}}`.

Zdarzenie `error` oznacza zmianę pliku, którego nie udało się spójnie odczytać (np. 15 prób z niezgodnym MD5):
```json
{"file": "co2", "error": "nie udało się odczytać spójnego pliku: niezgodne MD5: USER_DATA003", "time": "..."}
```

Opóźnienie backendu (zapis pliku → zdarzenie): ~0,5–1 s (polling 0,5 s + debounce 0,4 s; test: 0,96 s).
Opóźnienie gry (zdarzenie w grze → zapis pliku) to osobna sprawa: mediana ~28 s, maks. ~70 s (docs/04).

## Ekwipunek (`inventory` w `/api/state`)

Z save'a: `inventory_held` (0x9010 B, za GaItem map + 0x3A4) i `storage_box` (0x6010 B, za listą pocisków
+ 0x1D7). Układ obu (zweryfikowany na 7 postaciach): `u32 liczba`, N × `{u32 gaitem_handle, u32 ilość,
u32 indeks_zdobycia}`, `u32 liczba_kluczowych`, K × to samo, 2 × `u32` liczniki. Przy sobie N = 0xA80, K = 0x180;
w skrzyni N = 0x780, K = 0x80.

Typ = górne 4 bity handle: `0x8` broń, `0x9` zbroja, `0xC` popiół wojny (ID przez wpis GaItem: handle → item_id,
prefiks typu w item_id zdjęty), `0xA` talizman, `0xB` goods (ID = `handle & 0x0FFFFFFF`, bez GaItem).
ID są zgodne z parametrami gry (EquipParamWeapon / Protector / Accessory / Goods / Gem), więc nazwy i ikony
bierze się z katalogu przedmiotów (`assets/data/items.json`) po `id` (broń po `base_id`).

Prawdziwy przykład, `chuj` (co2, slot 6, poziom 8, ekwipunek startowy):
```json
"inventory": {
  "weapons": [
    {"id": 7140000, "count": 2, "storage": 0, "base_id": 7140000, "upgrade": 0, "affinity": "standard", "ash_id": null},
    {"id": 30090000, "count": 1, "storage": 0, "base_id": 30090000, "upgrade": 0, "affinity": "standard", "ash_id": null}
  ],
  "armor": [{"id": 670000, "count": 1, "storage": 0}, {"id": 670100, "count": 1, "storage": 0},
            {"id": 670200, "count": 1, "storage": 0}, {"id": 670300, "count": 1, "storage": 0}],
  "talismans": [],
  "goods": [{"id": 100, "count": 1, "storage": 0}, {"id": 103, "count": 1, "storage": 0}, "..."],
  "ashes": [],
  "key_items": [],
  "totals": {"held_entries": 29, "held_capacity": 3072, "storage_entries": 0, "storage_capacity": 2048, "unresolved": 0}
}
```
Fragmenty z `finali` (poziom 221): broń z ulepszeniem, nasyceniem i popiołem
`{"id": 1031125, "count": 1, "storage": 0, "base_id": 1030000, "upgrade": 25, "affinity": "blood", "ash_id": 80100}`,
przedmiot kluczowy `{"id": 2130, "count": 8, "storage": 0}`, popiół `{"id": 10000, "count": 1, "storage": 0}`,
`totals`: 2858/3072 przy sobie, 526/2048 w skrzyni.

| Pole | Opis |
|---|---|
| `count` / `storage` | ilość przy sobie / w skrzyni (wpis jest, gdy którakolwiek > 0) |
| `weapons[].base_id` | `id − id % 10000`, broń bazowa (klucz do nazwy) |
| `weapons[].upgrade` | `id % 100` (+0…+25; broń „somber” maks. +10) |
| `weapons[].affinity` | `(id % 10000) // 100` → `standard, heavy, keen, quality, fire, flame_art, lightning, sacred, magic, cold, poison, blood, occult` |
| `weapons[].ash_id` | popiół wojny osadzony w broni (ID EquipParamGem) albo `null`; ta sama broń z różnymi popiołami = osobne wpisy |
| `goods` | zwykłe przedmioty (materiały, flaszki, czary; czary to też goods) |
| `key_items` | przedmioty z sekcji kluczowej ekwipunku (też ID goods: klucze, mapy, zwoje, przedmioty questowe) |
| `totals.unresolved` | handle broni/zbroi/popiołu bez wpisu GaItem (na save'ach użytkownika: 0) |

Pomijane zaślepki, które gra zawsze trzyma w ekwipunku: broń `110000` (goła ręka) i zbroja `10000/10100/10200/10300`
(brak hełmu / zbroi / rękawic / nogawic). Dokładność: ID i ilości są zweryfikowane (ekwipunek startowy postaci poziomu 8 = komplet
4 części 670000–670300 + broń + flaszki); `ash_id` to pole wpisu GaItem broni (+8), wartości wyglądają poprawnie,
ale nie porównano ich z grą.

## Założony ekwipunek (`equipment` w `/api/state`) i dane postaci z profilu

Źródła w slocie (offsety od końca GaItem map; zweryfikowane na 7 postaciach):

| Offset | Pole | Co |
|---|---|---|
| `+0x280` | `equipped_items_equip_index` (22 × u32) | indeksy w ekwipunku (nieużywane w API) |
| `+0x2D8` | `active_weapon_slots_and_arm_style` | `[0]` styl trzymania, `[1]` aktywny slot lewej ręki, `[2]` prawej (0–2) |
| `+0x2F4` | `equipped_items_item_id` (22 × u32) | ID przedmiotów w 22 slotach (pusty = `0xFFFFFFFF`) |
| `+0x34C` | `equipped_items_gaitem_handle` (22 × u32) | handle, potrzebny do popiołu wojny w broni |
| `+0x93B4` | `equipped_spells` (0x74) | 14 × (id czaru, ?) + aktywny |
| `+0x9428` | `equipped_items` (0x8C) | 10 × (handle, idx) szybkie przedmioty, aktywny, 6 × (handle, idx) sakwa, (handle, idx) wielka runa |
| za listą pocisków `+0x9C` | `equipped_physics` | 2 × item_id łez do Cudownej Fiolki (`0x4…` = goods) |

Kolejność 22 slotów: L1, P1, L2, P2, L3, P3, strzały 1, bełty 1, strzały 2, bełty 2, ?, ?, głowa, tors, ręce, nogi,
?, talizman 1–4, ?. Profil (`USER_DATA010`, podsumowanie postaci `+0x15A`, 0xE8 B) zawiera te same ID (z prefiksem typu)
i zgadza się ze slotem na wszystkich postaciach.

Prawdziwy przykład, `finali` (co2, poziom 221):
```json
"equipment": {
  "head": {"id": 860000}, "chest": {"id": 5260100}, "arms": {"id": 180200}, "legs": {"id": 5260300},
  "right_weapons": [null, null, {"id": 14510010, "base_id": 14510000, "upgrade": 10, "affinity": "standard", "ash_id": null}],
  "left_weapons": [null, {"id": 10500010, "base_id": 10500000, "upgrade": 10, "affinity": "standard", "ash_id": null}, null],
  "active_weapon": {"left": 1, "right": 2, "arm_style": 3},
  "talismans": [{"id": 1032}, {"id": 7130}, {"id": 4003}, {"id": 8090}],
  "ammo": [null, null, null, null],
  "quick_items": [{"id": 250}, {"id": 190}, {"id": 2070}, {"id": 2150}, null, null, null, null, null, null],
  "active_quick_item": 1,
  "pouch": [{"id": 1075}, {"id": 1025}, {"id": 207010}, {"id": 130}, null, null],
  "great_rune": {"id": 192},
  "spells": [{"id": 2007600}, {"id": 7500}, null, null, null, null, null, null, null, null, null, null, null, null],
  "active_spell": 0,
  "physick": [{"id": 11002}, {"id": 11008}]
}
```
(nazwy wg `assets/data/items.json`: Raging Wolf Helm, Rellana's Armor, Black Knife Gauntlets, Rellana's Greaves;
Death Knight's Twin Axes +10, Euporia +10; Great-Jar's Arsenal, Pearldrake Talisman +3, …; Radahn's Great Rune;
łzy Crimson Crystal Tear + Opaline Bubbletear.)

`chuj` (poziom 8, `archetype: warrior`) ma dokładnie zestaw startowy Wojownika: Blue Cloth Cowl/Vest, Warrior
Gauntlets/Greaves, P1 = Scimitar, L1 = Scimitar, L2 = Riveted Wooden Shield, szybkie przedmioty: flaszki 1001/1051.

| Pole | Opis |
|---|---|
| `head/chest/arms/legs` | `{id}` (EquipParamProtector) albo `null`; „goła” zbroja (10000/10100/10200/10300 oraz 100000…100300) = `null` |
| `right_weapons` / `left_weapons` | 3 sloty każdej ręki, `{id, base_id, upgrade, affinity, ash_id}` jak w `inventory`; pięść (110000) = `null` |
| `active_weapon` | `left` / `right` = indeks aktywnego slotu (0–2); `arm_style` surowy (1 = jedna ręka?, 3 = oburącz prawa?; niezweryfikowane) |
| `talismans` | 4 sloty `{id}` (EquipParamAccessory) |
| `ammo` | 4 sloty: strzały 1, bełty 1, strzały 2, bełty 2: `{id, kind: "arrow"/"bolt"}` |
| `quick_items` / `active_quick_item` | 10 slotów szybkiego dostępu (goods) + indeks aktywnego |
| `pouch` | 6 slotów sakwy (goods) |
| `great_rune` | założona wielka runa (goods, np. 191 Godrick's, 192 Radahn's) |
| `spells` / `active_spell` | 14 slotów pamięci (ID goods czarów/inkantacji) + indeks aktywnego |
| `physick` | 2 łzy w Cudownej Fiolce (goods) |

Uwaga: flaszki (goods 1000–1099) mają w slotach ID zależne od stanu (liczba ładunków / pusta) i nie zawsze takie
samo jak w `inventory`. Przy nazwach traktuj je jako rodzinę (np. 1000–1025 = Flaszka Szkarłatnych Łez).

Dane z profilu w `character`:

| Pole | Wartości | Pewność |
|---|---|---|
| `archetype` | `{id, name}`: 0 `vagabond`, 1 `warrior`, 2 `hero`, 3 `bandit`, 4 `astrologer`, 5 `prophet`, 6 `confessor`, 7 `samurai`, 8 `prisoner`, 9 `wretch` | zweryfikowane: 0 (Ser Davick: zbroja Vagabond Knight), 1 (chuj), 5 (postać „prophet”), 9 (boink: bez zbroi); reszta wg kolejności z menu |
| `starting_gift` | 0 `none`, 1 `crimson_amber_medallion`, 2 `lands_between_rune`, 3 `golden_seed`, 4 `fanged_imp_ashes`, 5 `cracked_pot`, 6 `stonesword_key`, 7 `bewitching_branch`, 8 `boiled_prawn`, 9 `shabriris_woe` | zweryfikowane: 0 i 1 (Ser Davick ma talizman 1000); reszta wg menu |
| `body_type` | 1 `A`, 0 `B` | średnia (6 z 7 postaci = 1) |

## Foldery save'ów (`save_dirs`)

`/api/health` i `/api/characters` zwracają `save_dirs: {"sl2": …, "co2": …}`; każdy rodzaj pliku może leżeć w innym
folderze. Bez `--save-dir` / `ER_SAVE_DIR` backend przeszukuje `%APPDATA%\EldenRing` (Windows) oraz na Linuxie
wszystkie prefiksy Protona (`steamapps/compatdata/*/pfx/drive_c/users/*/AppData/Roaming/EldenRing`), `~/.wine`,
Lutris (`~/Games/*`), Heroic i Bottles, i dla każdego pliku wybiera najświeższy. Typowy przypadek: Seamless Coop
dodany do Steama jako gra spoza Steama dostaje własny `compatdata/<numer>`, więc `.co2` jest w innym prefiksie niż `.sl2`
(test: `backend/tests/test_savedirs.py`).

## Atrybuty (`stats` w `/api/state`)

Z PlayerGameData (zaraz za mapą GaItem, `savefile.parse_stats`): `+0x08` PŻ (bieżące, max, bazowe max), `+0x14` PS,
`+0x24` wytrzymałość, `+0x34` 8 × u32 atrybuty, `+0x60` poziom, `+0xF4` u8 błogosławieństwo Ostrodrzewa (0–20),
`+0xF5` u8 błogosławieństwo prochów czcigodnych (0–10), `+0xF9`/`+0xFA` u8 butelki szkarłatne / modre (suma 4 na
starcie, 14 z kompletem złotych nasion), `+0xBD` u8 kamienie pamięci (0–8), `+0xBE` u8 dodatkowe sloty talizmanów (0–3). Kontrola: suma atrybutów − 79 = poziom (inaczej
`attributes: null`).

```json
"stats": {"attributes": {"vigor": 60, "mind": 42, "endurance": 54, "strength": 32, "dexterity": 16,
          "intelligence": 27, "faith": 10, "arcane": 18}, "level": 180,
          "hp": {"current": 1900, "max": 1900, "base_max": 1900}, "fp": {...}, "stamina": {...},
          "scadutree_blessing": 9, "revered_spirit_ash_blessing": 5, "flasks": {"crimson": 12, "cerulean": 2},
          "memory_stones": 8, "talisman_slots_added": 3}
```

Miękkie progi liczy frontend z krzywych gry (`assets/data/stat_curves.json`, `tools/extract/extract_curves.py`, docs/08).

## Portrety postaci (zdarzenie SSE `portrait`)

`erbackend/portraits.py`: po zmianie slotu (i przy starcie dla brakujących) liczony jest podpis = id czterech części zbroi (hełm, tułów,
ręce, nogi) + skrót bloku `FACE` + wersja renderera (`render_character.py --version`, skrót plików renderu z `export_model.RENDER_FILES`), więc
po aktualizacji renderera portrety odświeżają się przy starcie. Gdy różni się od ostatniego renderu (`backend/var/portraits.json`) albo brak PNG, w wątku w tle uruchamia się
`tools/extract/render_character.py <plik> <slot>` (≈3 s: `char_<plik>_<slot>.png` z głową i `char_<plik>_<slot>_full.png`
z całą postacią w zbroi), potem zdarzenie:

```
event: portrait
data: {"file": "co2", "slot": 6, "head_id": 670000, "version": "670000:1a2b3c4d5e6f:c7c846a1bfbb"}
```

Frontend podmienia obrazek (`?v=<version>`). Render tylko czyta pliki gry i save; PNG zostaje lokalnie w `assets/renders/`.

## Flagi pokonania bossów: `extra_defeat_flags`

Bossowie dużej mapy zapisują śmierć pod flagą z prefiksem `12` zamiast `10` z `GameAreaParam`
(Radahn: 1052380800 → 1252380800, Borealis: 1054560800 → 1254560800; sprawdzone na wszystkich postaciach: flaga `10…`
nie jest ustawiana nigdy). `bosses.json` ma pole `extra_defeat_flags` (pokonany = flaga główna lub któraś dodatkowa;
także indeks kroniki). `alt_flags` znaczy co innego: tylko „odkryty” (np. pokonany w poprzednim cyklu NG).
Wariant `12…` dodawany jest tylko, gdy blok flagi istnieje w tabeli bst.

## Historia zapisów (baza `history.sqlite` w folderze użytkownika)

SQLite ze stdlib, plik `%LOCALAPPDATA%\Elden Map\history.sqlite` (Linux: `~/.local/share/elden-map/history.sqlite`); inna ścieżka: `--db`. Do wersji 0.1.6 baza leżała w `backend/var/` i ginęła
przy aktualizacji; przy pierwszym starcie nowej wersji jest stamtąd kopiowana (stary plik zostaje). Na Linuksie
szukamy jej też w folderach poprzednich wersji paczki obok bieżącej (`../elden-map-*/app/backend/var`), bierzemy najświeższą. Postać = plik + slot + imię
(nowa postać w tym samym slocie = nowa historia). Dla każdej postaci baza trzyma ostatni stan (flagi
skompresowane zlib), więc po restarcie serwera diff liczy się względem bazy, a zmiany zrobione, gdy serwer
nie działał, też trafią do kroniki (z czasem ostatniego zapisu pliku). Pierwsza obserwacja postaci to „baseline”:
nic nie trafia do kroniki (nie wiemy, kiedy co zdobyto).

Tabele: `characters`, `last_state`, `snapshots` (każdy zaobserwowany zapis: poziom, śmierci, czas gry, mapa,
pozycja; z nich liczone są sesje i dni), `events` (kronika), `deaths`.

Przedmioty zdobyte bez flagi (kupione, z przeciwników, wytworzone): `last_state` trzyma spis posiadanych przedmiotów
(`kategoria:id`, broń po ID bazowym). Klucz, którego wcześniej nie było, daje zdarzenie `item_obtained` (`ref_id` =
klucz, nazwę dopisuje strona z katalogu). Przedmioty ze skarbu podniesionego w tym samym zapisie pomijamy, bo mają
już `item_collected`. Gdy poprzednia migawka nie ma spisu (baza sprzed tej zmiany), zdarzeń nie ma.

`GET /api/days?file=&slot=&limit=7&before=RRRR-MM-DD`: kronika dzień po dniu, od najnowszego. Dzień trwa od 4:00
do 4:00 (granie po północy należy do poprzedniego dnia). Każdy dzień: `date`, `saves`, `events[]` i to samo
podsumowanie co sesja (`playtime_s`, `deaths`, `levels`, `runes_gained`, `bosses`, `graces`, `items`,
`items_obtained`, `quest_steps`, `maps`, `death_points`), liczone od ostatniego zapisu przed tym dniem. `more`: są
starsze dni (następna strona: `before` = data najstarszego). Zdarzenia zrobione, gdy aplikacja nie działała, mają
czas zapisu pliku save, więc mogą trafić do innego dnia.

## Miejsca śmierci i próby na bossa

Plama krwi (`blood_stain`, 0x44 B): za listą regionów jest koń (0x28 B), 1 bajt (na wszystkich
save'ach = 1, także u postaci bez śmierci, więc to nie jest „has_bloodstain”), potem struktura:

| Offset | Co | Pewność |
|---|---|---|
| `+0x00` | `float[3]` X, Y, Z (lokalne, jak PlayerCoordinates) | zweryfikowane (Ser Davick: plama na m31_03 = mapa, na której stoi) |
| `+0x0C` | `float[4]` obrót | prawdopodobnie |
| `+0x30` | i32 ? (0 albo −1) | ? |
| `+0x34` | i32 runy na plamie (−1 = brak / odzyskane) | średnia (wartości 6222, 101801) |
| `+0x38` | MapID `[DD, CC, BB, AA]` (`0xFFFFFFFF` = brak plamy, postać bez śmierci) | zweryfikowane |

Rejestracja śmierci (przy każdym zapisie): gdy licznik śmierci wzrósł albo plama krwi się przesunęła
(inna mapa lub > 5 cm) → wiersz w `deaths` z pozycją plamy (gdy się przesunęła) albo `position: null`.

Próby (`bosses[].attempts`) = liczba zarejestrowanych śmierci (z pozycją) na arenie bossa,
z czasem ≤ czas pokonania (zdarzenie `boss_defeated` w kronice). Arena pochodzi z `bosses.json`:
`arena: {map_id, x, y, z, radius, match, confidence, sources}`:
- `x` i `radius` podane (`match: "radius"`) → śmierć musi być w promieniu `radius` od `(x, y, z)`: lokalnie na tej
  samej mapie, a w otwartym świecie (m60/m61) przez współrzędne świata, więc śmierć na sąsiednim kaflu też się liczy,
- `x = null` (`match: "map"`) → liczy się każda śmierć na tej mapie.

`attempts: null`, gdy boss nie ma areny albo padł, zanim backend zaczął obserwować postać (czas pokonania nieznany).
Stan danych (2026-11-24): arenę ma 208 z 209 bossów (pozycja wroga z pliku mapy o EntityID = flaga pokonania;
5 zapasowo z `GameAreaParam +0x48`). Bez pozycji: Dryleaf Dane (tylko z tabeli CE).

- 158 bossów ma granice areny z gry (`match: "region"`): region pliku mapy (MSB, `POINT_PARAM_ST`), w którego
  nazwie jest „バディ”, czyli obszar przyzywania popiołów ducha w walce z bossem (np. „領域 ボス 接ぎ木の王 バディ起動範囲00”
  = „obszar bossa Godrick, zasięg przyzwania ducha”). U 149 pozycja bossa leży w tym regionie (pewność `high`),
  u 9 region jest < 40 m od bossa (`medium`). `arena.region = {shape, x, y, z, rot_y, dims}`:
  `rect` (szer. × głęb. po obrocie o `rot_y` stopni; wysokość przyjęta −10…+40 m), `box` (+ wysokość),
  `cylinder` (promień, wysokość), `circle`, `sphere`. Śmierć liczy się, gdy plama krwi leży w regionie (margines 3 m);
  w otwartym świecie punkt z sąsiedniego kafla jest przeliczany na układ kafla areny.
  Kierunek obrotu sprawdzony na danych: smok Adula (prostokąt 360×120 m, obrót 120°) jest w środku regionu tylko
  przy przyjętym kierunku (przy odwrotnym jest 56 m poza nim).
- 50 bossów ma promień 60 m od miejsca bossa (`match: "radius"`). To bossowie bez takiego regionu (głównie polowi
  w otwartym świecie). Promień to przybliżenie.

## Tryb bez spoilerów (`discovered`)

Każdy boss / łaska / przedmiot / quest w `/api/state` ma `discovered` (bool) i `discovered_by` (powód albo `null`):

| `discovered_by` | kiedy |
|---|---|
| `defeated` / `visited` / `collected` / `started` | wpis już zaliczony (quest: którykolwiek krok zrobiony) |
| `flag` | ustawiona któraś z `discover.flags` wpisu (np. flaga spotkania) |
| `alt_flag` | boss: ustawiona flaga z `alt_flags` (np. 61xxx = pokonany w poprzednim cyklu NG) |
| `nearby_grace` | odwiedzona łaska na tej samej mapie co wpis (`map_id` / `map_ids`; w otwartym świecie = ten sam kafel 256 m, w lochu = cały loch) albo któraś z łask `discover.graces` |
| `area_grace` | odwiedzona łaska w tym samym podregionie menu podróży (`subregion`, np. „Burzowe Wzgórze”, „Zamek Ensis”; dla łask DLC z tabeli CE też ich `area`). Do 2026-11-24 porównywana była cała kraina. `discover.areas` nadpisuje. Skarby tej reguły nie używają |
| `map_visited` | gracz był na mapie wpisu, mapie z `discover.maps` albo mapie areny (mapy z historii zapisów, pozycja, plama krwi) |

Przedmioty bez mapy (osełki, popioły wojny z tabeli CE) są odkryte dopiero po zdobyciu.
Opcjonalne pole w danych: `discover: {flags: [...], graces: ["grace-…"], areas: ["…"], maps: ["mAA_BB_CC_DD"]}`
(na razie nieużywane w wygenerowanych danych, działają reguły domyślne).
Prawdziwy przykład (boink, dane świata): bossowie: 157 `defeated`, 17 `nearby_grace`, 13 `area_grace`,
26 nieodkrytych; łaski: 327 `visited`, 9 `nearby_grace`, 13 `area_grace`, 70 nieodkrytych; przedmioty: 2146
`collected`, 533 `nearby_grace`, 784 nieodkryte.

### Reguła frontendu dla bossów (2026-11-23)

Frontend nie odsłania bossa za `area_grace` (dowolna łaska w krainie; jedna łaska w Liurni odsłaniała 28 bossów).
Boss jest znany, gdy: pokonany · `discovered_by` ∈ {`nearby_grace`, `map_visited`, `flag`, `alt_flag`} · `attempts > 0` ·
odkryta łaska w promieniu ~300 m od bossa · śmierć w promieniu ~150 m. Powód widać w szczegółach bossa
(„odkryty: łaska w pobliżu”). Przykład: BOINK, 158 pokonanych, 28 znanych żywych, 22 ukrytych.

## Regiony i krainy

Źródło: pliki gry, `backend/tools/extract_world_extras.py` → `backend/data/world_extras.json` (+ poprawiony
`tools/extract/extract_data.py` → `assets/data/graces.json`).

- Kraina / podregion łaski = zakładka / podkategoria menu podróży: `BonfireWarpParam +0x14` = id podkategorii,
  `BonfireWarpSubCategoryParam` (+0x04 tekst, +0x08 u16 id zakładki), `BonfireWarpTabParam` (+0x04 tekst), nazwy
  z `GR_MenuText` (menu.msgbnd). 19 krain: Pogrobno, Jeziorna Liurnia, Płaskowyż Altus, Caelid, Szczyty Olbrzymów,
  legacy dungeony (Zamek Burzowego Całunu, Leyndell…), podziemia, DLC: Cmentarna równina, Ostrowyż Altus, Ziemie
  Wieży, Donżon cienia. Katakumby i jaskinie należą do krainy, w której leżą.
  (Wcześniej `assets/data/graces.json` brał `+0x14` za ID nazwy miejsca (stąd przypadkowe „regiony”) i liczył
  `dlc` z ID wiersza; oba błędy poprawione u źródła 2026-11-24: łask DLC jest teraz 105, jak w tabeli CE.)
- Kraina bossa / skarbu = kraina najbliższej łaski: na tej samej mapie (lokalnie), inaczej przez współrzędne
  świata. Dla bossów pole `region_pl` = `region` (dawniej niespójne, np. Godrick „Limgrave” / „Jeziorna Liurnia”).
- `regions_unlocked` to ID wierszy `PlayRegionParam` (531 z 535 ID z save'ów użytkownika). Struktura ID:
  `61–65 xx yyy` Ziemie Pomiędzy (kraina = zakładka AA·1000, podregion AA·1000+xx, np. 6101000 → Burzowe Wzgórze),
  `68/69 xx yyy` Królestwo Cienia (podregion = ID // 1000, np. 6820000 → Zamek Ensis), `AA BB yyy` lochy
  (mapa `mAA_BB`; nazwa z `WorldMapPointParam`, `PlaceName` AABB00 albo łaski na mapie). Mapy bez nazwy/krainy
  w tych źródłach opisuje `MAP_OVERRIDES` w `backend/tools/extract_world_extras.py`: m12_08 / m12_09 = areny duchów
  przodków („Świątynia Poroża”, PlaceName 6654604; Rzeka Siofra / Nokron), koloseum m45_00/01/02 → Leyndell /
  Pogrobno / Caelid. Bez nazwy zostaje tylko m42_01 („Nienazwany obszar m42_01”, kuźnia DLC bez nazwy w grze).
  Podział na podregion w krainach świata jest wywnioskowany z numeracji (sprawdzony na save'ach: postać poz. 13 ma
  „Burzowe Wzgórze”, „Katakumby Burzowego Podnóża”, „Jaskinia w zagajniku”, zgodnie z tym, gdzie była).

## Ostrzeżenia „zanim zabijesz…” (`warnings`)

Quest w `quests.json` może mieć `locks: [{boss_id, step, warning}]`. Ostrzeżenie jest aktywne, gdy:
quest niedokończony, boss `boss_id` żyje oraz (jeśli podano `step`) krok `step` nie jest jeszcze zaliczony
(`step` = krok, który trzeba zrobić przed zabiciem bossa; po jego zaliczeniu blokada znika).

```json
"warnings": [
  {"quest_id": "q1", "quest": "…", "npc": "…", "boss_id": "…", "boss": "…", "step_id": "s2",
   "warning": "Najpierw skończ quest — zabicie bossa go przerwie.", "warning_safe": null}
]
```
Stan danych: 2 blokady z `assets/data/quests.json`: Tanith/Rykard (`boss-16000800`) i Millicent/Malenia
(`boss-15000800`). Na save'ach użytkownika aktywne np. u `prophet` (1), `Ser Davick` i `chuj` (po 2).

## Różnice względem szkicu kontraktu z makiety

Szkic: `state = {character:{slot,name,level,playtime_s,runes_memory,deaths,last_grace}, position:{map_id,x,y,z}, regions_unlocked, bosses:[{id,name,region,defeated,dlc}], graces:[{id,name,region,visited}], items:[{id,name,category,collected}], quests:[{id,name,npc,steps:[{text,done}]}], progress, save:{file,written_at}}`. Wszystkie te pola są, z tymi zmianami:

| Zmiana | Dlaczego |
|---|---|
| `character.last_grace` to obiekt `{entity_id, grace_id, name, map_id}`, a nie tekst (makieta: `"Kościół Elleh"`) | nazwa jest w `last_grace.name` |
| `position.global` (dodatkowe, `null` poza m60/m61) | współrzędne do mapy świata; wzór niezweryfikowany |
| dodatkowe: `map_id`, `bosses[].location/required/hints/confidence`, `graces[].area/dlc`, `items[].dlc/location`, `quests[].dlc/completed/next`, `steps[].id`, `save.path/slot_md5/is_active` | potrzebne do UI / cache |
| `save.file` to `"sl2"`/`"co2"` (makieta: `"ER0000.sl2"`) | ten sam identyfikator co parametr `file`; `seconds_ago` licz z `written_at` |
| `regions_unlocked` to surowe ID liczbowe; nazwy w osobnym `regions:[{id,name,region,subregion,map_id,kind}]` (od 2026-11-24) | zgodność wstecz |
| `equipment` + `character.body_type/archetype/starting_gift` (dodane 2026-11-23) | „aktualna postać” jak na ekranie wczytywania |
| `inventory` (dodane 2026-11-23): `goods` + osobne `key_items`; w każdym wpisie `count` (przy sobie) i `storage` (skrzynia) | „co gracz posiada”, nie tylko co podniósł z mapy |
| dodane po rozszerzeniu zakresu (2026-11-23): `bloodstain`, `warnings`, `*.discovered/discovered_by`, `bosses[].attempts`; endpointy `/api/deaths`, `/api/session`; zdarzenie SSE `chronicle`; w `save`: `bloodstain`, `map_changed` | kronika, miejsca śmierci, tryb bez spoilerów, ostrzeżenia, podsumowanie sesji |
| `bosses[].hints` to jeden tekst albo `null` (makieta: `how: [...]`, `drops`, `attempts`, `runes`, `x`, `y`) | tych danych nie ma w save'ie ani w rzetelnych źródłach, które mamy |
| ID bossów zmienione na `boss-<flaga>` (wcześniej slugi, np. `messmer-the-impaler`; stary slug jest w `bosses.json` jako `legacy_id`) | 213 bossów, nazwy się powtarzają (np. dwa Tańczące Lwy) |
| nazwy bossów, łask, skarbów i questów po polsku (z plików gry); `name_en` obok (nie dla wszystkich łask) | dane świata |
| osełki/popioły z tabeli CE mają nazwy angielskie | brak ich w danych świata (poza skarbami) |

## Warstwa danych

Pliki `backend/data/*.json`, generowane przez `backend/tools/build_data.py`. Wspólny kształt:

```json
{"_meta": {"schema_version": 1, "kind": "bosses", "generated_by": "backend/tools/build_data.py",
           "sources": {"ct-hexinton": {"title": "...", "url": "...", "license": "..."}, "...": {}},
           "confidence_levels": {"verified": "...", "high": "...", "medium": "...", "low": "..."},
           "coverage": "co jest, a czego brakuje"},
 "entries": [ ... ]}
```

Każdy wpis: `id` (unikalny slug), `name`, `sources` (klucze z `_meta.sources`), `confidence`, `notes` (lub `null`).

| `confidence` | znaczenie |
|---|---|
| `verified` | dwie niezależne flagi zgadzają się na save'ach (flaga mapy …800 + globalna flaga bossa 9xxx/61xxx) albo potwierdzone w grze |
| `high` | flaga z tabeli CE i spójne zachowanie na 7 postaciach |
| `medium` | wyprowadzone (konwencja numeracji / tylko sprawdzenie save'a), możliwa pomyłka |
| `low` | niepotwierdzone |

Źródła: `world-data` (dane świata z plików gry w `assets/data/`, generowane przez `tools/extract/run_all.py`;
opis pól w docs/10-world-data.md), `game-files` (`backend/data/world_extras.json` z
`backend/tools/extract_world_extras.py`: pozycje bossów, nazwy regionów, konwersja lochy → świat), `ct-hexinton`, `save-verified`, `flag-convention`, `general-knowledge`
oraz źródła questów (`regulation`, `tga-ct`, `npc-block`, `talk-esd`). Generator łączy dane świata z wpisami
z tabeli CE po fladze (kuratorowane pola `hints`, `alt_flags`, `required` i `confidence: verified` zostają).
Po przebudowaniu `assets/data/` uruchom `python backend\tools\extract_world_extras.py`, potem
`python backend\tools\build_data.py` i zrestartuj serwer.

`bosses.json`: `{id, name, name_en, region, subregion, region_pl, location, defeat_flag, alt_flags[], extra_defeat_flags[], arena, dlc, required,
hints, runes, map_id, world_id, remembrance, sources, confidence, notes, legacy_id}` (+ opcjonalnie `discover`)
```json
{"id": "boss-21010800", "name": "Messmer Palownik", "name_en": "Messmer the Impaler", "region": "Scadu Altus",
 "region_pl": "Donżon cienia", "location": "Shadow Keep", "defeat_flag": 21010800, "alt_flags": [9146, 61146],
 "arena": null, "dlc": true, "required": true,
 "hints": "Szczyt Shadow Keep — przez Specimen Storehouse w górę do Dark Chamber Entrance. Daje Messmer's Kindling.",
 "runes": 400000, "map_id": "m21_01_00_00", "world_id": 21010800, "remembrance": "Wizerunek Palownika",
 "sources": ["world-data", "ct-hexinton", "save-verified", "general-knowledge"], "confidence": "verified",
 "notes": null, "legacy_id": "messmer-the-impaler"}
```
`alt_flags`: inne flagi tego samego bossa (9xxx = pokonany w bieżącym cyklu NG, 61xxx = kiedykolwiek;
obserwacja z save'ów: postać w NG+ ma 61xxx bez 9xxx). Status liczony jest tylko z `defeat_flag`.
`arena` (dla `attempts`): `{map_id, x, y, z, radius: 60, match: "region"|"radius", region?, region_name?, confidence,
sources: ["game-files"]}`. `x/y/z` = miejsce bossa, `region` = granice areny z pliku mapy (158 bossów), inaczej
promień (patrz „Miejsca śmierci i próby na bossa”). Kraina bossa bez łaski w pobliżu: z PlayRegion mapy lochu,
z nazwy w danych świata (zakładka/podkategoria menu) albo z regionu tabeli CE. Każdy boss ma `subregion`.
Bossowie bez nazwy w plikach gry dostają polską nazwę gatunku od innego bossa + podregion (np. „Smok ognia duchów
(Ostrowyż Altus)”); strona pokazuje tę samą listę 209 bossów co backend.
`required: true` (10): Morgott, Ognisty olbrzym, Duet boskiej skóry, Sir Gideon, Godfrey/Hoarah Loux (m11_05),
Bestialski Duchowny/Maliketh (13000800), Radagon/Bestia Eldeńska (19000800), Messmer, Romina, Radahn (DLC).

`graces.json`: `{id, name, name_en, region, subregion, area, flag, dlc, map_id, position:{x,y,z}, pos, entity, last_grace_id, sources, confidence, notes}`.
`last_grace_id = entity + 1000` to wartość, którą save trzyma jako ostatnią łaskę. `region`/`subregion` = kraina
i podregion z menu podróży. `dlc` liczone z MapID (DLC = m61 oraz m20–m28, m40–m43); od 2026-11-24 zgodne też
z poprawionym `assets/data/graces.json`. Pominięte 3 łaski bez nazwy (flagi 200, 71260, 71261).

`items.json`: `{id, name, name_en, category, kind, flag, dlc, region, subregion, location, map_id, map_ids[], lots[], contents[{cat, id, count}], hints, sources, confidence, notes}`.
`kind: "map_lot"` to skarb z mapy, `id = item-<flaga>`, `contents` = przedmioty w skarbie (ID zgodne z `inventory`);
loty o tej samej fladze (np. Leyndell i Leyndell w popiele) są połączone (`map_ids`, `lots`).
`kind: "acquired_flag"` to osełki/popioły z tabeli CE (flaga „zdobyto”, bez miejsca); pominięte, gdy ta sama flaga jest skarbem.
Nazwy po polsku z katalogu `assets/data/items.json` (dopasowanie po nazwie angielskiej; 1 popiół bez odpowiednika
zostaje po angielsku). `region`/`subregion` skarbów = kraina najbliższej łaski.

`quests.json` powstaje z `assets/data/quests.json` (przepisane prawie 1:1): `{id, name, npc, npc_en, dlc, region, icon, missable,
steps:[{id, text, flags:[...], mode:"all"|"any", where, next, sources}], locks:[{boss_id, boss_en, boss_flag, step, warning}],
sources, confidence, notes, verification, npc_block}` (+ opcjonalnie `discover`). `locks[].boss_id` generator ustawia
na id z `bosses.json` (po `boss_flag`, a gdy go brak, po jednoznacznym `boss_en`).
Krok zaliczony, gdy wszystkie (`all`, domyślnie) / którakolwiek (`any`) z `flags` jest ustawiona.
`next` = tekst „co dalej” pokazywany, gdy ten krok jest pierwszym niezaliczonym (domyślnie `text`).

### Stan danych (2026-11-24) po przebudowie danych świata: 209 bossów, 419 łask, 3441 przedmiotów, 46 questów

Tabela poniżej pochodzi z 2026-11-23 (liczby sprzed przebudowy danych świata).

### Stan danych (2026-11-23, 19:40)

| Plik | Wpisów | Źródło | Pewność |
|---|---|---|---|
| bosses.json | 213 (170 gra podstawowa + 43 DLC) | 212 z danych świata + Dryleaf Dane z tabeli CE | 20 `verified`, 189 `high`, 3 `medium`, 1 `low` |
| graces.json | 419 (314 + 105 DLC) | dane świata; 105 DLC zgadza się z tabelą CE | `high` |
| items.json | 3458: 3336 skarbów z map + 122 osełek/popiołów z tabeli CE | dane świata + tabela CE | skarby `high`, popioły `medium` |
| quests.json | 46 | dane świata (regulation + TGA CT + blok flag NPC) | wg pliku: `verified` / `high` / `medium` / `low` |

Sprawdzenie na save'ach (co2): finali 153/170 + 40/43 bossów (43. to Dryleaf Dane), 2840/3336 skarbów, 10/10
obowiązkowych; boink 147/170 + 10/43; chuj 1/170. Zgodne z pomiarem sesji generującej dane świata.

Pominięte z tabeli CE: flaga 65600 (ustawiona u każdej postaci od startu, więc to nie podniesienie przedmiotu),
65885 „No Skill”, grupy „Buildings”, „Unlock Arena(s)”, „Events”, flagi techniczne bossów (np. 2200).

## Czego brakuje (następne kroki)

Uzupełnione 2026-11-24: pozycje aren (208/209 bossów), spójne krainy bossów/łask/skarbów, nazwy `regions_unlocked`,
weryfikacja `position.global` + piksele mapy (`position.map`), poprawka `dlc` i krain w `assets/data/graces.json`,
polskie nazwy popiołów. Zostaje:

1. `active_weapon.arm_style` i `body_type`: znaczenie wartości do potwierdzenia w grze (zmiana chwytu / wyglądu
   i porównanie save'ów).
2. 50 bossów bez regionu areny w pliku mapy; tam próby liczone w promieniu 60 m (przybliżenie).
3. m42_01 bez nazwy w grze; Dryleaf Dane bez pozycji (tylko z tabeli CE, flaga niepotwierdzona).
4. Działanie na żywo (zdarzenia SSE, kronika, sesja, próby) sprawdzone tylko na podmienianych kopiach save'a.
   Do potwierdzenia podczas prawdziwej gry.
