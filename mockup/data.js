// Dane przykładowe makiety. Kształt zgodny ze szkicem kontraktu API (docs/07-backend-api.md).
// Współrzędne x/y to punkty na abstrakcyjnej mapie makiety (0–1000), nie współrzędne gry.
window.MOCK = {
  character: { slot: 1, name: "boink", level: 180, playtime_s: 278280, runes_memory: 14592293, deaths: 330, last_grace: "Kościół Elleh" },
  characters: [
    { slot: 0, name: "grandes", level: 148 }, { slot: 1, name: "boink", level: 180 },
    { slot: 2, name: "prophet", level: 176 }, { slot: 3, name: "finali", level: 221 },
    { slot: 4, name: "Mokki", level: 152 }, { slot: 5, name: "Ser Davick", level: 13 }, { slot: 6, name: "chuj", level: 8 },
  ],
  position: { x: 318, y: 642, map: "Limgrave" },
  save: { file: "ER0000.sl2", seconds_ago: 23 },

  regions: [
    { id: "limgrave", name: "Limgrave", discovered: true },
    { id: "weeping", name: "Półwysep Płaczu", discovered: true },
    { id: "liurnia", name: "Liurnia Jezior", discovered: true },
    { id: "caelid", name: "Caelid", discovered: true },
    { id: "altus", name: "Płaskowyż Altus", discovered: true },
    { id: "leyndell", name: "Leyndell", discovered: true },
    { id: "mountaintops", name: "Szczyty Olbrzymów", discovered: false },
    { id: "haligtree", name: "Drzewo Hali", discovered: false },
    { id: "shadow", name: "Królestwo Cienia", discovered: false, dlc: true },
  ],

  bosses: [
    { id: "margit", name: "Margit, Okrutny Omen", region: "limgrave", loc: "Zamek Stormveil, brama", type: "omen", defeated: true, required: true, discovered: true, attempts: 6, runes: 12000, x: 352, y: 560,
      drops: ["Talizman Szponu Sokoła", "Okrutne ostrze Margit"],
      how: ["Z łaski Rozdroża Stormhill idź drogą na północ, w stronę bramy zamku.", "Przed mgłą postaw znak przyzwania Rogera lub popiół ducha.", "Kup przy Kalé Mineral Shackles, by na chwilę unieruchomić bossa."] },
    { id: "godrick", name: "Godrick Szczepiony", region: "limgrave", loc: "Zamek Stormveil, szczyt", type: "demigod", defeated: true, required: true, discovered: true, attempts: 9, runes: 20000, x: 372, y: 500,
      drops: ["Wielka Runa Godricka", "Pamięć Szczepionego"],
      how: ["Przejdź przez zamek od bocznego wejścia (łaska Boczny Ganek).", "Z łaski Rampa Hołdu zejdź na dziedziniec i po drabinie na wieżę.", "Mgła na końcu tarasu prowadzi na arenę."] },
    { id: "tree-sentinel", name: "Strażnik Drzewa", region: "limgrave", loc: "Kościół Elleh, droga", type: "knight", defeated: true, required: false, discovered: true, attempts: 4, runes: 3600, x: 300, y: 652,
      drops: ["Złota Halabarda"], how: ["Patroluje drogę tuż obok Kościoła Elleh – nie da się go przegapić."] },
    { id: "agheel", name: "Smok Agheel", region: "limgrave", loc: "Jezioro Agheel", type: "dragon", defeated: true, required: false, discovered: true, attempts: 2, runes: 5000, x: 258, y: 600,
      drops: ["Serce Smoka"], how: ["Wejdź na środek Jeziora Agheel – smok spada z nieba."] },
    { id: "night-cavalry-l", name: "Nocna Kawaleria", region: "limgrave", loc: "Most Agheel (tylko nocą)", type: "knight", defeated: false, required: false, discovered: true, attempts: 3, runes: 2400, x: 285, y: 575,
      drops: ["Popiół wojny: Barykada"], how: ["Pojawia się nocą na drodze pod mostem – odpocznij przy łasce i przewiń czas do nocy."] },
    { id: "bell-bearing", name: "Łowca z Dzwonem", region: "limgrave", loc: "Chata Warmastera (nocą)", type: "knight", defeated: false, required: false, discovered: false, attempts: 0, runes: 2700, x: 410, y: 610,
      drops: ["Dzwon Łowcy Kostnego"], how: ["Odwiedź chatę nocą."] },
    { id: "leonine", name: "Leoniński Wypaczeniec", region: "weeping", loc: "Zamek Morne", type: "beast", defeated: true, required: false, discovered: true, attempts: 1, runes: 3800, x: 412, y: 808,
      drops: ["Miecz Milosa"], how: ["Przejdź przez Zamek Morne od zachodniej skarpy."] },
    { id: "rennala", name: "Rennala, Królowa Pełni Księżyca", region: "liurnia", loc: "Akademia Raya Lucaria", type: "demigod", defeated: true, required: true, discovered: true, attempts: 3, runes: 40000, x: 205, y: 370,
      drops: ["Wielka Runa Ukrytego", "Pamięć Pełni Księżyca"],
      how: ["Zdobądź Klucz Kamiennej Bramy Akademii (Cmentarz Zaczarowanego Ostrza).", "Przejdź przez Akademię aż do łaski Biblioteka Debaty.", "W pierwszej fazie uderzaj świecących uczniów, by przerwać barierę."] },
    { id: "red-wolf", name: "Czerwony Wilk Radagona", region: "liurnia", loc: "Akademia Raya Lucaria", type: "beast", defeated: true, required: true, discovered: true, attempts: 2, runes: 14000, x: 220, y: 395,
      drops: ["Pamięć Czerwonego Wilka"], how: ["Hala Debaty w Akademii, po drodze do Rennali."] },
    { id: "royal-knight", name: "Królewski Rycerz Loretta", region: "liurnia", loc: "Ruiny Caria Manor", type: "knight", defeated: true, required: false, discovered: true, attempts: 7, runes: 10000, x: 150, y: 300,
      drops: ["Wielki Łuk Loretty"], how: ["Wejdź do Caria Manor z północnego wschodu Liurni.", "Arena jest za ogrodem z kamiennymi rękami."] },
    { id: "radahn", name: "Starscourge Radahn", region: "caelid", loc: "Zamek Redmane (festiwal)", type: "demigod", defeated: true, required: false, discovered: true, attempts: 14, runes: 70000, x: 715, y: 650,
      drops: ["Wielka Runa Radahna", "Pamięć Gwiazdo-Plagi"],
      how: ["Aktywuj festiwal w Zamku Redmane (łaska Plac Zamku Redmane).", "Na plaży przyzwij wszystkich sojuszników – Blaidd i Alexander pomagają.", "Jedź Torrentem między przywołanymi, unikaj meteorów."] },
    { id: "decaying-ekzykes", name: "Rozkładający się Ekzykes", region: "caelid", loc: "Pustkowia Caelid", type: "dragon", defeated: false, required: false, discovered: true, attempts: 0, runes: 72000, x: 640, y: 560,
      drops: ["Oddech Rozkładu"], how: ["Na wschód od łaski Rozdroże Caelid – smok śpi na wzgórzu."] },
    { id: "commander-oneil", name: "Dowódca O'Neil", region: "caelid", loc: "Bagno Aeonia", type: "knight", defeated: false, required: false, discovered: true, attempts: 1, runes: 12000, x: 690, y: 595,
      drops: ["Popiół wojny: Sztandar Dowódcy"], how: ["Środek szkarłatnego bagna Aeonia."] },
    { id: "godskin-apostle", name: "Apostoł Bożej Skóry", region: "caelid", loc: "Ruiny Divine Tower", type: "omen", defeated: false, required: false, discovered: false, attempts: 0, runes: 16000, x: 760, y: 470,
      drops: ["Szata Bożej Skóry"], how: ["Wieża Boska Caelid, od strony mostu."] },
    { id: "rykard", name: "Rykard, Pan Bluźnierstwa", region: "altus", loc: "Posiadłość Wulkaniczna", type: "demigod", defeated: false, required: false, discovered: true, attempts: 0, runes: 130000, x: 470, y: 205,
      drops: ["Wielka Runa Rykarda"], how: ["Dołącz do Posiadłości Wulkanicznej przez Tanith.", "Wykonaj zlecenia lub wejdź do audiencji przez kaplicę.", "Weź Miecz Serpent-Hunter z zakrętu przed areną."] },
    { id: "godfrey-shade", name: "Pierwszy Władca Elden (cień)", region: "leyndell", loc: "Stolica Leyndell", type: "demigod", defeated: true, required: true, discovered: true, attempts: 3, runes: 80000, x: 600, y: 245,
      drops: ["Talizman Godfreya"], how: ["Na schodach przed Erdtree w stolicy."] },
    { id: "morgott", name: "Morgott, Król Omenów", region: "leyndell", loc: "Stolica Leyndell", type: "omen", defeated: false, required: true, discovered: true, attempts: 5, runes: 120000, x: 620, y: 220,
      drops: ["Wielka Runa Morgotta"], how: ["Przejdź przez Leyndell do łaski Królowa Bedchamber.", "Arena przed Erdtree."] },
    { id: "fire-giant", name: "Ognisty Olbrzym", region: "mountaintops", loc: "Szczyty Olbrzymów", type: "beast", defeated: false, required: true, discovered: false, attempts: 0, runes: 180000, x: 720, y: 110,
      drops: ["Pamięć Ognistego Olbrzyma"], how: ["Na szczycie zamarzniętego jeziora."] },
    { id: "malenia", name: "Malenia, Ostrze Miquelli", region: "haligtree", loc: "Drzewo Hali, korzenie", type: "demigod", defeated: false, required: false, discovered: false, attempts: 0, runes: 480000, x: 860, y: 75,
      drops: ["Pamięć Malenii"], how: ["Wymaga Medalionu Hali (dwie połówki).", "Na dnie Elphael, przy łasce Ostoja Drzewa Hali."] },
    { id: "messmer", name: "Messmer Palownik", region: "shadow", loc: "Twierdza Cienia", type: "demigod", defeated: false, required: true, discovered: false, attempts: 0, runes: 500000, dlc: true, x: 905, y: 880,
      drops: ["Pamięć Messmera"], how: ["Królestwo Cienia – szczyt twierdzy."] },
  ],

  quests: [
    { id: "ranni", name: "Kres Gwiazd", npc: "Ranni Czarownica", warn: true, steps: [
      { text: "Spotkaj Ranni w Wieży Kościoła (Wieża Ranni)", done: true, where: "Trzy Siostry, Liurnia" },
      { text: "Pokonaj Starscourge Radahna", done: true, where: "Zamek Redmane, Caelid" },
      { text: "Zejdź do Nokron, Wiecznego Miasta", done: true, where: "Krater po upadku gwiazdy, Limgrave" },
      { text: "Zabierz Palec-Zabójcę ze Świątyni Nokronu", done: false, current: true, where: "Nokron – przez akwedukt na zachód" },
      { text: "Oddaj Palec-Zabójcę Ranni", done: false, where: "Wieża Ranni" },
      { text: "Znajdź Pierścień z Zimnym Ognia w Ainsel", done: false, where: "Rzeka Ainsel – Głębia Lake of Rot" },
      { text: "Pokonaj Baldachina i odbierz Miecz Gwiazd", done: false, where: "Grób Cariana – Moonlight Altar" } ],
      next: { text: "Zdobądź Palec-Zabójcę w Nokron", hint: "Od łaski Nokron, Wieczne Miasto idź akweduktem na zachód. Ostrze leży w kaplicy za grobowcem z kamiennymi palcami." },
      locks: [{ text: "Nie atakuj Blaidda ani Iji — wrogość któregokolwiek z nich przerwie quest Ranni." }] },
    { id: "varre", name: "Ścieżka Krwi", npc: "Biała Maska Varre", steps: [
      { text: "Porozmawiaj z Varre przy Pierwszym Kroku", done: true, where: "Limgrave" },
      { text: "Pokonaj Godricka", done: true, where: "Zamek Stormveil" },
      { text: "Najedź 3 światy (Pazur Krwawego Palca)", done: false, current: true, where: "Online – inwazje" },
      { text: "Nasyć Pazur krwią Dziewicy Płotek", done: false, where: "Rotunda w Pustkowiu" },
      { text: "Użyj Pazura przy Kaplicy Mohgwyn", done: false, where: "Rotunda Kamiennego Dziedzictwa" } ],
      next: { text: "Wykonaj 3 inwazje Pazurem Krwawego Palca", hint: "Gra online z EAC — inwazje działają normalnie. Każda udana inwazja odhaczy się po zapisie gry." } },
    { id: "alexander", name: "Wojownik w Słoju", npc: "Żelazna Pięść Alexander", steps: [
      { text: "Wyciągnij Alexandra z ziemi (Pole Rozdroża)", done: true, where: "Limgrave, północ" },
      { text: "Spotkaj go przed festiwalem Radahna", done: true, where: "Zamek Redmane" },
      { text: "Pomóż mu wyjść z pułapki w Gelmir", done: false, current: true, where: "Góra Gelmir, przy gorącym źródle" },
      { text: "Spotkaj na Szczytach Olbrzymów", done: false, where: "Szczyty Olbrzymów" },
      { text: "Pojedynek w Farum Azula", done: false, where: "Rozkruszone Farum Azula" } ],
      next: { text: "Uwolnij Alexandra z gorącej skały w Gelmir", hint: "Weź z sobą broń o dużym ciężarze; uderz go kilka razy, stojąc na lawie." } },
    { id: "millicent", name: "Kwiat Szkarłatu", npc: "Millicent", steps: [
      { text: "Spotkaj Millicent w Kaplicy Tchnienia", done: false, current: true, where: "Caelid, Kościół Plagi" },
      { text: "Przynieś Ziarno Nasion Złocistej Igły", done: false, where: "Fort Faroth, Dragonbarrow" },
      { text: "Pomagaj jej w 3 walkach", done: false, where: "Altus, Gelmir, Szczyty" },
      { text: "Decyzja w Drzewie Hali", done: false, where: "Drzewo Hali" } ],
      next: { text: "Odwiedź Millicent w Kościele Plagi", hint: "Odwiedziłeś ten obszar, ale nie porozmawiałeś z Gowrym – zacznij od niego." } },
    { id: "sellen", name: "Uczennica Gwiazd", npc: "Czarodziejka Sellen", steps: [
      { text: "Kup zaklęcia w Ruinach Wyschniętej Kaplicy", done: true, where: "Limgrave" },
      { text: "Zdobądź Kamień Grafa", done: true, where: "Pustkowie Caelid" },
      { text: "Odszukaj ciało Sellen w Akademii", done: true, where: "Raya Lucaria" },
      { text: "Wybierz stronę: Sellen czy Jerren", done: false, current: true, where: "Gościniec Witchbane" } ],
      next: { text: "Wybierz stronę konfliktu w Witchbane", hint: "Wybór blokuje drugą ścieżkę – zapisz kopię save'a przed decyzją." } },
  ],

  items: {
    categories: [
      { id: "weapons", name: "Bronie", total: 418, have: 147 },
      { id: "armor", name: "Zbroje", total: 568, have: 201 },
      { id: "talismans", name: "Talizmany", total: 155, have: 72 },
      { id: "spells", name: "Czary", total: 178, have: 34 },
      { id: "aow", name: "Popioły wojny", total: 116, have: 73 },
      { id: "spirits", name: "Duchy", total: 86, have: 31 },
    ],
    weapons: [
      ["Miecz Pana Moonvieleka", 1], ["Rivers of Blood", 1], ["Złota Halabarda", 1], ["Wielki Miecz Gwiazd", 0], ["Ostrze Zaćmienia", 0],
      ["Katana Nagakiba", 1], ["Miecz Milosa", 1], ["Włócznia Gwiazdy", 0], ["Ostrze Godslayera", 0], ["Bluźniercze Ostrze", 0],
      ["Kostur Cichego", 1], ["Wielki Łuk Loretty", 1], ["Miecz Wiecznego Mroku", 0], ["Topór Rozdarcia", 1], ["Księżycowy Wielki Miecz", 0],
      ["Kosa Zimowa", 0], ["Młot Gniewu", 1], ["Rapier Antspur", 0], ["Bicz Hoslowa", 1], ["Miecz Serpent-Hunter", 0],
      ["Pazur Bestii", 1], ["Sztylet Zabójcy", 1], ["Kij Niebieskiej Wiśni", 0], ["Wielka Maczuga", 1], ["Ostrze Dziewczęcia", 0],
      ["Łuk Wężowy", 0], ["Miecz Krwi Psa", 1], ["Włócznia Smoczego Kła", 0], ["Halabarda Strażnika", 1], ["Siekiera Wilka", 0],
      ["Kostur Łzy", 0], ["Topór Kryształu", 1], ["Nóż Zbóża", 1], ["Ostrze Godfreya", 0], ["Miecz Sedanu", 0], ["Kosa Grafa", 0] ],
  },

  graces: { done: 186, total: 309 },
  itemsProgress: { done: 558, total: 1521 },

  deaths: [ [352,560],[350,566],[356,558],[349,561],[355,563],[372,500],[370,505],[375,498],[369,503],[371,499],[374,506],[368,502],[373,501],
            [715,650],[712,655],[718,648],[716,652],[710,649],[720,654],[714,647],[717,651],[713,653],[719,646],[711,650],[716,656],[714,649],[718,652],
            [620,220],[622,224],[618,219],[621,222],[619,225], [150,300],[152,303],[148,298],[151,302],[149,299],[153,301],[150,304], [205,370],[208,372],[203,368],
            [440,300],[530,420],[600,520],[300,700],[480,640],[260,450] ],

  chronicle: [
    { day: "Dziś — sesja wieczorna", entries: [
      { t: "21:42", g: "❦", kind: "grace", txt: "Odkryto łaskę <em>Krawędź Krateru</em>", sub: "Caelid" },
      { t: "21:31", g: "☠", kind: "death", blood: true, txt: "Śmierć nr 330", sub: "Bagno Aeonia — szkarłatna zgnilizna" },
      { t: "21:12", g: "⚔", kind: "boss", txt: "Pokonano Starscourge Radahna", sub: "po 14 próbach, 1 h 52 min od pierwszego spotkania" },
      { t: "20:58", g: "✦", kind: "quest", txt: "Ranni: <em>zejdź do Nokron</em>", sub: "nowy krok questa" },
      { t: "20:40", g: "❖", kind: "item", txt: "Zdobyto <em>Wielką Runę Radahna</em>", sub: "Zamek Redmane" },
      { t: "20:22", g: "▲", kind: "level", txt: "Poziom 176 → 180", sub: "+4 Witalność" } ] },
    { day: "Wczoraj", entries: [
      { t: "23:05", g: "❦", kind: "grace", txt: "Odkryto łaskę <em>Plac Zamku Redmane</em>", sub: "Caelid" },
      { t: "22:47", g: "⚔", kind: "boss", txt: "Pokonano Rozkładającą się Bestię", sub: "za pierwszym razem" },
      { t: "22:10", g: "◈", kind: "map", txt: "Wkroczono do regionu <em>Dragonbarrow</em>", sub: "" },
      { t: "21:33", g: "☠", kind: "death", blood: true, txt: "Seria 6 śmierci", sub: "Radahn — pierwsze próby" },
      { t: "20:15", g: "✦", kind: "quest", txt: "Alexander: <em>spotkany przed festiwalem</em>", sub: "Zamek Redmane" } ] },
  ],

  session: { duration: "2 h 47 min", bosses: 3, graces: 12, items: 9, deaths: 41, levels: 4,
    highlights: ["Starscourge Radahn — po 14 próbach", "Wielka Runa Radahna", "Nowy region: Dragonbarrow"] },
};

