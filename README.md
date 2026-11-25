<div align="center">

# ⟡ Elden Map

**Twój postęp w Elden Ring na żywo — mapa, bossowie, questy, przedmioty i kronika wyprawy.**

Lokalna strona, która czyta plik zapisu gry (tylko do odczytu) i po każdym zapisie od razu pokazuje,
co już zrobiłeś, a co jeszcze przed tobą. Działa z oficjalną grą online (EasyAntiCheat), z Seamless Coop
i offline. Windows i Linux (Steam + Proton).

`Python 3.11+` · `Node.js 18+` · bez frameworków, bez kont, bez chmury — wszystko na `127.0.0.1`

</div>

---

## Spis treści

- [Co potrafi](#co-potrafi)
- [Jak to działa](#jak-to-działa)
- [Wymagania](#wymagania)
- [Szybki start — Windows](#szybki-start--windows)
- [Szybki start — Linux](#szybki-start--linux)
- [Uruchamianie na co dzień](#uruchamianie-na-co-dzień)
- [Konfiguracja](#konfiguracja)
- [Rozwiązywanie problemów](#rozwiązywanie-problemów)
- [Struktura projektu](#struktura-projektu)
- [Dla programistów](#dla-programistów)
- [Prawa i dane](#prawa-i-dane)

---

## Co potrafi

| Widok | Co pokazuje |
|---|---|
| 🧍 **Postać** | Portret 3D głowy z twojego save'a (twarz, włosy, kolory, założony hełm) · ekwipunek · atrybuty z **miękkimi progami z plików gry** (podświetlenie „blisko progu”, tabela przyrostów po najechaniu) · obciążenie |
| 🗺️ **Mapa** | Prawdziwa mapa z gry (Ziemie Pomiędzy i Królestwo Cieni) · łaski, bossowie, NPC, lochy, ~3400 skarbów w kategoriach · filtry · wyszukiwanie · twoja pozycja i miejsca śmierci |
| ⚔️ **Bossowie** | 200+ bossów z ikonami lub portretami 3D · rangi (Wielki run, Legenda, Wielki boss… „Ledwo boss”) · grupowanie, sortowanie, panel krain z postępem · nagrody · najbliższa łaska *przed* areną |
| 📜 **Questy** | Kroki odhaczane z flag zapisu · „co dalej” · zagnieżdżone wątki · ostrzeżenia „zanim zabijesz…” · **teksty bez spoilerów** do czasu wykonania kroku |
| 🎒 **Przedmioty** | Kolekcja z ekwipunku w save'ie · ramki **rzadkość × żywioł** (np. legendarny + mróz) · statystyki · „**Jak zdobyć**”: boss, kupiec z ceną, wymiana, łup z przeciwnika (szansa), nagroda ze zdarzenia |
| 📖 **Kronika** | Dziennik wyprawy pisany z kolejnych zapisów gry · podsumowanie sesji |

Wszystko jest połączone: z przedmiotu przejdziesz na mapę, do bossa albo questa — i z powrotem.
**Tryb bez spoilerów** ukrywa bossów, których jeszcze nie spotkałeś, i rzadkie przedmioty, których nie masz.

## Jak to działa

```
  Elden Ring ──(autozapis)──▶ ER0000.sl2 / .co2
                                   │  tylko odczyt (os.stat + kopia w pamięci)
                                   ▼
                     backend/server.py  ── API JSON + Server-Sent Events ── 127.0.0.1:8765
                                   │                                    │
   pliki gry ──(prepare.py, raz)──▶ assets/  (mapa, ikony, dane świata) │
                                   ▼                                    ▼
                          strona  mockup/  ◀───────── odświeża się sama po każdym zapisie
```

- **Nie dotyka procesu gry** — tylko plik zapisu. Bezpieczne z EasyAntiCheat (granie online).
- **Nic nie zapisuje do plików gry ani save'ów.** Historia (kronika, śmierci) leży w `backend/var/`.
- Dane świata (bossowie, przedmioty, mapa, ikony) są **wyciągane z twojej kopii gry** — repozytorium
  nie zawiera żadnych plików FromSoftware.

## Wymagania

| | Windows | Linux |
|---|---|---|
| Gra | Elden Ring ze Steama (DLC opcjonalne) | Elden Ring ze Steama przez **Proton** |
| Python | 3.11+ (zalecany **3.14**) | 3.11+ (zalecany **3.14**) |
| Node.js | 18+ (budowa kafli mapy, ikon i portretów) | 18+ |
| Pakiety Python | — (używa `bcrypt.dll` i DLL Oodle z gry) | `pip install -r requirements.txt` |
| Miejsce | ok. 3 GB na `assets/` | ok. 3 GB |

Przeglądarka: dowolna nowoczesna (Chrome, Firefox, Edge).

## Szybki start — Windows

PowerShell:

```powershell
git clone https://github.com/jurtomasz13/elden-map.git
cd elden-map
python -m pip install -r requirements.txt   # na Windows nic nie doinstaluje (poza zstandard dla Pythona < 3.14)
python prepare.py                           # jednorazowo: dane z gry (kilkanaście minut)
python start.py                             # backend + strona, otworzy przeglądarkę
```

Folder gry i save'y zostaną znalezione automatycznie (biblioteki Steama, `%APPDATA%\EldenRing`).

## Szybki start — Linux

```bash
git clone https://github.com/jurtomasz13/elden-map.git
cd elden-map
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt             # cryptography (AES) + kraken-decompressor (Oodle)
python prepare.py                           # jednorazowo: dane z gry (kilkanaście minut)
python start.py                             # backend + strona, otworzy przeglądarkę
```

**CachyOS / Arch Linux** — zależności systemowe (raz):

```bash
sudo pacman -S --needed git python nodejs npm base-devel   # base-devel: gdyby pip musiał skompilować dekoder Oodle
```

Arch blokuje `pip install` poza wirtualnym środowiskiem (PEP 668) — dlatego powyżej jest `venv`.
Steam z repozytorium (`steam`) i Proton (także `proton-cachyos`) są wykrywane automatycznie.

**Debian / Ubuntu / Mint:** `sudo apt install git python3 python3-venv nodejs npm build-essential`
· **Fedora:** `sudo dnf install git python3 nodejs npm gcc-c++`

Automatycznie przeszukiwane są biblioteki Steama: `~/.steam/steam`, `~/.local/share/Steam`,
Flatpak (`~/.var/app/com.valvesoftware.Steam/…`), Snap oraz wszystkie dodatkowe biblioteki z
`libraryfolders.vdf`. Save'y z Protona:

```
<biblioteka Steama>/steamapps/compatdata/1245620/pfx/drive_c/users/steamuser/AppData/Roaming/EldenRing/<SteamID64>/
```

> **Oodle na Linuxie.** Archiwa gry są kompresowane Oodle Kraken. Na Windowsie używana jest biblioteka
> z folderu gry; na Linuxie pakiet `kraken-decompressor` (otwarty dekoder ooz). Jeśli `prepare.py`
> zgłosi *„Unable to decompress”*, wskaż natywną bibliotekę Oodle:
> `export ER_OODLE_LIB=/ścieżka/do/liboo2corelinux64.so` — albo wykonaj `prepare.py` raz na Windowsie,
> skopiuj `assets/` i `backend/data/` na Linuxa i uruchom `python prepare.py --skip-extract`.

## Uruchamianie na co dzień

```bash
python start.py                    # http://127.0.0.1:5180/mockup/  (Ctrl+C kończy)
python start.py --no-browser       # bez otwierania przeglądarki
python start.py --save-dir "ŚCIEŻKA/do/folderu/z/ER0000.sl2"
```

Graj normalnie — po każdym autozapisie strona sama się odświeży (bossowie, łaski, przedmioty, kronika).
Aplikacja śledzi postać, której save zmienił się ostatnio; inną wybierzesz w nagłówku („zmień postać”).

Ręcznie, w dwóch terminalach (to samo co `start.py`):

```bash
python backend/server.py                                  # API na 127.0.0.1:8765
python -m http.server 5180 --bind 127.0.0.1               # strona: http://127.0.0.1:5180/mockup/
```

## Konfiguracja

| Zmienna / opcja | Do czego |
|---|---|
| `ER_GAME_DIR` | folder gry (`…/ELDEN RING/Game`), gdy nie wykrywa się sam |
| `ER_SAVE_DIR` lub `--save-dir` | folder z `ER0000.sl2` / `ER0000.co2` |
| `ER_OODLE_LIB` | (Linux) ścieżka do natywnej biblioteki Oodle zamiast `kraken-decompressor` |
| `python backend/server.py --help` | port, poll, ścieżki danych, logi debug |

`ER0000.sl2` to oficjalna gra, `ER0000.co2` — Seamless Coop. Obsługiwane oba, także wiele postaci.

## Rozwiązywanie problemów

<details>
<summary><b>„nie znaleziono folderu save'a”</b></summary>

Podaj go jawnie: `python start.py --save-dir "…/EldenRing/<SteamID64>"` albo ustaw `ER_SAVE_DIR`.
Komunikat błędu wypisuje wszystkie sprawdzone lokalizacje.
</details>

<details>
<summary><b>„Brak danych z gry” / pusta mapa</b></summary>

Uruchom `python prepare.py`. Ekstrakcja potrzebuje zainstalowanej gry; jeśli folder nie zostanie
znaleziony, ustaw `ER_GAME_DIR`.
</details>

<details>
<summary><b>Port 8765 lub 5180 jest zajęty</b></summary>

`python start.py --port 5190` zmienia port strony. Backend: `python backend/server.py --port 9000`
(strona domyślnie łączy się z 8765 — przy zmianie uruchamiaj ręcznie).
</details>

<details>
<summary><b>Linux: „Brak pakietu 'cryptography'” / „Brak dekompresora Oodle”</b></summary>

`pip install -r requirements.txt` w aktywnym `venv`. Dla Oodle zobacz notkę w
[Szybki start — Linux](#szybki-start--linux).
</details>

<details>
<summary><b>Strona nie odświeża się po zapisie</b></summary>

Gra zapisuje co jakiś czas (łaska, menu, pokonanie bossa). Status połączenia widać na dole menu po
lewej („na żywo · ER0000.co2 · slot N”). Sprawdź też <http://127.0.0.1:8765/api/health>.
</details>

## Struktura projektu

```
elden-map/
├─ start.py              # uruchamia backend + stronę
├─ prepare.py            # jednorazowe przygotowanie danych z gry
├─ requirements.txt      # tylko Linux / Python < 3.14
├─ mockup/               # strona (HTML/CSS/JS, Leaflet) — wszystkie widoki w app.js
├─ backend/              # serwer: odczyt save'a, API, SSE, kronika (tylko biblioteka standardowa)
│  ├─ erbackend/         #   parser save'a, flagi, ekwipunek, historia, portrety
│  ├─ tools/             #   budowa backend/data z danych świata
│  └─ tests/             #   testy (kopiują save'y do katalogu tymczasowego)
├─ tools/
│  ├─ extract/           # ekstrakcja z plików gry: archiwa BHD/BDT, DCX, params, MSB, EMEVD, FLVER, mapa, ikony
│  └─ fetch_community.py # pobiera dane społeczności (ER-Save-Lib, The Grand Archives)
└─ docs/                 # badania i formaty: save, pamięć, archiwa, mapa, questy, API
```

Generowane lokalnie (w `.gitignore`): `assets/`, `backend/data/*.json`, `backend/var/`, `docs/data/`.

## Dla programistów

```bash
python -m unittest discover -s backend/tests -v     # testy backendu (potrzebują save'ów: ER_SAVE_DIR)
python tools/extract/run_all.py                     # sama ekstrakcja z gry
python backend/tools/build_data.py                  # dane backendu z assets/data
```

Dokumentacja formatów i ustaleń: [docs/](docs/README.md) — m.in. [format save'a](docs/03-format-save.md),
[API backendu](docs/07-backend-api.md), [mapa i ikony](docs/08-assets.md), [dane świata](docs/10-world-data.md),
[questy](docs/09-quests.md).

## Prawa i dane

- **Elden Ring** i wszystkie zasoby gry (mapa, ikony, modele, teksty) należą do **FromSoftware / Bandai Namco**.
  Repozytorium ich nie zawiera — `prepare.py` czyta je z twojej legalnej kopii gry, wyłącznie do użytku lokalnego.
  Nie publikuj katalogu `assets/`.
- Dane społeczności pobierane przy instalacji (bez licencji, nie są tu kopiowane):
  [ClayAmore/ER-Save-Lib](https://github.com/ClayAmore/ER-Save-Lib) (`eventflag_bst.txt`),
  [The Grand Archives — Elden Ring CT](https://github.com/The-Grand-Archives/Elden-Ring-CT-TGA).
- Na Linuxie: [kraken-decompressor](https://pypi.org/project/kraken-decompressor/) (dekoder
  [ooz](https://github.com/powzix/ooz)) i [cryptography](https://pypi.org/project/cryptography/).
- Projekt fanowski, niezwiązany z FromSoftware ani Bandai Namco.
