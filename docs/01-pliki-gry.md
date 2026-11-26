# Pliki gry i analiza binarek

## Lokalizacja

- Gra: `C:\Program Files (x86)\Steam\steamapps\common\ELDEN RING\Game` (Steam app 1245620, buildid 25827938)
- Save'y: `%APPDATA%\EldenRing\<SteamID64>\`
  - `ER0000.sl2`: zwykła gra (oficjalna)
  - `ER0000.co2`: Seamless Coop (ten sam format, zweryfikowane)
  - `*.bak`: kopie zapasowe robione przez grę
  - folder `<SteamID64> — kopia`: ręczna kopia z 17.11.2026

## Zawartość folderu `Game`

| Plik | Co to |
|---|---|
| `eldenring.exe` (87 MB) | gra; wersja pliku 2.7.1.0 = „1.17.1” w menu |
| `Data0-3.bdt/.bhd`, `DLC.bdt/.bhd` | zaszyfrowane archiwa z zasobami (mapy, modele, teksty, parametry) |
| `regulation.bin` | parametry gry (przedmioty, bronie, łaski, ItemLot…), BND4 zaszyfrowany AES |
| `start_protected_game.exe` | launcher EAC |
| `ersc_launcher.exe` + `SeamlessCoop\ersc.dll` | Seamless Coop (uruchamia grę bez EAC) |
| `eldenring_all-in-one_Hexinton-v8.0.4.CT` | tabela Cheat Engine, najlepsze źródło wiedzy o pamięci gry |
| `amd_ags_x64.dll`, `bink2w64.dll`, `oo2core_6_win64.dll`, `eossdk-*.dll`, `steam_api64.dll` | biblioteki firm trzecich (AMD, Bink video, Oodle, Epic Online Services, Steam), dla nas bez znaczenia |

## Analiza DLL / EXE: dlaczego nie dekompilujemy

Napisałem własny parser nagłówków PE (`scratchpad`, bez zewnętrznych bibliotek) i sprawdziłem dwa pliki.

### `SeamlessCoop\ersc.dll`

- Jedyny eksport to `modengine_ext_init`, więc DLL jest pisany jako rozszerzenie Mod Engine 2 (da się go ładować
  obok innych modów przez ME2).
- Importuje po jednej funkcji z każdej biblioteki (`GetModuleHandleA`, `GetAsyncKeyState`,
  `SteamAPI_GetHSteamPipe`…) i ma sekcję `ERSC` o rozmiarze 11 MB. Plik jest więc spakowany albo zabezpieczony
  (packer rozwiązuje importy w locie). Dekompilacja dałaby tylko kod rozpakowujący.
- Wniosek: nic z niego nie wyciągniemy, a do naszego celu nie jest potrzebny.

### `eldenring.exe`

- Ma dwie sekcje `.text` (0x29A6400 i 0x11E7600 bajtów). Druga to kod zabezpieczenia Arxan (obfuskacja
  i anty-tamper). Statyczna dekompilacja 87 MB zaciemnionego kodu bez Ghidry albo IDA to tygodnie pracy.
- Eksportuje 560 symboli Scaleform (UI) i Wwise (`AK::`), nieistotnych dla nas.
- Importuje m.in. `WINHTTP` z WebSocketami (komunikacja sieciowa gry).

### Lepsza droga: wiedza społeczności

Wszystko, czego potrzebujemy z pamięci gry (adresy managerów, pozycja, flagi), jest już rozpracowane w tabeli Cheat
Engine (zwykły XML, 7.9 MB), patrz [02-pamiec-gry.md](02-pamiec-gry.md). Sygnatury AOB z tabeli przetrwają patche,
bo szukają wzorca bajtów, a nie stałego adresu.

Gdyby kiedyś była potrzebna prawdziwa dekompilacja (np. żeby znaleźć coś, czego nie ma w CT):

- Ghidra (darmowa, wymaga Javy; Java 21 jest zainstalowana) na zrzucie pamięci działającej gry (po rozpakowaniu
  przez Arxan), a nie na pliku z dysku.
- Te narzędzia nie są zainstalowane. Cheat Engine jest (`C:\Program Files\Cheat Engine`).