// Prawdziwa mapa: pozycje w pikselach L0 (10496 px, assets/map/M00), ikony z assets/icons/<iconId>.png.
// Bossowie: ikony wizerunków (remembrances) albo charakterystycznego łupu. Pozycje przybliżone (makieta).
window.MOCK.bossMeta = {
  margit: { px: 3705, py: 6690, icon: 12083 }, godrick: { px: 3560, py: 6450, icon: 163 },
  "tree-sentinel": { px: 3712, py: 7235, icon: 10688 }, agheel: { px: 3990, py: 7190, icon: 3230 },
  "night-cavalry-l": { px: 4050, py: 7040 }, "bell-bearing": { px: 3721, py: 6653 },
  leonine: { px: 4072, py: 8547, icon: 10096 }, rennala: { px: 1900, py: 4610, icon: 172 },
  "red-wolf": { px: 1960, py: 4700 }, "royal-knight": { px: 1760, py: 3950, icon: 6013 },
  radahn: { px: 6228, py: 6794, icon: 164 }, "decaying-ekzykes": { px: 5620, py: 6930 },
  "commander-oneil": { px: 5900, py: 7330 }, "godskin-apostle": { px: 6600, py: 6380 },
  rykard: { px: 2300, py: 2720, icon: 166 }, "godfrey-shade": { px: 3950, py: 3330, icon: 170 },
  morgott: { px: 4010, py: 3230, icon: 165 }, "fire-giant": { px: 6000, py: 2150, icon: 174 },
  malenia: { px: 5250, py: 1300, icon: 167 }, messmer: { map: "M10", icon: 733 },
};
window.MOCK.questIcons = { ranni: 3050, varre: 625, alexander: 18871, millicent: 3275, sellen: 3072 };
window.MOCK.position = { px: 3671, py: 7185, map: "M00", name: "Kościół Elleha" };
