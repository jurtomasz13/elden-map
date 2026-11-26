# Elden Map

Polska strona-towarzysz do Elden Ring. Pokazuje na żywo twój postęp: mapę, bossów, questy, przedmioty i kronikę
wyprawy.

Program działa lokalnie i tylko czyta plik zapisu gry. Po każdym zapisie strona od razu pokazuje, co już zrobiłeś,
a co jeszcze przed tobą. Działa z oficjalną grą online (EasyAntiCheat), z Seamless Coop i offline, na Windowsie
i na Linuxie (Steam + Proton).

[Pobierz najnowszą wersję](https://github.com/jurtomasz13/elden-map/releases/latest) dla Windowsa albo Linuxa.
Nie trzeba zakładać konta i nic nie trafia do chmury: wszystko działa na `127.0.0.1`.

## Spis treści

- [Co potrafi](#co-potrafi)
- [Jak to działa](#jak-to-działa)
- [Gotowa paczka](#gotowa-paczka)
- [Wymagania](#wymagania)
- [Ze źródeł na Windowsie](#ze-źródeł-na-windowsie)
- [Ze źródeł na Linuxie](#ze-źródeł-na-linuxie)
- [Uruchamianie na co dzień](#uruchamianie-na-co-dzień)
- [Konfiguracja](#konfiguracja)
- [Rozwiązywanie problemów](#rozwiązywanie-problemów)
- [Struktura projektu](#struktura-projektu)
- [Dla programistów](#dla-programistów)
- [Prawa i dane](#prawa-i-dane)

## Co potrafi

| Widok | Co pokazuje |
|---|---|
| Postać | Portret 3D głowy z twojego save'a (twarz, włosy, kolory, założony hełm), ekwipunek i obciążenie. Atrybuty mają miękkie progi wzięte z plików gry: atrybut blisko progu jest podświetlony, a po najechaniu widać tabelę przyrostów. |
| Mapa | Prawdziwa mapa z gry: Ziemie Pomiędzy, Podziemia i Królestwo Cieni. W trybie „Mój postęp” widać tylko zebrane fragmenty mapy, tak jak w grze, i to, co już zaliczyłeś. Na mapie są łaski, bossowie, NPC, lochy, ok. 3400 skarbów w kategoriach, twoja pozycja i miejsca śmierci. Są filtry i wyszukiwanie. |
| Bossowie | Ponad 200 bossów z ikonami albo portretami 3D. Rangi od „Wielki run” i „Legenda” przez „Wielki boss” do „Ledwo boss”, grupowanie, sortowanie, panel krain z postępem, nagrody i najbliższa łaska przed areną. |
| Questy | Kroki odhaczają się same na podstawie flag w zapisie. Widać, co zrobić dalej, wątki zagnieżdżone i ostrzeżenia typu „zanim zabijesz…”. Tekst kroku nie zdradza fabuły, dopóki krok nie zostanie wykonany. |
| Przedmioty | Kolekcja z ekwipunku w save'ie. Ramka pokazuje rzadkość i żywioł (np. legendarny + mróz). Do tego statystyki i sekcja „Jak zdobyć”: boss, kupiec z ceną, wymiana, łup z przeciwnika z szansą, nagroda ze zdarzenia. |
| Kronika | Dziennik wyprawy pisany z kolejnych zapisów gry i podsumowanie sesji. |

Widoki są połączone: z przedmiotu przejdziesz na mapę, do bossa albo questa i z powrotem. Przełącznik
Wszystko / Podstawka / DLC w górnym pasku działa we wszystkich widokach naraz. Tryb bez spoilerów ukrywa bossów,
których jeszcze nie spotkałeś, i rzadkie przedmioty, których nie masz.

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

Program nie dotyka procesu gry, czyta tylko plik zapisu, więc można spokojnie grać online z EasyAntiCheat. Nic nie
zapisuje do plików gry ani do save'ów. Własną historię (kronikę, śmierci) trzyma w `backend/var/`.

Dane świata (bossowie, przedmioty, mapa, ikony) są wyciągane z twojej kopii gry. Repozytorium nie zawiera żadnych
plików FromSoftware.

## Gotowa paczka

Najprościej pobrać paczkę z [Releases](https://github.com/jurtomasz13/elden-map/releases/latest). Ma w sobie
Pythona i Node.js, więc nic nie trzeba instalować ani konfigurować.

### Windows: instalator

1. Pobierz `EldenMap-Setup-<wersja>.exe` i uruchom go. Instaluje się dla bieżącego użytkownika, bez uprawnień
   administratora.
2. Uruchom Elden Map z menu Start albo z pulpitu.
3. Przy pierwszym uruchomieniu program przez kilkanaście minut wyciąga dane z twojej gry (mapę, ikony, bossów,
   przedmioty), a potem otwiera przeglądarkę. Kolejne uruchomienia trwają kilka sekund.

> Windows SmartScreen może ostrzec o nieznanym wydawcy, bo instalator nie jest podpisany certyfikatem. Wtedy kliknij
> „Więcej informacji”, a potem „Uruchom mimo to”.

### Linux (CachyOS, Arch, Ubuntu, Fedora…): archiwum

```bash
sudo pacman -S --needed wine          # CachyOS / Arch  (Ubuntu/Debian: sudo apt install wine · Fedora: sudo dnf install wine)
tar xf elden-map-<wersja>-linux-x64.tar.gz
cd elden-map-<wersja>-linux-x64
./elden-map
```

Pierwsze uruchomienie przygotuje dane z gry (kilkanaście minut), potem otworzy przeglądarkę.

Wine jest potrzebne tylko raz, do rozpakowania archiwów gry. Dekompresję Oodle robi biblioteka z samej gry
(`oo2core_6_win64.dll`), uruchamiana w osobnym prefiksie `~/.cache/elden-map/wine`, więc twoich prefiksów Wine
i Protona program nie rusza. Backend i strona działają natywnie.

Dane od nowa (np. po aktualizacji gry) przygotujesz na Windowsie skrótem „Elden Map — przygotuj dane od nowa”
w menu Start, a na Linuxie poleceniem `./elden-map --prepare`.

## Wymagania

| | Windows | Linux |
|---|---|---|
| Gra | Elden Ring ze Steama (DLC opcjonalne) | Elden Ring ze Steama przez Proton |
| Paczka z Releases | nic więcej | Wine (tylko do pierwszego przygotowania danych) |
| Ze źródeł | Python 3.11+ (zalecany 3.14), Node.js 18+ | to samo i Wine |
| Miejsce | ok. 3 GB na dane z gry | ok. 3 GB |

Wystarczy dowolna aktualna przeglądarka, np. Chrome, Firefox albo Edge.

## Ze źródeł na Windowsie

W PowerShellu:

```powershell
git clone https://github.com/jurtomasz13/elden-map.git
cd elden-map
python prepare.py                           # jednorazowo: dane z gry (kilkanaście minut)
python start.py                             # backend + strona, otworzy przeglądarkę
```

Folder gry i save'y program znajdzie sam (biblioteki Steama, `%APPDATA%\EldenRing`).

## Ze źródeł na Linuxie

Najpierw pakiety:

- CachyOS / Arch: `sudo pacman -S --needed git python nodejs wine`
- Debian / Ubuntu / Mint: `sudo apt install git python3 nodejs wine`
- Fedora: `sudo dnf install git python3 nodejs wine`

```bash
git clone https://github.com/jurtomasz13/elden-map.git
cd elden-map
python prepare.py                           # jednorazowo: dane z gry (kilkanaście minut)
python start.py                             # backend + strona, otworzy przeglądarkę
```

Pakiety z `pip` nie są potrzebne. Opcjonalnie `pip install cryptography` w `venv` przyspiesza odszyfrowywanie. Przy
pierwszej ekstrakcji `prepare.py` pobiera z python.org mały Python dla Windowsa (12 MB, suma SHA-256 jest
sprawdzana), w którym przez Wine działa Oodle z gry.

Program sam przeszukuje biblioteki Steama: `~/.steam/steam`, `~/.local/share/Steam`, Flatpak
(`~/.var/app/com.valvesoftware.Steam/…`), Snap oraz wszystkie dodatkowe biblioteki z `libraryfolders.vdf` (także
Steam z repozytorium CachyOS i `proton-cachyos`). Save'y z Protona leżą tu:

```
<biblioteka Steama>/steamapps/compatdata/1245620/pfx/drive_c/users/steamuser/AppData/Roaming/EldenRing/<SteamID64>/
```

Przeszukiwane są wszystkie prefiksy Protona (`compatdata/*`), a także Lutris, Heroic, Bottles i `~/.wine`. Seamless
Coop dodany do Steama jako gra spoza Steama ma własny prefiks. Wtedy `ER0000.co2` leży gdzie indziej niż
`ER0000.sl2`, a backend czyta oba naraz i dla każdego pliku wybiera najświeższy.

> Bez Wine: wskaż natywną bibliotekę Oodle (`export ER_OODLE_LIB=/ścieżka/liboo2corelinux64.so`) albo przygotuj dane
> raz na Windowsie, skopiuj `assets/` i `backend/data/` i uruchom `python prepare.py --skip-extract`. Otwarty
> dekoder `kraken-decompressor` (ooz) nie rozpakowuje archiwów Elden Ringa.

## Uruchamianie na co dzień

```bash
python start.py                    # http://127.0.0.1:5180/mockup/  (Ctrl+C kończy)
python start.py --no-browser       # bez otwierania przeglądarki
python start.py --save-dir "ŚCIEŻKA/do/folderu/z/ER0000.sl2"
```

Graj normalnie. Po każdym autozapisie strona sama się odświeży (bossowie, łaski, przedmioty, kronika). Aplikacja
śledzi postać, której save zmienił się ostatnio. Inną wybierzesz w nagłówku przyciskiem „zmień postać”.

Oba serwery można też uruchomić ręcznie w dwóch terminalach. `start.py` robi to samo:

```bash
python backend/server.py                                  # API na 127.0.0.1:8765
python tools/static_server.py 5180                     # strona: http://127.0.0.1:5180/mockup/
```

## Konfiguracja

| Zmienna / opcja | Do czego |
|---|---|
| `ER_GAME_DIR` | folder gry (`…/ELDEN RING/Game`), gdy program go nie znajdzie |
| `ER_SAVE_DIR` lub `--save-dir` | jeden folder z `ER0000.sl2` / `ER0000.co2` (bez tego każdy plik jest wyszukiwany osobno) |
| `ER_OODLE_LIB` | (Linux) natywna biblioteka Oodle zamiast Wine |
| `ER_WINEPREFIX` | (Linux) inny prefiks Wine dla Oodle (domyślnie `~/.cache/elden-map/wine`) |
| `python backend/server.py --help` | port, częstotliwość sprawdzania save'a, ścieżki danych, logi debug |

`ER0000.sl2` to zapis oficjalnej gry, a `ER0000.co2` zapis Seamless Coop. Obsługiwane są oba, także z wieloma
postaciami.

## Rozwiązywanie problemów

<details>
<summary>„nie znaleziono folderu save'a”</summary>

Podaj folder wprost: `python start.py --save-dir "…/EldenRing/<SteamID64>"` albo ustaw `ER_SAVE_DIR`. Komunikat
błędu wypisuje wszystkie sprawdzone lokalizacje.
</details>

<details>
<summary>„Brak danych z gry” albo pusta mapa</summary>

Uruchom `python prepare.py`. Ekstrakcja potrzebuje zainstalowanej gry. Jeśli program nie znajdzie jej folderu, ustaw
`ER_GAME_DIR`.
</details>

<details>
<summary>Port 8765 lub 5180 jest zajęty</summary>

Najczęściej to Elden Map uruchomiony w innym oknie terminala. `start.py` sam to wykrywa i otwiera stronę. Żeby
uruchomić program od nowa, zamknij tamto okno albo naciśnij w nim Ctrl+C. Jeśli port zajmuje inny program,
`start.py` podpowie, jak go znaleźć:

```sh
ss -ltnp | grep :8765        # Linux: który proces nasłuchuje
fuser -k 8765/tcp            # Linux: zamknij go
```

```powershell
netstat -ano | findstr :8765   # Windows: ostatnia kolumna to PID
```

Do wersji 0.1.2 na Linuxie restart zaraz po Ctrl+C kończył się błędem
`OSError: [Errno 98] Address already in use` (port zwalniał się dopiero po ok. minucie). Od 0.1.3 restart działa od
razu.

`python start.py --port 5190` zmienia port strony. Port backendu zmienia `python backend/server.py --port 9000`, ale
strona domyślnie łączy się z 8765, więc w takim przypadku uruchamiaj serwery ręcznie.
</details>

<details>
<summary>Linux: „potrzebne jest Wine” albo „Pomocnik Oodle (Wine) zakończył się”</summary>

Zainstaluj Wine (`sudo pacman -S wine`) i sprawdź, czy działa `wine --version`. Pierwsze uruchomienie tworzy prefiks
w `~/.cache/elden-map/wine`, co trwa kilkanaście sekund. Sposoby bez Wine opisuje sekcja
[Ze źródeł na Linuxie](#ze-źródeł-na-linuxie).
</details>

<details>
<summary>Strona nie odświeża się po zapisie</summary>

Gra zapisuje stan co jakiś czas: przy łasce, w menu, po pokonaniu bossa. Stan połączenia widać na dole menu po lewej
(„na żywo · ER0000.co2 · slot N”). Sprawdź też <http://127.0.0.1:8765/api/health>.
</details>

## Struktura projektu

```
elden-map/
├─ start.py              # uruchamia backend + stronę
├─ prepare.py            # jednorazowe przygotowanie danych z gry
├─ launcher.py           # punkt startowy paczek (pierwsze uruchomienie → prepare, potem start)
├─ requirements.txt      # opcjonalne (Python < 3.14, szybsze AES na Linuxie)
├─ mockup/               # strona (HTML/CSS/JS, Leaflet), wszystkie widoki są w app.js
├─ backend/              # serwer: odczyt save'a, API, SSE, kronika (tylko biblioteka standardowa)
│  ├─ erbackend/         #   parser save'a, flagi, ekwipunek, historia, portrety
│  ├─ tools/             #   budowa backend/data z danych świata
│  └─ tests/             #   testy (kopiują save'y do katalogu tymczasowego)
├─ tools/
│  ├─ extract/           # ekstrakcja z plików gry: archiwa BHD/BDT, DCX, params, MSB, EMEVD, FLVER, mapa, ikony
│  ├─ fetch_community.py # pobiera dane społeczności (ER-Save-Lib, The Grand Archives)
│  └─ build_release.py   # buduje instalator Windows i archiwum Linux (bez kompilacji)
└─ docs/                 # badania i formaty: save, pamięć, archiwa, mapa, questy, API
```

Te katalogi powstają lokalnie i są w `.gitignore`: `assets/`, `backend/data/*.json`, `backend/var/`, `docs/data/`.

## Dla programistów

```bash
python -m unittest discover -s backend/tests -v     # testy backendu (potrzebują save'ów: ER_SAVE_DIR)
python tools/extract/run_all.py                     # sama ekstrakcja z gry
python backend/tools/build_data.py                  # dane backendu z assets/data
```

Formaty plików i ustalenia z badań opisuje [docs/](docs/README.md), m.in. [format save'a](docs/03-format-save.md),
[API backendu](docs/07-backend-api.md), [mapa i ikony](docs/08-assets.md), [dane świata](docs/10-world-data.md)
i [questy](docs/09-quests.md).

## Prawa i dane

- Elden Ring i wszystkie zasoby gry (mapa, ikony, modele, teksty) należą do FromSoftware / Bandai Namco.
  Repozytorium ich nie zawiera: `prepare.py` czyta je z twojej legalnej kopii gry, wyłącznie do użytku lokalnego.
  Nie publikuj katalogu `assets/`.
- Dane społeczności są pobierane przy instalacji. Nie mają licencji, więc nie ma ich w repozytorium:
  [ClayAmore/ER-Save-Lib](https://github.com/ClayAmore/ER-Save-Lib) (`eventflag_bst.txt`) i
  [The Grand Archives, Elden Ring CT](https://github.com/The-Grand-Archives/Elden-Ring-CT-TGA).
- Paczki zawierają [Python](https://www.python.org/) (PSF), [python-build-standalone](https://github.com/astral-sh/python-build-standalone)
  (Linux) i [Node.js](https://nodejs.org/) (MIT). Są pobierane z oficjalnych źródeł, a ich sumy SHA-256 sprawdza
  `tools/build_release.py`. Instalator powstaje w [Inno Setup](https://jrsoftware.org/isinfo.php).
- To projekt fanowski, niezwiązany z FromSoftware ani Bandai Namco.
