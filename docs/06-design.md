# Kierunek wizualny i widoki (makieta)

## Cel

Aplikacja-towarzysz do Elden Ring z kilkoma widokami (bossowie, questy, przedmioty, mapa), która wygląda jak część
świata gry, a nie jak zwykły dashboard. Odświeża się sama po każdym zapisie save'a (w trybie online z EAC opóźnienie
sięga minuty, patrz [04](04-otwarte-pytania.md)).

## Badanie: co definiuje styl Elden Ring

Źródła: [UX/UI of Elden Ring (UX Collective)](https://uxdesign.cc/the-ux-and-ui-of-elden-ring-42036ad0e24c),
[Analysing the UX Design of Elden Ring (Superjump)](https://superjumpmagazine.com/analysing-the-ux-design-of-elden-ring),
[Kotaku o UI Elden Ring](https://kotaku.com/elden-ring-ui-ux-user-experience-interface-fromsoftware-1848637410),
[Stamen: kartografowie o mapie Elden Ring](https://stamen.com/cartographers-play-video-games-a-review-of-the-map-in-elden-ring/),
[Inverse o mapie](https://www.inverse.com/gaming/elden-ring-killed-the-map-game-good-riddance),
[Made Good Designs: fonty FromSoftware](https://madegooddesigns.com/fromsoftware-font/),
[Carter & Cone: Mantinia](https://carterandcone.com/font/mantinia/).

Obserwacje:

1. Minimalizm i cisza. Mało elementów na ekranie, dużo pustej, ciemnej przestrzeni. Informacja podawana obrazem,
   nie liczbami. Brak ikon zadań i krzykliwych kolorów.
2. Ciemne, ciepłe tło i oszczędne złoto. Prawie czarne panele z lekką przezroczystością, tekst w kolorze
   kości/pergaminu, złoto tylko na akcentach (zaznaczenie, nagłówki, cienkie linie).
3. Szeryfowa, klasyczna typografia. Logo bazuje na Mantinii (inskrypcyjne kapitaliki, komercyjna), tekst UI jest
   zbliżony do Agmeny (komercyjna). Darmowe odpowiedniki: Cinzel (kapitaliki inskrypcyjne) i Cormorant Garamond
   (wysoki kontrast, elegancki) albo EB Garamond (czytelność drobnego tekstu).
4. Ornament z cienkich linii. Poziome kreski zanikające na końcach, drobne romby jako węzły, narożniki-klamry
   zamiast pełnych ramek. Nic ciężkiego, żadnych błyszczących gradientów.
5. Światło łaski. Złota, miękka poświata oznacza „tu jest coś ważnego” albo „aktywne”.
6. Mapa jak pergamin. Ręcznie rysowana, w kolorze sepii, atramentem, nieodkryte obszary to pusty pergamin. Bardzo
   oszczędna ikonografia (łaski, budowle).

## Decyzje projektowe

### Paleta (tokeny CSS)

| Token | Kolor | Użycie |
|---|---|---|
| `--void` | `#0a0907` | tło aplikacji (ciepła czerń) |
| `--ash` | `#14120e` | panele |
| `--ash-2` | `#1c1913` | panele podniesione, hover |
| `--line` | `rgba(201,170,113,.22)` | cienkie linie ornamentu |
| `--gold` | `#c9aa71` | akcenty, nagłówki |
| `--gold-hi` | `#ecdcae` | zaznaczenie, liczby |
| `--bone` | `#d8cfbb` | tekst główny |
| `--muted` | `#8a8170` | tekst drugorzędny |
| `--grace` | `#f4d37c` | poświata „aktywne / na żywo” |
| `--blood` | `#9b3428` | pozostałe / niebezpieczne (oszczędnie) |
| `--parchment` | `#cbb88f` | mapa |
| `--ink` | `#3a2d1e` | atrament na mapie |

Trybu jasnego nie planujemy: gra jest ciemna, a aplikacja działa obok niej, często na drugim ekranie.

### Typografia

- Cinzel: tytuły widoków, nazwy bossów, nawigacja. Wersaliki, duży odstęp liter (0.12–0.25em).
- Cormorant Garamond: opisy, wskazówki, tekst fabularny, duże liczby.
- Domyślnie bez fontów bezszeryfowych w interfejsie, bo to one najszybciej dają wygląd generycznego UI. Przełącznik
  „Czytelna czcionka” nad przyciskiem „Podsumowanie sesji” zamienia oba kroje na Libertinus Serif (następca Linux
  Libertine, licencja OFL, z Google Fonts); wybór zostaje w przeglądarce.

### Ornament i faktura

- Linie: `linear-gradient(90deg, transparent, gold, transparent)` o grubości 1 px.
- Romby 5–7 px jako węzły linii, punkty osi czasu questa, znaczniki postępu.
- Narożniki-klamry na kartach zamiast pełnych obramowań.
- Winieta i delikatne ziarno (SVG `feTurbulence`) na tle, żeby czerń nie była płaska.
- Ikony: własne, liniowe SVG (pieczęcie, sigile), żadnych grafik z gry (prawa autorskie).

### Ruch

- Wolne przejścia 300–600 ms, `ease-out`, bez sprężyn i podskoków.
- Zdarzenie na żywo (np. boss pokonany po zapisie save'a): krótki złoty napis przez środek ekranu z rozszerzającym
  się odstępem liter, potem karta bossa przechodzi w stan „pokonany”.
- Wskaźnik „na żywo” w górnym pasku: pulsująca kropka łaski i napis „ostatni zapis 23 s temu”.

## Struktura aplikacji

```
┌──────────────────────────────────────────────────────────────────────┐
│ ◆ boink · poz. 180 · 77 h · ☠ 330          ● zapis 23 s temu (online) │  pasek postaci
├────────┬─────────────────────────────────────────────────────────────┤
│ MAPA   │                                                             │
│ BOSSOWIE│               treść widoku                    │ szuflada   │
│ QUESTY │                                                │ szczegółów │
│ PRZEDM.│                                                │ (po kliknięciu)
└────────┴─────────────────────────────────────────────────────────────┘
```

Szerokość: treść widoku jest wyśrodkowana (limit 1400 px, bossowie 1760 px, od 2400 px okna 2100 px, bo siatki
dokładają wtedy kolumny). Do 1800 px szuflada szczegółów wysuwa się nad treścią; od 1800 px (szerokie monitory,
ultrawide) otwarta szuflada jest trzecią kolumną obok treści i niczego nie zasłania. Mapa przelicza wtedy rozmiar
sama (ResizeObserver). Ikona strony: `mockup/favicon.svg`, złoty romb jak znak postaci w pasku.

### Widoki

1. Bossowie: licznik `pokonani / wszyscy` z pierścieniem postępu, filtry (region, gra / DLC, tylko pozostali,
   obowiązkowi), siatka kart z sigilem, nazwą, regionem i stanem. Kliknięcie otwiera szufladę: lokalizacja, jak
   dotrzeć (kroki), wymagania, nagrody, mini-mapa.
2. Questy: lista NPC z paskami postępu. Wybrany quest pokazuje oś czasu kroków (zrobione, bieżący, kolejne),
   wyróżnioną kartę „Co dalej” i ostrzeżenia o rzeczach, które można przegapić.
3. Przedmioty: kategorie (bronie, zbroje, talizmany, czary, popioły wojny, duchy…) i siatka kolekcji: zdobyte
   w złocie, brakujące jako sylwetki. Kliknięcie pokazuje, gdzie przedmiot leży i jak go zdobyć.
4. Mapa: pergamin, znaczniki wszystkich punktów (łaski, bossowie, przedmioty, questy) z filtrami, pozycja postaci
   z ostatniego zapisu, legenda, zoom i przesuwanie.

## Pomysły na dodatkowe funkcje (z danych save'a)

| # | Pomysł | Skąd dane | W makiecie |
|---|---|---|---|
| 1 | Kronika: automatyczna oś czasu zdarzeń (łaski, bossowie, questy) | diff flag między zapisami | tak, widok |
| 2 | Miejsca śmierci (mapa cieplna) i liczba prób na bossa | pozycja plamy krwi (`blood_stain`) w każdym zapisie + licznik śmierci | tak, warstwa mapy |
| 3 | Tryb bez spoilerów: nieodkryte rzeczy jako zamazane sylwetki | flagi odkrycia / regiony | tak, przełącznik |
| 4 | Ostrzeżenia „zanim zabijesz X, dokończ Y” | flagi questów + bossów | tak, w widoku questów |
| 5 | Podsumowanie sesji (karta do udostępnienia) | diff od startu sesji | tak |
| 6 | Mgła wojny z odblokowanych regionów | `unlocked_regions` | tak, mapa |
| 7 | Postęp w każdym regionie (%) | flagi pogrupowane po regionach | tak, mapa i bossowie |
| 8 | Statystyki postaci, wykres poziomu w czasie | PlayerGameData, historia zapisów | nie |
| 9 | Porównanie postaci / NG+ | profil USER_DATA010, `clear_count` | nie |
| 10 | Osiągnięcia Steam z flag | flagi | nie |
| 11 | Widok na telefon (QR w sieci LAN), nakładka OBS | backend HTTP | nie |

## Makieta

`mockup/index.html`: jeden plik, dane przykładowe zgodne z kontraktem API backendu
([07-backend-api.md](07-backend-api.md), przygotowuje go równoległa sesja). Mapa w makiecie to abstrakcyjny ląd
narysowany ręcznie w SVG. Prawdziwą mapę świata wyciągniemy później z plików gry zainstalowanej u użytkownika.

## Zachowanie widoków (stan na 2026-11-23, po dwóch audytach)

- Nazewnictwo jak w grze: PŻ / PS / Energia, atrybut Wytrzymałość, Wielki run, „runów”, Wieczne więzienia, Grobowce
  bohaterów, Dzwonki kuliste. Filtry wszędzie w tej samej kolejności: Wszystko / Gra podstawowa / DLC. Odmiana
  liczebników przez `plural()` / `pl()` w `app.js`.
- Tryb bez spoilerów: boss odsłania się po spotkaniu (łaska przy arenie, teren, próba walki). Ukryte są tylko rzadkie
  i legendarne przedmioty, których nie masz. „Odsłoń” działa na jednego bossa albo jeden przedmiot
  (`state.revealed`) i nie wyłącza trybu. Niezaliczone kroki questów pokazują wersję bez spoilerów.
- Mapa: wyszukiwanie pokazuje chip „Filtr: … ✕”, który znika po wyjściu z mapy. „Wszystkie miejsca” z przedmiotu
  filtruje po dokładnej nazwie. Kliknięcie mini-mapy w szczegółach otwiera okienko „Pokazać na dużej mapie?”.
  Przejście na mapę z innej strony (karta bossa, przedmiotu, „Gdzie wypada”) włącza tryb skupienia: widać tylko
  szukaną rzecz, niezależnie od warstw, wyszukiwania, „Ukryj zaliczone” i „Mojego postępu”; chip „Pokazuję: … ·
  pokaż resztę ✕” go wyłącza. Nad warstwami jest przycisk „Ukryj wszystko / Pokaż wszystko”.
- Mapa: warstwy „Teleporty” (klik: skąd i dokąd, czy brama otwarta, czego wymaga, przycisk „Przenieś do celu”)
  i „Znaki przywołania” (klik: karta postaci). Postacie z portretem 3D mają okrągłą miniaturę zamiast kropki.
- Karta postaci (klik w postać na mapie albo w znak): portret, gdzie jest teraz według gry, quest (dalej jednym
  kliknięciem), usługi, sklep z ceną i stanem z save'a (kupione X z Y, wyprzedane, jeszcze niedostępne), podarunki,
  łup po śmierci (z uwagą o dzwonku kulistym), znaki przywołania, najazdy, miejsca, w których bywa.
- Karta bossa: statystyki z plików gry (PŻ, postawa, redukcja obrażeń, progi statusów), „Twoje bronie: ile ciosów”
  (bronie założone w rękach, atrybuty z save'a), wizerunek z runami za użycie i wymianami u Enii. Najeźdźcy i przeciwnicy
  z jednorazowym łupem (skarabeusze) mają te same sekcje.
- Postacie: ręczny wybór przypina postać, a „Śledź automatycznie” wraca do postaci, której save zmienił się
  ostatnio.
- Bossowie: grupy według rangi (domyślnie), krainy albo statusu, panel krain po prawej z podkrainami. Karta
  niepokonanego jest wyszarzona, pokonanego jasna ze złotym ptaszkiem, bez napisu o stanie. Na samym dole, pod „Ledwo boss”, osobna grupa
  najeźdźców (unikalne czerwone fantomy) z portretami, te same filtry stanu i wyszukiwania, bez filtra krainy i rangi.
- Strona postaci: duży obrazek całej postaci w zbroi, kafelki PŻ, PS, energii, błogosławieństw Ostrodrzewa
  i prochów czcigodnych (poziom i zmiana obrażeń w procentach, tylko gdy postać je ma), butelek (ładunki szkarłatne
  i modre z 14, moc +0 do +12), miejsc na czary (kamienie pamięci), slotów talizmanów oraz obciążenia: pasek
  podzielony na strefy lekki / średni / ciężki z górną wagą każdej i zapasem do następnego progu.
- Liczenie ciosów na przeciwników z DLC mnoży obrażenia przez błogosławieństwo Ostrodrzewa postaci.
- Pola o rodzaju obrażeń albo statusie (redukcja i odporności bossa, atak broni, ochrona zbroi, tagi żywiołów,
  linia „słaby na”) mają kolor i efekt swojego żywiołu, np. ogień żarzy się od dołu, mróz ma lodowy połysk.
- Przedmioty: grupy według rzadkości (domyślnie), typu, skalowania albo żywiołu, ramki rzadkość × żywioł, sekcja
  „Jak zdobyć” (bossowie, kupcy z ceną, wymiana, przeróbka odzienia, łup z przeciwników z szansą, nagrody ze
  zdarzeń).
