# elden-map — backend

Lokalny serwer (Python 3, **tylko biblioteka standardowa**), który czyta plik save Elden Ring
(`ER0000.sl2` / `ER0000.co2`) **wyłącznie do odczytu** i wystawia API JSON + Server-Sent Events.
Nie dotyka procesu gry (bezpieczne z EasyAntiCheat). Kontrakt API: [docs/07-backend-api.md](../docs/07-backend-api.md).

## Uruchomienie

Z katalogu projektu (`elden-map/`):

```powershell
python backend\server.py
```

Serwer startuje na `http://127.0.0.1:8765` i sam znajduje folder save'a
(`%APPDATA%\EldenRing\<SteamID64>`, ten z najświeższym plikiem). Opcje:

| Opcja | Domyślnie | Co robi |
|---|---|---|
| `--port N` | `8765` | port HTTP |
| `--host` | `127.0.0.1` | tylko adresy loopback (`::1`, `localhost`) — inne są odrzucane |
| `--save-dir DIR` | auto | folder z `ER0000.sl2` / `.co2` (np. kopia do testów) |
| `--poll S` | `0.5` | co ile sekund sprawdzać folder (os.stat) |
| `--bst PATH` | `docs/data/er-save-lib/eventflag_bst.txt` | mapa ID flagi → bajt/bit |
| `--data-dir DIR` | `backend/data` | pliki `bosses/graces/items/quests.json` |
| `--db PATH` | `backend/var/history.sqlite` | baza historii (kronika, śmierci, sesje); `var/` jest w `.gitignore` |
| `-v` | — | logi debug (każde żądanie HTTP) |

Szybki test: <http://127.0.0.1:8765/api/health>, <http://127.0.0.1:8765/api/state>.

## Testy

```powershell
python -m unittest discover -s backend\tests -v
```

Testy kopiują save'y do katalogu tymczasowego (`tempfile.mkdtemp`) i tylko tam je modyfikują
(podmiana pliku jak przy zapisie gry, z przeliczonym MD5). Do folderu save'ów gry nic nie jest
pisane — pilnuje tego `tests/helpers.py::assert_not_game_dir`; baza historii w testach też leży
w katalogu tymczasowym (nie w `backend/var`). Źródło save'ów: zmienna `ER_SAVE_DIR`
albo automatycznie `%APPDATA%\EldenRing\<SteamID>`; bez save'ów testy na plikach są pomijane.

## Struktura

```
backend/
  server.py              punkt wejścia (argparse, logowanie)
  erbackend/
    savefile.py          parser BND4 / profil / slot (MD5, ponawianie odczytu, tylko odczyt)
    inventory.py         ekwipunek (przy sobie + skrzynia) z GaItem
    equipment.py         założony ekwipunek + klasa/dar startowy z profilu
    worldmap.py          pozycja lokalna -> świat -> piksele mapy strony; nazwy regionów (PlayRegion)
    flags.py             ID flagi -> (bajt, bit), diff bloków flag
    gamedata.py          ładowanie data/*.json, statusy (pokonany/odwiedzona/zebrany/krok questa)
    diffing.py           migawka slotu (Snap) + diff dwóch zapisów (zdarzenie SSE 'save')
    history.py           SQLite: kronika, miejsca śmierci, próby na bossa, sesje
    service.py           cache save'ów, aktywny plik/slot, watcher folderu, stan, historia
    server.py            ThreadingHTTPServer: REST + SSE, CORS dla localhost
  data/                  bosses.json, graces.json, items.json, quests.json (generowane)
  tools/extract_world_extras.py  z plików gry: pozycje bossów, nazwy regionów, konwersja lochy->świat
                                 (-> data/world_extras.json; korzysta z tools/extract, tylko odczyt)
  tools/build_data.py    generator data/*.json z assets/data, world_extras.json i tabeli CE
  tests/                 unittest
  var/                   history.sqlite (tworzone przy starcie, nie commitować)
```

## Dane (`backend/data`)

Pliki są generowane (poprawki rób w generatorach). Po przebudowie `assets/data/` (`tools/extract/run_all.py`):
`python backend\tools\extract_world_extras.py`, potem `python backend\tools\build_data.py`, potem restart serwera.
Każdy plik ma `_meta` (źródła, poziomy pewności, zakres) i `entries`. Każdy wpis ma `sources`
(klucze z `_meta.sources`) i `confidence` (`verified` / `high` / `medium` / `low`).
Szczegóły schematu — w [docs/07-backend-api.md](../docs/07-backend-api.md#warstwa-danych).

## Jak działa wykrywanie zapisu

Wątek co 0,5 s robi `os.stat` obu plików. Po zmianie `mtime` czeka, aż przestanie się zmieniać
(debounce 0,4 s), czyta cały plik do pamięci, sprawdza MD5 wszystkich wpisów (przy niezgodności
ponawia do 15 razy co 0,2 s), porównuje MD5 slotów z poprzednim odczytem i dla zmienionych slotów
liczy diff flag. Aktywny plik/slot = ostatnio zapisany. Na starcie: plik z najnowszym `mtime`,
slot = „ostatnio wczytana postać” z profilu (`USER_DATA010 + 0x1334`).
Opóźnienie backendu od zapisu pliku do zdarzenia SSE: ~0,5–1 s (zmierzone w teście: 0,96 s).
Do tego dochodzi opóźnienie samej gry (zapis co ~60 s, mediana ~28 s — patrz docs/04).

## Historia (kronika, śmierci, sesje)

Każdy zaobserwowany zapis slotu trafia do `backend/var/history.sqlite`: migawka (poziom, śmierci, czas gry,
mapa), zdarzenia kroniki (boss / łaska / przedmiot / krok questa / poziom / zmiana obszaru) i miejsca śmierci
(z plamy krwi). Baza pamięta ostatni stan każdej postaci, więc po restarcie serwera zmiany zrobione w tym czasie
też trafią do kroniki. Pierwsze zobaczenie postaci to tylko punkt odniesienia (bez wpisów w kronice).
Żeby zacząć historię od zera, zatrzymaj serwer i usuń `backend/var/`.
Endpointy: `/api/chronicle`, `/api/deaths`, `/api/session` — opis w docs/07.
