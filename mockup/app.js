(() => {
  const D = window.MOCK;
  const $ = (s, el = document) => el.querySelector(s);
  const main = $("#main");
  const ASSETS = "../assets";
  // ikona z gry (numer) albo portret wyrenderowany z modelu 3D ("r:c4340" -> assets/renders/c4340.png)
  const MAP_ICON = id => `${ASSETS}/map/icons/${id}.png`;          // ikony miejsc na mapie (atlasy menu gry)
  const ICON = id => typeof id === "string" && id.startsWith("r:") ? `${ASSETS}/renders/${id.slice(2)}.png` : `${ASSETS}/icons/${id}.png`;
  const L0 = 10496, MAXZ = 6;
  const fmt = n => (n ?? 0).toLocaleString("pl-PL");
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const pref = (k, d) => { try { return localStorage.getItem("er." + k) ?? d; } catch { return d; } };
  const savePref = (k, v) => { try { localStorage.setItem("er." + k, v); } catch { /* prywatne okno */ } };
  // "readable font" switch above the session summary button (styles: :root[data-font="plain"])
  const setPlainFont = on => { document.documentElement.dataset.font = on ? "plain" : ""; savePref("font", on ? "plain" : ""); };
  setPlainFont(pref("font", "") === "plain");
  const state = { spoilers: true, game: pref("game", "all"), mine: pref("mine", "1") === "1", mapPeek: false, offMine: new Set(["npc", "poi:landmark"]), bossFilter: "all", bossRegion: "all", bossQuery: "", quest: null, cat: "weapons", map: "M00",
    hideDone: false, mapQuery: "", qOpen: new Set(), qFilter: "all", off: new Set(["golden_rune", "material", "consumable", "ammo", "upgrade", "note", "npc", "poi:landmark"]) };

  // zakres gry dla wszystkich widoków (przełącznik w górnym pasku): wszystko / podstawka / DLC
  const gameOk = x => state.game === "all" || (state.game === "dlc") === !!x?.dlc;
  // przejście do konkretnej rzeczy spoza wybranego zakresu (np. link do questu z DLC) — pokaż wszystko
  function ensureGame(x) { if (x && !gameOk(x)) setGame("all", true); }
  // „Mój postęp” (przełącznik w górnym pasku): wszystkie widoki pokazują tylko to, co już zrobione albo zdobyte,
  // bez list i liczby tego, co jeszcze jest w grze; zawsze bez spoilerów (bieżący krok, ostrzeżenia o żywych bossach)
  const spoilers = () => state.spoilers || state.mine;
  const frac = (d, n) => state.mine ? `${d}` : `${d} / ${n}`;
  const layerCount = n => `${n[0] && !state.mine ? n[0] + "/" : ""}${n[1]}`;
  // mapa: przejście do miejsca spoza odkrytego terenu zdejmuje na chwilę granice widoku (mgła i znaczniki zostają)
  const mapMine = () => state.mine && !state.mapPeek;
  function syncMine() {
    $("#mineToggle").checked = state.mine;
    $("#spoilerToggle").checked = spoilers();
    $("#spoilerToggle").disabled = state.mine;
    $("#spoilerToggle").closest(".toggle").classList.toggle("disabled", state.mine);
  }
  function setMine(v) { state.mine = v; state.mapPeek = false; savePref("mine", v ? "1" : "0"); syncMine(); closeDrawer(); render(); }
  function setGame(g, quiet) {
    state.game = g; savePref("game", g); state.bossRegion = "all";
    document.querySelectorAll("[data-game]").forEach(b => b.classList.toggle("on", b.dataset.game === g));
    if (!quiet) render();
  }

  // dane wyciągnięte z gry (tools/extract)
  const cache = {};
  const load = name => cache[name] ??= fetch(`${ASSETS}/data/${name}.json`, { cache: "no-cache" }).then(r => r.ok ? r.json() : null).catch(() => null);
  const W = { bosses: [], pois: [], items: [], npcs: [], graces: [], quests: [], invaders: [], warps: [], summons: [] };

  /* ---------------- słowniki ---------------- */
  const KINDS = {
    weapon: ["Broń", "#d8b874"], armor: ["Zbroje", "#b7a98a"], talisman: ["Talizmany", "#e6c46e"], ash_of_war: ["Popioły wojny", "#a9c3d3"],
    sorcery: ["Czary", "#7aa7e0"], incantation: ["Inkantacje", "#f0cb63"], spirit_ash: ["Prochy duchów", "#8fd6cc"],
    golden_seed: ["Złote nasiona", "#ffd86b"], sacred_tear: ["Święte łzy", "#dff1f6"], memory_stone: ["Kamienie pamięci", "#c4b0ec"],
    dlc_blessing: ["Ostrodrzew i prochy czcigodne", "#b39ad6"], crystal_tear: ["Kryształowe łzy", "#e2918a"],
    smithing_stone: ["Kamienie kowalskie", "#a5a5a5"], somber_stone: ["Ponure kamienie", "#8496bd"], whetblade: ["Osełki", "#cfcfcf"],
    bell_bearing: ["Dzwonki kuliste", "#d39552"], cookbook: ["Receptury", "#b3c873"], stonesword_key: ["Klucze kamiennego miecza", "#bdbdbd"],
    map_fragment: ["Fragmenty map", "#d8c79a"], key_item: ["Przedmioty kluczowe", "#eaa955"], remembrance: ["Wizerunki", "#f5da8a"], great_rune: ["Wielkie runy", "#f5da8a"],
    golden_rune: ["Złote runy", "#c9a646"], material: ["Materiały", "#86a173"], consumable: ["Przedmioty użytkowe", "#8f8676"], ammo: ["Amunicja", "#8f8676"],
    upgrade: ["Konwalie", "#a7a7a7"], note: ["Notatki i listy", "#8f8676"],
  };
  const KIND_GROUPS = [
    ["Ekwipunek", ["weapon", "armor", "talisman", "ash_of_war", "sorcery", "incantation", "spirit_ash"]],
    ["Rozwój postaci", ["golden_seed", "sacred_tear", "memory_stone", "dlc_blessing", "crystal_tear"]],
    ["Kowalstwo", ["smithing_stone", "somber_stone", "whetblade"]],
    ["Klucze i odkrycia", ["bell_bearing", "cookbook", "stonesword_key", "map_fragment", "key_item", "remembrance", "great_rune"]],
    ["Pozostałe", ["golden_rune", "material", "consumable", "ammo", "upgrade", "note"]],
  ];
  const POI = { legacy: ["Główne lochy", "♛"], catacombs: ["Katakumby", "⛫"], cave: ["Jaskinie i pieczary", "◒"], tunnel: ["Tunele", "⛏"],
    evergaol: ["Wieczne więzienia", "⊚"], gaol: ["Lochy", "⊚"], hero_grave: ["Grobowce bohaterów", "⚰"], mausoleum: ["Mauzolea", "⚱"], tower: ["Wieże", "♜"], ruins: ["Ruiny", "⌂"], church: ["Kościoły i kaplice", "✝"],
    castle: ["Zamki i twierdze", "♖"], fort: ["Forty", "♖"], shack: ["Szopy i chaty", "⌂"], minor_erdtree: ["Pomniejsze Złote Drzewa", "♣"],
    village: ["Wioski i osady", "⌂"], landmark: ["Inne miejsca", "◇"] };

  /* ---------------- sigile i portrety ---------------- */
  const SIGIL = {
    demigod: '<path d="M20 40 L24 24 L32 32 L40 24 L44 40 Z"/><path d="M22 44 H42"/><circle cx="32" cy="18" r="2.2"/>',
    knight: '<path d="M22 44 V28 C22 21 26 17 32 17 C38 17 42 21 42 28 V44"/><path d="M22 31 H42"/><path d="M32 31 V44"/><path d="M32 17 V12"/>',
    beast: '<path d="M20 22 C22 32 24 40 26 46"/><path d="M28 18 C29 30 31 40 32 46"/><path d="M36 18 C35 30 34 40 33 46"/><path d="M44 22 C42 32 40 40 38 46"/>',
  };
  const sigil = (type, cls = "sigil") =>
    `<svg class="${cls}" viewBox="0 0 64 64" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <circle cx="32" cy="32" r="29" stroke-opacity=".35"/><circle cx="32" cy="32" r="26.5" stroke-opacity=".18"/>${SIGIL[type] || SIGIL.knight}</svg>`;
  const portrait = (icon, cls, type) => `<span class="portrait ${cls || ""}">${icon != null ? `<img src="${ICON(icon)}" alt="" loading="lazy">` : sigil(type)}</span>`;

  /* ---------------- stan: na żywo (backend) albo demo ---------------- */
  const API = "http://127.0.0.1:8765";
  const live = { on: false, file: null, slot: null, pinned: false, state: null, flags: {}, characters: null, inventory: null };
  const api = (p, ms = 6000) => fetch(API + p, { signal: AbortSignal.timeout(ms) }).then(r => r.ok ? r.json() : Promise.reject(new Error(r.status)));
  const qs = () => live.file ? `file=${live.file}&slot=${live.slot}` : "";
  // event flags from the save in chunks (the backend takes up to 1000 ids per request)
  async function readFlags(ids) {
    const out = {};
    for (let i = 0; i < ids.length; i += 900) Object.assign(out, (await api(`/api/flags?${qs()}&ids=${ids.slice(i, i + 900).join(",")}`)).flags);
    return out;
  }
  const hashPct = n => ((n * 2654435761) >>> 0) % 100;
  const demoSet = new Set();   // tryb demo: flagi „ustawione” przyciskiem symulacji
  const isSet = (flag, demoPct = 45) => !flag ? false : live.on ? !!live.flags[flag] : demoSet.has(flag) || hashPct(flag) < demoPct;
  let saveAgo = D.save.seconds_ago;
  setInterval(() => { saveAgo++; $("#lastSave").textContent = saveAgo < 120 ? saveAgo + " s" : saveAgo < 7200 ? Math.round(saveAgo / 60) + " min" : saveAgo < 172800 ? Math.round(saveAgo / 3600) + " h" : Math.round(saveAgo / 86400) + " dni"; }, 1000);

  let TR = null;
  function toMap(mapId, x, z) {
    const m = /^m(\d\d)_(\d\d)_(\d\d)/.exec(mapId || "");
    if (!m || !TR) return null;
    for (const [key, t] of Object.entries(TR)) if (t.area === +m[1])
      return { map: key, px: +m[2] * 256 + x + 128 - t.ox, py: t.size - (+m[3] * 256 + z + 128 - t.oz) };
    return null;
  }
  // krok zaliczony: własne flagi (any/all) albo dowolna flaga późniejszego etapu (`later`, quest_steps.py)
  // `gated` (sama flaga bossa) — liczy się dopiero po zaliczeniu poprzedniego kroku
  // `here` (flagi położenia NPC): postać czeka przy tym kroku — to bieżący krok, a wcześniejsze bez dowodu są
  // „za tobą” (zrobione albo pominięte — gra tego nie rozróżnia, ale nie są już do zrobienia)
  const questSteps = q => { let prev = true;
    const st = q.steps.map(s => { const fl = s.flags || [];
      const own = fl.length ? (s.mode === "all" ? fl.every(f => isSet(f, 50)) : fl.some(f => isSet(f, 50))) : false;
      const done = (own && (!s.gated || prev)) || (s.later || []).some(f => isSet(f, 50));
      if (!s.alt) prev = done;
      return { ...s, done, own: own && done, skipped: false }; });
    st.forEach((s, i) => { if (s.done && !s.own) {
      const by = st.slice(i + 1).find(x => x.own && !x.alt);
      if (by) s.why = `Zaliczony, bo zrobiłeś już dalszy krok: ${by.text}`; } });
    let h = -1;
    st.forEach((s, i) => { if (!s.alt && (s.here || []).some(f => isSet(f, 50))) h = i; });
    for (let i = 0; i < h; i++) if (!st[i].alt && !st[i].done) { st[i].done = true; st[i].skipped = true;
      st[i].why = "Postać czeka już przy dalszym kroku, więc ten jest za tobą. Gra nie zapisuje, czy go zrobiłeś, czy pominąłeś."; }
    return st; };

  // Wejście do DLC: kokon Miquelli na arenie Mohga (Pałac Mohgwynów, podziemia). Wątek dopisywany do questów —
  // kroki z flag save'a (pokonani bossowie, łaski pałacu, obszar startowy DLC 62002 / pierwsza łaska DLC).
  const DLC_COCOON = "Kokon Niebianina", DLC_ARRIVAL = "Cmentarna Równina";
  // znaczniki wejścia do DLC: kokon (mapa podziemi) i miejsce przybycia (mapa DLC)
  function dlcMarks(m) {
    const q = W.quests.find(x => x.id === "dlc-entry"), entered = q ? questSteps(q).at(-1).done : false, out = [];
    const cocoon = W.graces.find(g => g.name === DLC_COCOON), arrival = W.graces.find(g => g.name === DLC_ARRIVAL && g.dlc);
    if (cocoon && cocoon.map === m) out.push({ ...cocoon, done: entered, title: "Wejście do DLC",
      sub: spoilers() && !entered ? "Kokon w Pałacu Mohgwynów" : "Kokon Miquelli na arenie Mohga, po pokonaniu Radahna i Mohga" });
    if (arrival && arrival.map === m) out.push({ ...arrival, done: entered, title: "Początek Królestwa Cieni", sub: "Tu trafiasz z kokonu Miquelli" });
    return out;
  }
  function dlcEntryQuest() {
    const boss = pre => W.bosses.find(b => (b.name || "").startsWith(pre));
    const radahn = boss("Radahn, Gwiezdna Plaga"), mohg = boss("Mohg, Pan Krwi");
    const palace = W.graces.filter(g => (g.map_id || "").startsWith("m12_05")), arrival = W.graces.find(g => g.name === DLC_ARRIVAL && g.dlc);
    if (!radahn || !mohg || !palace.length) return null;
    return { id: "dlc-entry", name: "Wejście do Królestwa Cieni", npc: "Shadow of the Erdtree (DLC)", dlc: true, icon: null, parent: null, missable: false, locks: [],
      steps: [
        { text: "Pokonaj Radahna, Gwiezdną Plagę (Zamek Redmane, Caelid). Bez tego kokon nie zadziała.", text_safe: "Pokonaj potężnego wroga, którego wzywa festiwal w Zamku Redmane (Caelid).",
          flags: [radahn.flag, ...(radahn.alt_flags || [])], mode: "any", where: "Zamek Redmane, Caelid" },
        { text: "Dostań się do Pałacu Mohgwynów: teleport w Uświęconej Śnieżnej Dolinie albo Medalik Rycerza Czystej Krwi od Varrégo.",
          flags: palace.map(g => g.flag), mode: "any", where: "Pałac Mohgwynów (Podziemia)" },
        { text: "Pokonaj Mohga, Pana Krwi, na końcu pałacu.", text_safe: "Pokonaj pana tego pałacu.", flags: [mohg.flag, ...(mohg.alt_flags || [])], mode: "any", where: "Pałac Mohgwynów" },
        { text: "Dotknij ręki Miquelli w kokonie na arenie Mohga, a trafisz do Królestwa Cieni.", text_safe: "Znajdź na arenie przejście dalej.",
          flags: [62002, ...(arrival ? [arrival.flag] : [])], mode: "any", where: DLC_COCOON } ] };
  }
  async function loadWorld() {
    const [b, p, it, n, g, q, tr, mp, fx, inv, wp, sm] = await Promise.all(["bosses_all", "pois", "item_locations", "npcs", "graces", "quests", "map_transform", "map_pieces", "item_effects", "invaders", "warps", "summons"].map(load));
    // warps from the event scripts (extract_warps.py); none ending in Roundtable Hold, which has no world-map place
    W.warps = (wp || []).filter(w => !atRoundtable(w.src) && !atRoundtable(w.dst));
    W.summons = sm || [];                                  // znaki przywołania postaci (extract_summons.py)
    W.invaders = inv || [];                                // najeźdźcy (czerwone fantomy NPC, extract_world.py)
    W.pieces = mp || {};                                   // flagi fragmentów mapy (bit i maski = i-ty fragment)
    W.effects = fx || {};                                  // ukryte statystyki (extract_effects.py)
    // bossowie bez nazwy w plikach gry (np. Wyszczerbiony Drake na szczycie) zostają — nazwę dopisze backend (tabela CE)
    W.bosses = (b || []).map(x => x.name ? x : { ...x, name: x.name_en || "Boss bez nazwy w grze", unnamed: true })
      .map(x => x.render ? { ...x, icon: "r:" + x.render } : x);   // 3D portrait first, the drop's icon only without one
    W.pois = p || []; W.items = it || []; W.npcs = n || []; W.graces = g || [];
    W.quests = (q && q.entries) || []; TR = tr;
    const dq = dlcEntryQuest(); if (dq && W.quests.length) W.quests.push(dq);
    if (W.quests.length) state.quest = W.quests[0].id; else state.quest = D.quests[0].id;
  }

  async function loadLive() {
    // tylko potrzebne sekcje: pełny stan to ~1,5 MB (sam spis 3400 skarbów z map ~1 MB — ich stan i tak idzie przez /api/flags)
    const st = live.state = await api(`/api/state?${qs()}${qs() ? "&" : ""}sections=position,bloodstain,regions,inventory,equipment,stats,items,bosses,warnings,progress_detail&item_kind=acquired_flag`, 15000);
    live.file = st.save.file; live.slot = st.character.slot;
    const [chars, chron, sess, deaths] = await Promise.all([
      api("/api/characters").catch(() => null), api(`/api/days?${qs()}&limit=${Math.min(60, Math.max(7, D.chronicle?.length || 0))}`).catch(e => ({ failed: e.message || String(e) })),
      api(`/api/session?${qs()}`).catch(() => null), api(`/api/deaths?${qs()}&limit=500`).catch(() => null)]);
    // flagi wszystkich obiektów świata (łaski, bossowie, skarby, kroki questów) — czyta je backend z save'a
    const ids = new Set([...W.graces.map(x => x.flag), ...W.bosses.flatMap(x => [x.flag, ...(x.alt_flags || [])]), ...W.items.map(x => x.flag),
      ...W.quests.flatMap(q => q.steps.flatMap(s => [...(s.flags || []), ...(s.here || [])])), ...Object.values(W.pieces || {}).flat().map(p => p.f), ...W.invaders.map(x => x.flag),
      ...WORLD_FLAGS, ...W.pois.flatMap(p => [...(p.names || []), ...(p.people || [])].flatMap(n => [n[1], n[2]])), ...W.pois.flatMap(p => (p.restore || []).map(r => r.flag))].filter(Boolean));
    live.flags = await readFlags([...ids]); live.characters = chars; live.inventory = st.inventory || null;
    const c = st.character, lgId = c.last_grace?.entity_id, lg = W.graces.find(g => g.entity === lgId || g.entity === lgId - 1000);
    D.character = { slot: c.slot, name: c.name, level: c.level, playtime_s: c.playtime_s, runes_memory: c.runes_memory, deaths: c.deaths, last_grace: lg?.name || null };
    saveAgo = Math.max(0, Math.round((Date.now() - new Date(st.save.written_at)) / 1000));
    D.save = { file: st.save.file === "co2" ? "ER0000.co2" : "ER0000.sl2" };
    // piksele mapy liczy backend (position.map) — także w lochach (przez WorldMapLegacyConvParam; małe lochy = wejście, approx)
    const px = pos => pos && (pos.map || toMap(pos.map_id, pos.x, pos.z));
    const p = px(st.position);
    D.position = p ? { ...p, name: lg?.name || st.position.map_id } : { map: null, name: st.position.map_id };
    D.deathPoints = (deaths?.deaths || []).filter(d => d.position).map(d => px(d.position)).filter(Boolean);
    // plama krwi z save'a = zwykle ta sama, co ostatnia zapisana śmierć — jeden znacznik, nie dwa nałożone
    const bs = px(st.bloodstain);
    if (bs) D.deathPoints = [...D.deathPoints.filter(d => d.map !== bs.map || Math.hypot(d.px - bs.px, d.py - bs.py) > 3),
      { ...bs, last: true, runes: st.bloodstain.runes }];
    D.chronicleFailed = chron?.failed || null;
    D.chronicle = (chron?.days || []).map(dayModel);
    D.daysMore = chron?.more ? chron.days.at(-1).date : null;      // data najstarszego wczytanego dnia, gdy są starsze
    const s = sess?.session;
    D.session = s ? { duration: playtime(s.playtime_s), hours: (s.playtime_s / 3600).toFixed(1),
      bosses: s.bosses.length, graces: s.graces.length, items: s.items.length, deaths: s.deaths, levels: s.levels.gained, active: s.active,
      highlights: [...s.bosses.map(b => "Pokonano: " + b.name), ...s.graces.slice(0, 3).map(g => "Łaska: " + g.name)] } : null;
    live.aow = new Map(st.items.map(i => [i.name, i.collected]));
    live.hints = new Map(st.bosses.filter(b => b.hints).map(b => [b.name.toLowerCase(), b.hints]));
    // ta sama lista bossów co w backendzie: nazwy dla bezimiennych w grze + bossowie spoza danych świata (bez pozycji)
    const byFlag = new Map(W.bosses.map(b => [b.flag, b]));
    for (const x of st.bosses || []) {
      const w = byFlag.get(x.flag);
      if (w && w.unnamed) { w.name = x.name; w.unnamed = false; }
      else if (!w) W.bosses.push({ id: x.flag, flag: x.flag, name: x.name, name_en: x.name_en, region_pl: x.region,
        location: x.location, dlc: x.dlc, runes: x.runes, map_id: x.map_id, map: null, alt_flags: [], backendOnly: true });
    }
    live.on = true;
    $(".nav-note").textContent = `na żywo · ${D.save.file} · slot ${live.slot}`;
  }
  const KIND_EV = { boss_defeated: ["⚔", "boss", n => `Pokonano ${n}`], grace_discovered: ["❦", "grace", n => `Odkryto łaskę <em>${n}</em>`],
    item_collected: ["❖", "item", n => `Zdobyto <em>${n}</em>`], quest_step: ["✦", "quest", n => `Quest: <em>${n}</em>`],
    level_up: ["▲", "level", n => n], map_changed: ["◈", "map", n => `Zmiana obszaru: <em>${n}</em>`] };
  // dzień z /api/days (od 4:00 do 4:00) → karta kroniki: podsumowanie, zdarzenia od najnowszych, zdobyte przedmioty razem
  function dayModel(d) {
    const date = new Date(d.date + "T12:00"), today = new Date(Date.now() - 4 * 3600e3), y = new Date(today);
    y.setDate(today.getDate() - 1);
    const same = (a, b) => a.toDateString() === b.toDateString();
    const day = same(date, today) ? "Dziś" : same(date, y) ? "Wczoraj" : date.toLocaleDateString("pl-PL", { weekday: "long", day: "numeric", month: "long" });
    const summary = [d.playtime_s > 0 && `${playtime(d.playtime_s)} gry`, d.deaths > 0 && pl(d.deaths, "śmierć", "śmierci", "śmierci"),
      d.levels.gained > 0 && `poziom ${d.levels.from} → ${d.levels.to}`, d.runes_gained > 0 && `+${fmt(d.runes_gained)} run`].filter(Boolean).join(" · ");
    const time = ts => new Date(ts).toLocaleTimeString("pl-PL", { hour: "2-digit", minute: "2-digit" });
    const entries = d.events.filter(e => e.kind !== "item_obtained").reverse().map(e => { const [g, kind, txt] = KIND_EV[e.kind] || ["·", "map", n => n];
      return { t: time(e.ts), g, kind, txt: txt(esc(e.name)), sub: e.data?.text || "" }; });
    const got = [...new Set(d.items_obtained.map(k => { const [c, id] = k.split(":"); return findItem(c, +id)?.name; }).filter(Boolean))];
    if (got.length) entries.push({ t: "", g: "❖", kind: "item", sub: "kupione, z przeciwników albo wytworzone",
      txt: `Zdobyte przedmioty: <em>${got.slice(0, 12).map(esc).join(", ")}</em>${got.length > 12 ? ` i ${got.length - 12} innych` : ""}` });
    return { day, summary, entries };
  }

  /* ---------------- topbar ---------------- */
  function topbar() {
    const c = D.character;
    $("#charName").textContent = c.name;
    $("#stLevel").textContent = c.level;
    $("#stTime").textContent = c.playtime_s < 3600 ? Math.round(c.playtime_s / 60) + " min" : Math.round(c.playtime_s / 3600) + " h";
    $("#stDeaths").textContent = fmt(c.deaths);
    $("#stRunes").textContent = c.runes_memory < 1e6 ? fmt(c.runes_memory) : (c.runes_memory / 1e6).toLocaleString("pl-PL", { maximumFractionDigits: 1 }) + " mln";
    // portret w pasku: ikona hełmu z założonego ekwipunku (klik → widok postaci)
    const head = live.state?.equipment?.head, sig = $(".char-sigil");
    itemsIndex().then(() => { const it = head && findItem("armor", head.id);
      sig.classList.toggle("has-portrait", !!(it || live.file));
      const html = live.file ? `<img class="hp-render" src="${headSrc(live.file, live.slot, live.state?.equipment)}" alt="" data-fb="${it ? ICON(it.icon) : ""}" onerror="__hpFallback(this)">`
        : it ? `<img src="${ICON(it.icon)}" alt="">` : "";
      if (sig.dataset.html !== html) { sig.dataset.html = html; sig.innerHTML = html; } });   // bez migania przy każdym zapisie
    sig.onclick = $("#charName").onclick = () => { location.hash = "#character"; };
  }
  const ring = (done, total, label) => {
    const r = 32, c = 2 * Math.PI * r, off = state.mine ? 0 : c * (1 - done / Math.max(1, total));
    return `<div class="ring"><svg viewBox="0 0 74 74"><circle class="track" cx="37" cy="37" r="${r}" fill="none" stroke-width="1"/>
      <circle class="bar" cx="37" cy="37" r="${r}" fill="none" stroke-width="2.5" stroke-dasharray="${c}" stroke-dashoffset="${off}"/></svg>
      <div><div class="ring-num">${done}${state.mine ? "" : `<small> / ${total}</small>`}</div><div class="ring-label">${label}</div></div></div>`;
  };

  /* ---------------- bossowie (wszyscy, z plików gry) ---------------- */
  const visitedRegions = () => new Set(W.graces.filter(g => isSet(g.flag, 60)).map(g => g.region).filter(Boolean));
  // tryb bez spoilerów: boss „znany” dopiero po spotkaniu — nie wystarczy łaska gdziekolwiek w krainie.
  // Znany, gdy: pokonany · łaska na jego fragmencie mapy / w jego lochu (backend: nearby_grace, map_visited) ·
  // śmierć lub próba przy arenie · odkryta łaska w promieniu ~300 m · śmierć w promieniu ~150 m.
  function bossDiscovery() {
    const be = new Map((live.state?.bosses || []).map(x => [x.flag, x]));
    const graces = W.graces.filter(g => g.map && isSet(g.flag, 60)), deaths = D.deathPoints || [];
    const near = (b, p, r) => p.map === b.map && (p.px - b.px) ** 2 + (p.py - b.py) ** 2 <= r * r;
    return b => {
      const e = be.get(b.flag);
      if (e && (["nearby_grace", "map_visited", "flag", "alt_flag"].includes(e.discovered_by) || e.attempts > 0))
        return e.attempts > 0 ? "próby przy arenie" : e.discovered_by === "map_visited" ? "odwiedzony teren" : "łaska w pobliżu";
      if (b.map == null) return null;
      if (graces.some(g => near(b, g, 300))) return "łaska w pobliżu";
      if (deaths.some(d => near(b, d, 150))) return "śmierć w pobliżu";
      return null;
    };
  }
  function bossList() {
    const vr = visitedRegions(), disc = live.on ? bossDiscovery() : null;
    return W.bosses.map(b => {
      // pokonany: flaga z GameAreaParam albo alternatywna (bossowie dużej mapy, np. Radahn: 10… → 12…)
      const defeated = isSet(b.flag, 40) || (live.on && (b.alt_flags || []).some(f => isSet(f)));
      const how = defeated ? "pokonany" : disc ? disc(b) : vr.has(b.region_pl) ? "kraina" : null;   // makieta: dawna reguła krainy
      return { ...b, defeated, tier: bossTier(b), discovered: !!how, discovered_by: how, region: REGION_ALIAS[b.region_pl] || b.region_pl || (b.dlc ? "Królestwo Cieni" : "Ziemie Pomiędzy") };
    });
  }
  const hiddenBoss = b => spoilers() && !b.discovered && !(state.revealed ??= new Set()).has("b:" + b.id);
  // ostrzeżenia „zanim zabijesz…” z backendu: aktywne, gdy quest niedokończony, a boss blokujący jeszcze żyje
  const bossFlagOf = id => +String(id || "").replace("boss-", "");
  function activeWarnings() {
    if (!live.on) return [];
    const bl = new Map(bossList().map(b => [b.flag, b]));
    return (live.state?.warnings || []).map(w => ({ ...w, b: bl.get(bossFlagOf(w.boss_id)) }))
      .map(w => ({ ...w, hidden: w.b && hiddenBoss(w.b), text: (spoilers() && w.warning_safe) || w.warning }));
  }
  const warnHtml = w => `<p class="note warn">⚠ <b>${w.hidden ? "Nieznany wróg" : esc(w.b?.name || w.boss)}</b> · quest <a href="#quests" data-wq="${esc(w.quest_id)}">„${esc(w.quest)}”</a>${w.npc ? ` (${esc(w.npc)})` : ""}: ${esc(w.text || "zabicie tego bossa może przerwać quest.")}</p>`;
  // próby z backendu: zarejestrowane śmierci przy arenie (promień 60 m) przed pokonaniem; null = nie wiadomo
  const bossAttempts = b => (live.state?.bosses || []).find(x => x.flag === b.flag)?.attempts ?? null;
  // ---------- rangi bossów (z danych gry: wizerunek, runy, lokacja) ----------
  const GREAT_RUNE_EN = new Set(["Godrick the Grafted", "Starscourge Radahn", "Morgott, the Omen King", "Rykard, Lord of Blasphemy",
    "Malenia, Blade of Miquella", "Mohg, Lord of Blood"]);
  const TIER = {
    great_rune: { name: "Wielki run", short: "Wielki run", glyph: "ᛟ", desc: "Półbóg. Po pokonaniu zostawia Wielki run." },
    legend: { name: "Legenda", short: "Legenda", glyph: "♛", desc: "Boss z wizerunkiem albo ostateczne wyzwanie krainy." },
    major: { name: "Wielki boss", short: "Wielki", glyph: "◆", desc: "Boss głównego lochu lub wyjątkowo groźny przeciwnik." },
    normal: { name: "Boss", short: "Boss", glyph: "◇", desc: "Boss lochu lub pola." },
    minor: { name: "Pomniejszy", short: "Pomniejszy", glyph: "·", desc: "Słabszy boss, mała nagroda w runach." },
    trivial: { name: "Ledwo boss", short: "Ledwo boss", glyph: "∘", desc: "Formalnie boss, w praktyce zwykły przeciwnik albo spotkanie fabularne." },
  };
  const TIER_ORDER = Object.keys(TIER);
  const LEGACY_AREAS = new Set([10, 11, 13, 14, 15, 16, 19, 20, 21, 22, 25, 28]);   // główne lochy (Burzowy Zamek, Leyndell, Akademia…)
  function bossTier(b) {
    if (GREAT_RUNE_EN.has(b.name_en)) return "great_rune";
    if (b.backendOnly && !b.runes) return "normal";          // boss tylko z tabeli CE — runy nieznane
    const r = b.runes || 0, area = +(b.map_id || "m00").slice(1, 3);
    if (b.remembrance || r >= (b.dlc ? 380000 : 300000)) return "legend";
    if (r < 1500) return "trivial";
    const legacy = LEGACY_AREAS.has(area) && (b.map_id || "").slice(4, 6) !== "01" || (area === 20 || area === 21);   // m10_01 = Kaplica Wyczekiwania
    if (legacy || r >= (b.dlc ? 200000 : 70000)) return "major";
    if (r < (b.dlc ? 75000 : 5000)) return "minor";
    return "normal";
  }
  const tierBadge = (t, cls = "") => `<span class="tier-badge t-${t} ${cls}" title="${esc(TIER[t].desc)}"><i>${TIER[t].glyph}</i>${TIER[t].short}</span>`;
  // krainy nadrzędne → podkrainy (geografia gry); bossowie podkrainy liczą się też do krainy nadrzędnej
  const REGION_TREE = {
    "Pogrobno": ["Burzowe Wzgórze", "Zamek Burzowego Całunu", "Opuszczone cmentarzysko"],
    "Płaczący Półwysep": [],
    "Jeziorna Liurnia": ["Trakt Bellum", "Ołtarz Blasku Księżyca", "Akademia Rai Lucarii"],
    "Caelid": ["Smocze Kurhany Greyoll", "Bagno Aeonii"],
    "Płaskowyż Altus": ["Obrzeża stolicy", "Góra Gelmir", "Wulkaniczny Dwór", "Leyndell, królewska stolica", "Leyndell, stolica popiołów", "Eldeński Tron",
      "Podziemia porzuconych", "Urwisko usiane ruinami"],
    "Szczyty Olbrzymów": ["Zakazane Krainy", "Szczyt Płomienia", "Uświęcona śnieżna dolina", "Święte Drzewo Miquelli", "Elphael, Podpora Świętego Drzewa", "Przeklęte Farum Azula", "Kamienna platforma"],
    "Podziemia": ["Rzeka Siofra", "Nokron, Wieczne Miasto", "Rzeka Ainsel", "Główne koryto rzeki Ainsel", "Głębiny", "Jezioro Zgnilizny", "Pałac Mohgwynów"],
    "Cmentarna równina": ["Belurat, osada przy wieży", "Szczelina kamiennego sarkofagu"],
    "Ostrowyż Altus": ["Donżon cienia", "Donżon cienia, dzielnica kościelna", "Magazyn z okazami", "Włości Midry"],
    "Ziemie Wieży": ["Enir-Ilim"],
  };
  const REGION_ALIAS = { "Land of the Tower": "Ziemie Wieży", "Kraina Wieży": "Ziemie Wieży", "Cmentarna Równina": "Cmentarna równina" };   // nazwy jak w menu podróży gry
  const REGION_PARENT = Object.fromEntries(Object.entries(REGION_TREE).flatMap(([p, kids]) => kids.map(k => [k, p])));
  const regionMatch = (r, sel) => sel === "all" || r === sel || REGION_PARENT[r] === sel;
  // grupowanie / sortowanie bossów (domyślnie wg rangi, w grupie od najcenniejszych)
  const BOSS_GROUPS = {
    tier: { name: "Ranga", key: b => b.tier, order: (x, y) => TIER_ORDER.indexOf(x) - TIER_ORDER.indexOf(y), head: k => tierBadge(k, "big") + `<span class="bg-desc">${esc(TIER[k].desc)}</span>` },
    region: { name: "Kraina", key: b => b.region, order: (x, y) => x.localeCompare(y, "pl"), head: k => `<span class="region-name">${esc(k)}</span>` },
    status: { name: "Status", key: b => b.defeated ? 1 : 0, order: (x, y) => x - y, head: k => `<span class="region-name">${k ? "Pokonani" : "Niepokonani"}</span>` },
    none: { name: "Bez grup", key: () => 0, order: () => 0, head: () => "" },
  };
  const BOSS_SORTS = {
    runes: { name: "Runy (malejąco)", f: (x, y) => (y.runes || 0) - (x.runes || 0) },
    tier: { name: "Ranga", f: (x, y) => TIER_ORDER.indexOf(x.tier) - TIER_ORDER.indexOf(y.tier) || (y.runes || 0) - (x.runes || 0) },
    name: { name: "Nazwa", f: (x, y) => x.name.localeCompare(y.name, "pl") },
    region: { name: "Kraina", f: (x, y) => x.region.localeCompare(y.region, "pl") || (y.runes || 0) - (x.runes || 0) },
    alive: { name: "Najpierw niepokonani", f: (x, y) => x.defeated - y.defeated || (y.runes || 0) - (x.runes || 0) },
  };
  function viewBosses() {
    const all = bossList().filter(gameOk).filter(b => !state.mine || b.defeated);
    const done = all.filter(b => b.defeated).length;
    const regions = [...new Set(all.map(b => b.region))].sort((x, y) => x.localeCompare(y, "pl"));
    const gk = state.bossGroup || "tier", sk = state.bossSort || "runes", g = BOSS_GROUPS[gk], so = BOSS_SORTS[sk];
    const q = (state.bossQuery || "").toLowerCase();
    const list = all.filter(b => (state.bossFilter === "all" || state.mine || (state.bossFilter === "alive" ? !b.defeated : b.defeated)) &&
      regionMatch(b.region, state.bossRegion) && (!state.bossTier || b.tier === state.bossTier) &&
      (!q || (b.name + " " + (b.name_en || "") + " " + b.region).toLowerCase().includes(q))).sort(so.f);
    const chip = (attr, k, l, on) => `<button class="chip ${on ? "on" : ""}" data-${attr}="${esc(k)}">${l}</button>`;
    const sel = (id, opts, cur) => `<select class="it-sel" id="${id}">${opts.map(([k, v]) => `<option value="${esc(k)}" ${k === cur ? "selected" : ""}>${esc(v)}</option>`).join("")}</select>`;
    const groups = new Map();
    for (const b of list) { const k = g.key(b); if (!groups.has(k)) groups.set(k, []); groups.get(k).push(b); }
    // panel krain: postęp w każdej krainie (z uwzględnieniem filtrów gry i rangi, bez filtra krainy)
    const base = all.filter(b => !state.bossTier || b.tier === state.bossTier);
    const stat = rs => { const l = base.filter(b => rs.includes(b.region)); return { n: l.length, d: l.filter(b => b.defeated).length }; };
    const tops = [...new Set(regions.map(r => REGION_PARENT[r] || r))].map(t => {
      const kids = regions.filter(r => REGION_PARENT[r] === t).map(r => ({ r, ...stat([r]) })).filter(x => x.n).sort((x, y) => y.n - x.n);
      return { r: t, kids, ...stat([t, ...kids.map(k => k.r)]) };
    }).filter(x => x.n).sort((x, y) => (x.d === x.n) - (y.d === y.n) || y.n - x.n);
    state.regOpen ??= new Set();
    const row = (x, cls = "") => `<button class="ra-row ${cls} ${state.bossRegion === x.r ? "on" : ""} ${x.d === x.n && !state.mine ? "complete" : ""}" data-br="${esc(x.r)}">
        <span class="ra-name">${esc(x.r)}</span><span class="ra-cnt">${x.d === x.n && !state.mine ? "✓ " : ""}${frac(x.d, x.n)}</span>
        ${state.mine ? "" : `<span class="qbar"><i style="width:${x.d / x.n * 100}%"></i></span>`}</button>`;
    const regionAside = `<aside class="region-aside corners"><div class="eyebrow">Krainy</div>
      <button class="ra-row ${state.bossRegion === "all" ? "on" : ""}" data-br="all"><span class="ra-name">Wszystkie krainy</span><span class="ra-cnt">${frac(base.filter(b => b.defeated).length, base.length)}</span></button>
      ${tops.map(t => { const open = state.regOpen.has(t.r) || t.kids.some(k => k.r === state.bossRegion) || state.bossRegion === t.r;
        return `<div class="ra-node ${open ? "open" : ""}">${t.kids.length ? `<button class="ra-tog" data-rt="${esc(t.r)}" aria-label="Rozwiń">▸</button>` : ""}${row(t, "top")}
          ${t.kids.length ? `<div class="ra-kids">${t.kids.map(k => row(k, "kid")).join("")}</div>` : ""}</div>`; }).join("")}
      <p class="view-sub ra-note">Kraina obejmuje swoje podkrainy (▸ rozwija).${state.mine ? "" : " Ukończone spadają na dół listy."}</p></aside>`;
    main.innerHTML = `<div class="view wide">
      <div class="view-head"><div><div class="eyebrow">Wrogowie godni wspomnienia</div><h1 class="title">Bossowie</h1>
        <div class="view-sub">${pl(all.length, "boss", "bossów", "bossów")} w tym widoku${live.on ? " · stan z twojego save'a" : " · stan przykładowy"}. Kliknij, by zobaczyć nagrody i miejsce.</div></div>
        ${ring(done, all.length, "pokonanych")}</div>
      ${(() => { const ws = activeWarnings(), known = ws.filter(w => !w.hidden), unknown = ws.length - known.length;
        if (!known.length) return "";                // only hidden ones: a bare count says nothing (quests show them with ⚠)
        // bez spoilerów: ostrzeżenia o wrogach, których gracz jeszcze nie spotkał, tylko jako liczba (tekst zdradzałby bossa)
        const more = unknown ? `<p class="view-sub bw-more">Oraz ${pl(unknown, "ostrzeżenie dotyczy", "ostrzeżenia dotyczą", "ostrzeżeń dotyczy")} wrogów, których jeszcze nie spotkałeś. Szczegóły są w questach oznaczonych ⚠.</p>` : "";
        return `<details class="boss-warnings" ${known.length <= 3 ? "open" : ""}><summary><span class="eyebrow">Zanim zabijesz…</span>
          <span class="bw-count">${pl(known.length, "aktywne ostrzeżenie", "aktywne ostrzeżenia", "aktywnych ostrzeżeń")}${unknown ? " · " : ""}${unknown ? pl(unknown, "ukryte", "ukryte", "ukrytych") : ""}</span></summary>
          ${known.map(warnHtml).join("")}${more}</details>`; })()}
      <div class="it-bar boss-bar">
        <input class="search it-q" id="bq" type="search" placeholder="Szukaj bossa lub krainy…" value="${esc(state.bossQuery || "")}">
        <label class="it-lbl"><span>Grupuj</span>${sel("bgroup", Object.entries(BOSS_GROUPS).map(([k, v]) => [k, v.name]), gk)}</label>
        <label class="it-lbl"><span>Sortuj</span>${sel("bsort", Object.entries(BOSS_SORTS).map(([k, v]) => [k, v.name]), sk)}</label>
        ${state.mine ? "" : `<span class="it-chips">${chip("bf", "all", "Wszyscy", state.bossFilter === "all")}${chip("bf", "alive", "Niepokonani", state.bossFilter === "alive")}${chip("bf", "felled", "Pokonani", state.bossFilter === "felled")}</span>`}
        <span class="it-chips tier-filters">${chip("bt", "", "Każda ranga", !state.bossTier)}${TIER_ORDER.map(t => { const n = all.filter(b => b.tier === t);
          return n.length ? `<button class="chip tier-chip t-${t} ${state.bossTier === t ? "on" : ""}" data-bt="${t}" title="${esc(TIER[t].desc)}"><i>${TIER[t].glyph}</i>${TIER[t].name}<small>${frac(n.filter(b => b.defeated).length, n.length)}</small></button>` : ""; }).join("")}</span>
      </div>
      <div class="boss-layout"><div class="boss-groups">${state.bossRegion !== "all" ? `<div class="ra-active">Kraina: <b>${esc(state.bossRegion)}</b> <button class="chip" data-br="all">✕ pokaż wszystkie</button></div>` : ""}
      ${[...groups.entries()].sort((x, y) => g.order(x[0], y[0])).map(([k, items]) => {
        const tot = all.filter(b => g.key(b) === k && regionMatch(b.region, state.bossRegion) && (!state.bossTier || b.tier === state.bossTier) &&
          (!q || (b.name + " " + (b.name_en || "") + " " + b.region).toLowerCase().includes(q)));
        return `<section class="region boss-group ${gk === "tier" ? "tg-" + k : ""}">${gk === "none" ? "" : `<div class="region-head">${g.head(k)}<span class="region-count">${frac(tot.filter(b => b.defeated).length, tot.length)}</span><span class="region-line"></span></div>`}
          <div class="grid">${items.map(bossCard).join("")}</div></section>`; }).join("") || '<p class="view-sub">Nic nie pasuje do filtrów.</p>'}</div>
      ${regionAside}</div></div>`;
    main.querySelectorAll("[data-bf]").forEach(b => b.onclick = () => { state.bossFilter = b.dataset.bf; viewBosses(); });
    main.querySelectorAll("[data-bt]").forEach(b => b.onclick = () => { state.bossTier = b.dataset.bt; viewBosses(); });
    $("#bgroup").onchange = e => { state.bossGroup = e.target.value; viewBosses(); };
    $("#bsort").onchange = e => { state.bossSort = e.target.value; viewBosses(); };
    main.querySelectorAll("[data-br]").forEach(b => b.onclick = () => { state.bossRegion = b.dataset.br; viewBosses(); });
    main.querySelectorAll("[data-rt]").forEach(b => b.onclick = e => { e.stopPropagation(); const r = b.dataset.rt;
      state.regOpen.has(r) ? state.regOpen.delete(r) : state.regOpen.add(r); b.closest(".ra-node").classList.toggle("open"); });
    const qi = $("#bq"); let t; qi.oninput = () => { clearTimeout(t); t = setTimeout(() => { state.bossQuery = qi.value; const pos = qi.selectionStart; viewBosses(); const n = $("#bq"); n.focus(); n.setSelectionRange(pos, pos); }, 200); };
    main.querySelectorAll("[data-boss]").forEach(c => c.onclick = () => openBoss(+c.dataset.boss));
  }
  // link do questu z ostrzeżenia (lista bossów i szuflada bossa)
  document.addEventListener("click", e => { const a = e.target.closest("[data-wq]"); if (a) { e.preventDefault(); goQuest(a.dataset.wq); } });
  function bossCard(b) {
    const hid = hiddenBoss(b);
    return `<button class="card corners tier-${b.tier} ${b.defeated ? "done" : ""} ${hid ? "hidden-spoiler" : ""}" data-boss="${b.id}">
      ${hid ? "" : tierBadge(b.tier, "on-card")}
      ${b.defeated && !hid ? '<span class="felled-mark" title="Pokonany">✓</span>' : ""}
      ${portrait(hid ? null : b.icon, "card-portrait", b.icon ? "demigod" : "knight")}
      <div class="card-name">${hid ? "Nieznany wróg" : esc(b.name)}</div>
      <div class="card-meta"><span>${hid ? "??????" : (b.runes ? pl(b.runes, "run", "runy", "runów") : "")}</span></div></button>`;
  }
  // najbliższa łaska. W lochach (wszystko poza otwartym światem m60/m61) liczymy w obrębie tego samego lochu,
  // po lokalnych współrzędnych z pliku mapy — rzut lochu na mapę świata (Farum Azula, Leyndell, jaskinie) myli odległości.
  // exclude: nazwa łaski pomijanej (łaska z nazwą bossa pojawia się dopiero po walce).
  // Areny w osobnej przestrzeni (sen, przeszłość, po walce z poprzednikiem) — bez łaski w pobliżu; łaska, z której się tam idzie.
  const ARENA_ACCESS = { "Dragonlord Placidusax": "Przy wielkim moście", "Maliketh, the Black Blade": "Przy wielkim moście",
    "Rennala, Queen of the Full Moon": "Sala debat", "Elden Beast": "Eldeński Tron" };
  function nearestGrace(o, exclude) {
    const area = +(o.map_id || "m60").slice(1, 3), ok = g => g.name && g.name !== exclude;
    const fixed = exclude && ARENA_ACCESS[o.name_en] && W.graces.find(g => g.name === ARENA_ACCESS[o.name_en] && g.map_id?.slice(0, 3) === o.map_id?.slice(0, 3) || g.name === ARENA_ACCESS[o.name_en]);
    if (fixed) return { ...fixed, dist: null, inside: true, access: true };
    // łaska w samej arenie (< 25 m od bossa) pojawia się dopiero po walce — dla bossów ją pomijamy
    const cut = area !== 60 && area !== 61 ? 45 : 25, bare = (exclude || "").replace(/\s*\(.*\)$/, "");
    const arena = g => exclude && (g.name === bare || o.pos && g.pos && g.map_id === o.map_id && (g.pos[0] - o.pos[0]) ** 2 + (g.pos[1] - o.pos[1]) ** 2 + (g.pos[2] - o.pos[2]) ** 2 < cut * cut);
    if (o.pos && area !== 60 && area !== 61) {
      const same = W.graces.filter(g => g.map_id === o.map_id && g.pos && ok(g) && !arena(g));
      if (same.length) {
        let best = null, bd = 1e18;
        for (const g of same) { const d = (g.pos[0] - o.pos[0]) ** 2 + (g.pos[1] - o.pos[1]) ** 2 + (g.pos[2] - o.pos[2]) ** 2; if (d < bd) { bd = d; best = g; } }
        return { ...best, dist: Math.round(Math.sqrt(bd)), inside: true };
      }
    }
    let best = null, bd = 1e18;
    for (const g of W.graces) if (g.map === o.map && g.px != null && ok(g) && !arena(g) && (atRoundtable(g) === atRoundtable(o))) { const d = (g.px - o.px) ** 2 + (g.py - o.py) ** 2; if (d < bd) { bd = d; best = g; } }
    return best && { ...best, dist: Math.round(Math.sqrt(bd)) };
  }
  // wiersz listy w szufladzie: `attrs` (np. data-go) robi z niego przycisk; ikona, nazwa i opis po prawej
  const listRow = (attrs, img, label, right) => `<${attrs ? `button class="reward xreward" ${attrs}` : `div class="reward"`}><span class="rw">${img ? `<img src="${img}">` : ""}${label}</span><span>${right}${attrs ? " ›" : ""}</span></${attrs ? "button" : "div"}>`;
  // wiersz nagrody (boss, najeźdźca): klik otwiera kartę przedmiotu, gdy jest w katalogu
  const rewardRow = (r, it) => listRow(it && `data-go="item:${it.category}:${it.id}"`, r.icon != null && ICON(r.icon), esc(r.name), KINDS[r.kind]?.[0] || "");
  // Twierdza Okrągłego Stołu: postacie, najeźdźca i skarby z m11_10 w jednej liście (gra nie ma mapy wnętrza)
  const roundtable = () => ({ grace: W.graces.find(atRoundtable), invaders: W.invaders.filter(atRoundtable), spots: W.items.filter(atRoundtable),
    npcs: W.npcs.filter((n, i, all) => atRoundtable(n) && all.findIndex(x => atRoundtable(x) && x.name === n.name) === i) });
  function openRoundtable() {
    const { grace: g, npcs, invaders, spots } = roundtable();
    drawer(`<div class="d-hero"><span class="portrait hero-portrait item"><img src="${MAP_ICON(48)}" alt=""></span>
      <div class="d-title">Twierdza Okrągłego Stołu</div><div class="d-loc">${isSet(g.flag, 60) ? "odkryta" : "jeszcze nieodkryta"}</div></div>
      <p class="view-sub" style="margin:10px 0 0">Gra nie ma mapy wnętrza Twierdzy, dostajesz się tam tylko szybką podróżą do łaski ${esc(g.name)}.</p>
      ${npcs.length ? `<div class="d-section"><h4>Postacie</h4>${npcs.map(n => { const q = npcQuest(n); return listRow(q && `data-go="quest:${esc(q.id)}"`, null, esc(n.name), q ? "quest" : ""); }).join("")}</div>` : ""}
      ${invaders.length ? `<div class="d-section"><h4>Najeźdźcy</h4>${invaders.map(x => listRow(`data-go="invader:${x.id}"`, null, hiddenInvader(x) ? "Nieznany najeźdźca" : esc(x.name), isSet(x.flag) ? "pokonany" : "niepokonany")).join("")}</div>` : ""}
      ${spots.length ? `<div class="d-section"><h4>Skarby</h4>${spots.map((t, i) => listRow(`data-rt-spot="${i}"`, t.items[0]?.icon != null && ICON(t.items[0].icon), esc(t.items.map(x => x.name).join(", ")), isSet(t.flag) ? "zebrane" : "do zebrania")).join("")}</div>` : ""}`,
      () => document.querySelectorAll("[data-rt-spot]").forEach(b => b.onclick = () => openSpot(spots[+b.dataset.rtSpot])));
  }
  // najeźdźca: bez spoilerów imię i nagrody widać dopiero po pokonaniu
  const hiddenInvader = x => spoilers() && !isSet(x.flag);
  function openInvader(x) {
    const done = isSet(x.flag), hid = hiddenInvader(x);
    drawer(`<div class="d-hero">${portrait(null, "hero-portrait" + (done ? "" : " alive"), "knight")}<div class="eyebrow">${x.summoned ? "Pojedynek" : "Najeźdźca"}${x.dlc ? " · DLC" : ""}</div>
      <div class="d-title">${hid ? (x.summoned ? "Nieznany przeciwnik" : "Nieznany najeźdźca") : esc(x.name)}</div><div class="d-loc">${esc(x.region_pl || "")}</div></div>
      <div class="d-stats"><div><b>${done ? "✓" : "—"}</b><span>${done ? "Pokonany" : "Niepokonany"}</span></div>${x.summoned ? "" : `<div><b>${hid ? "?" : x.rewards.length}</b><span>Nagrody</span></div>`}</div>
      <p class="view-sub" style="margin:10px 0 0">${x.summoned ? "Czerwony fantom, którego przyzywasz znakiem. To jedna z kilku walk po kolei; za wygranie wszystkich nagrodę daje postać przy znaku."
        : "Czerwony fantom, który najeżdża twój świat w tej okolicy. Pokonany już nie wraca."}</p>
      ${hid ? '<p class="note">Imię i nagrody zobaczysz po pokonaniu (tryb bez spoilerów).</p>' : x.rewards.length ? `<div class="d-section"><h4>Nagrody</h4>${x.rewards.map(r => rewardRow(r, findItem(r.cat, r.id))).join("")}
        ${x.quest_rewards ? '<p class="view-sub" style="margin:8px 0 0">Nagroda zależy od etapu questu tej postaci.</p>' : ""}</div>` : ""}
      ${x.stats && !hid ? bossStatsHtml(x.stats) : ""}
      ${live.on && x.stats && !hid ? '<div class="d-section" id="hitsBox"></div>' : ""}
      ${x.map ? `<div class="d-section"><h4>Na mapie</h4><div class="minimap" id="minimap"></div></div>` : ""}`,
      () => { if (x.stats) fillHits(x.stats);
        if (x.map) miniMap($("#minimap"), x.map, x.px, x.py, null, [{ label: "Pokaż na mapie", primary: true, run: () => goMap(x) }]); });
  }
  // hidden enemy stats from the game files (NpcParam + area scaling, bosses_all.json `stats`)
  const PHYS = { standard: "Zwykłe", slash: "Cięte", strike: "Obuchowe", pierce: "Kłute" };
  const dmgName = k => PHYS[k] || AFF[k][0];
  function bossStatsHtml(st) {
    const neg = Object.entries(st.absorb), lo = Math.min(...neg.map(n => n[1])), hi = Math.max(...neg.map(n => n[1]));
    const statuses = Object.entries(st.status), open = statuses.filter(([, t]) => t).sort((a, b) => a[1][0] - b[1][0]);
    // weakest damage: the lowest reduction (all four physical types tied read as one), real weakness when below zero
    const low = lo < hi ? neg.filter(([, v]) => v === lo).map(([k]) => k) : [];
    const lowNames = Object.keys(PHYS).every(k => low.includes(k)) ? ["obrażenia fizyczne", ...low.filter(k => !PHYS[k]).map(dmgName)] : low.map(dmgName);
    const weakDmg = lowNames.length ? `${lowNames.join(", ").toLowerCase()} (${lo}%)` : "";
    const easy = open.filter(([, t]) => t[0] === open[0][1][0]).map(([k]) => k);
    const weakSt = easy.length ? `${easy.map(k => AFF[k][0].toLowerCase()).join(", ")} (próg ${open[0][1][0]})` : "";
    return `<div class="d-section"><h4>Statystyki</h4>
      <div class="d-stats"><div><b>${fmt(st.hp)}</b><span>Punkty życia</span></div><div><b>${st.poise}</b><span>Postawa</span></div></div>
      <h5 class="sub-h">Redukcja obrażeń</h5><div class="neg-grid">${neg.map(([k, v]) =>
        statCell(esc(dmgName(k)), v + "%", k, v === lo && lo < hi ? "weak" : v >= 40 ? "strong" : "")).join("")}</div>
      <h5 class="sub-h">Odporność na statusy (próg po kolejnych wywołaniach)</h5><div class="neg-grid st">${statuses.map(([k, t]) =>
        statCell(esc(AFF[k][0]), t ? t.join(" → ") : "odporny", k, t ? "" : "strong")).join("")}</div>
      <p class="ib-note"${low.length === 1 ? elAttr(low[0]) : ""}><b>${lo < 0 ? "Słaby na" : "Najmniej odporny na"}</b> ${esc(weakDmg || "nic szczególnego")}</p>
      ${weakSt ? `<p class="ib-note"${easy.length === 1 ? elAttr(easy[0]) : ""}><b>Najłatwiejszy status</b> ${esc(weakSt)}</p>` : '<p class="ib-note"><b>Statusy</b> odporny na wszystkie</p>'}
      <p class="view-sub" style="margin:8px 0 0">Pierwsze przejście, wartości z plików gry. Przy kilku fazach: zwykle pierwsza faza.</p></div>`;
  }
  // ---------- the player's weapons against an enemy: attack rating, damage of one hit, hits to kill ----------
  // weapon_calc.json (tools/extract/extract_damage.py); the formula matches the MIT weapon calculator by ThomasJClark
  let CALC = null;
  const calcIndex = async () => CALC ??= await load("weapon_calc");
  function weaponAR(w, upgrade, attrs) {
    const rf = CALC.reinforce[w.reinforce]?.[upgrade], el = CALC.element[w.element];
    if (!rf || !el) return null;
    return w.base.map((b, t) => {
      const base = b * rf[t], by = [0, 1, 2, 3, 4].filter(s => el[t][s] !== null);
      if (!base) return 0;
      if (by.some(s => attrs[s] < w.req[s])) return base * 0.6;          // stat below requirement: -40%, no scaling
      const g = CALC.graphs[w.graph[t]];
      return base * (1 + by.reduce((sum, s) => sum + curve(g, attrs[s]) / 100 * (el[t][s] === -1 ? w.scaling[s] : el[t][s]) / 100 * rf[5 + s], 0));
    });
  }
  // share of an attack that passes flat defense (attack/defense ratio curve, community-derived; 10%..90%)
  const defenseMul = (atk, def) => { const r = atk / def;
    return r >= 8 ? .9 : r >= 2.5 ? .9 - (8 - r) ** 2 / 151.25 : r >= 1 ? .7 - (2.5 - r) ** 2 / 7.5 : r >= .125 ? .1 + (r - .125) ** 2 / 2.552 : .1; };
  const PHYS_ATTR = ["slash", "strike", "pierce", "standard"];          // EquipParamWeapon +0x104
  const hitDamage = (ar, attr, st) => ar.reduce((sum, a, t) => !a ? sum
    : sum + a * defenseMul(a, st.defense[t]) * (1 - st.absorb[[PHYS_ATTR[attr] || "standard", "magic", "fire", "lightning", "holy"][t]] / 100), 0);
  async function fillHits(st) {
    // only the weapons put in your hands (equipment, 3 slots per hand), not everything carried
    const at = live.state?.stats?.attributes, eq = live.state?.equipment;
    if (!$("#hitsBox")) return;
    if (!at || !eq) return $("#hitsBox").remove();
    const inv = [...(eq.right_weapons || []), ...(eq.left_weapons || [])].filter(Boolean);
    await Promise.all([calcIndex(), itemsIndex()]);
    const box = $("#hitsBox"); if (!box || !CALC) return;
    const attrs = [at.strength, at.dexterity, at.intelligence, at.faith, at.arcane], seen = new Set(), rows = [];
    for (const e of inv) {
      const w = CALC.weapons[e.id - (e.upgrade || 0)], it = findItem("weapon", e.base_id ?? e.id), cls = it?.stats?.class;
      if (!w || !it || seen.has(e.id) || (cls >= 50 && cls <= 56) || (cls >= 81 && cls <= 86)) continue;   // bows and ammo: damage comes from arrows
      seen.add(e.id);
      const ar = weaponAR(w, e.upgrade || 0, attrs), dmg = ar && hitDamage(ar, w.attr, st);
      if (dmg > 0) rows.push({ it, up: e.upgrade || 0, dmg, hits: Math.ceil(st.hp / dmg) });
    }
    rows.sort((a, b) => a.hits - b.hits || b.dmg - a.dmg);
    box.innerHTML = `<h4>Twoje bronie: ile ciosów</h4>${rows.map(r => listRow(`data-go="item:weapon:${r.it.id}"`, ICON(r.it.icon),
      esc(r.it.name + (r.up ? " +" + r.up : "")), `${pl(r.hits, "cios", "ciosy", "ciosów")} · ${Math.floor(r.dmg)} na cios`)).join("")
      || '<p class="view-sub" style="margin:0">Nie masz w rękach broni do walki wręcz (łuki i kusze pomijamy, bo obrażenia zależą od strzał).</p>'}
      <p class="view-sub" style="margin:8px 0 0">Bronie z Twoich rąk i Twoje atrybuty. Liczę pierwszy lekki cios jedną ręką, bez statusów,
        umiejętności broni, talizmanów i wzmocnień.</p>`;
  }
  function openBoss(id) {
    const b = bossList().find(x => x.id === id);
    if (hiddenBoss(b)) return drawer(`<div class="d-hero">${portrait(null, "hero-portrait alive", "knight")}<div class="d-title">Nieznany wróg</div>
      <div class="d-loc">${esc(b.region)}</div></div><div class="rule"></div>
      <p class="note">Jeszcze go nie spotkałeś. Ten wróg kryje się w krainie <b>${esc(b.region)}</b>. Odsłoni się, gdy odkryjesz łaskę w jego pobliżu albo staniesz z nim do walki.</p><button class="btn" id="reveal">Odsłoń mimo to</button>`,
      () => $("#reveal").onclick = () => { (state.revealed ??= new Set()).add("b:" + id); render(); openBoss(id); });
    const ng = nearestGrace(b, b.name), hint = live.hints?.get((b.name_en || "").toLowerCase());
    const tries = bossAttempts(b), warns = activeWarnings().filter(w => w.b?.flag === b.flag);
    drawer(`<div class="d-hero">${portrait(b.icon, "hero-portrait" + (b.defeated ? "" : " alive"), "knight")}
      <div class="eyebrow">${esc(b.region)}${b.dlc ? " · DLC" : ""}</div><div class="d-title">${esc(b.name)}</div>
      <div class="d-loc">${esc(b.location || b.name_en || "")}</div><div class="rtags">${tierBadge(b.tier)}${!b.defeated && b.discovered_by && live.on ? `<span class="rtag">odkryty: ${esc(b.discovered_by)}</span>` : ""}</div></div>
      <div class="d-stats"><div><b>${b.defeated ? "✓" : "—"}</b><span>${b.defeated ? "Pokonany" : "Niepokonany"}</span></div>
        <div><b>${fmt(b.runes)}</b><span>${plural(b.runes || 0, "Run", "Runy", "Runów")}</span></div><div><b>${TIER[b.tier].glyph}</b><span>${TIER[b.tier].name}</span></div>
        ${live.on && tries != null ? `<div title="Śmierci przy arenie (do 60 m od bossa) zarejestrowane przez backend${b.defeated ? " przed pokonaniem" : ""}"><b>${tries}</b><span>${plural(tries, "Próba", "Próby", "Prób")}</span></div>` : ""}</div>
      ${warns.length ? `<div class="d-section"><h4>Zanim zabijesz</h4>${warns.map(warnHtml).join("")}</div>` : ""}
      <div class="d-section"><h4>Jak dotrzeć</h4><ol class="steps">${ng ? `<li>${ng.access ? `Do areny dochodzi się od miejsca łaski: <b>${esc(ng.name)}</b>` : `Najbliższe miejsce łaski przed areną: <b>${esc(ng.name)}</b> (${ng.dist} m${ng.inside ? ", w tym samym lochu" : ""})${ng.region && !ng.inside ? ", " + esc(ng.region) : ""}`}.</li>` : ""}
        ${b.approx && !ng?.inside ? "<li>Boss jest w lochu, znacznik stoi przy wejściu.</li>" : b.approx ? "<li>Znacznik na mapie stoi przy wejściu do lochu.</li>" : ""}${hint ? `<li>${esc(hint)}</li>` : ""}
        ${!ng && !hint ? "<li>Pozycja tego bossa nie jest jeszcze przeliczona na mapę świata.</li>" : ""}</ol></div>
      ${b.map ? `<div class="d-section"><h4>Na mapie</h4><div class="minimap" id="minimap"></div></div>` : ""}
      ${b.stats ? bossStatsHtml(b.stats) : ""}
      ${live.on && b.stats ? '<div class="d-section" id="hitsBox"></div>' : ""}
      ${questLinks(bossQuests(b))}
      ${b.rewards?.length ? `<div class="d-section"><h4>Nagrody</h4>${b.rewards.map(r => rewardRow(r, itemByName(r.name))).join("")}</div>` : ""}
      ${b.remembrance ? `<div class="d-section"><h4>Wizerunek</h4><div id="bossRem">${listRow(itemByName(b.remembrance) ? `data-go="item:goods:${itemByName(b.remembrance).id}"` : null,
        ICON(itemByName(b.remembrance)?.icon), esc(b.remembrance), "")}</div></div>` : ""}`,
      () => {
        if (b.stats) fillHits(b.stats);
        const rem = b.remembrance && itemByName(b.remembrance);
        if (rem) sourcesIndex().then(() => { if ($("#bossRem")) $("#bossRem").insertAdjacentHTML("beforeend", remembranceHTML(rem)); });
        if (b.map) miniMap($("#minimap"), b.map, b.px, b.py, b.icon, [{ label: "Pokaż na mapie", primary: true, run: () => goMap(b) }]);
      });
  }

  /* ---------------- szuflada / modal ---------------- */
  let mini;
  function drawer(html, after) {
    if (mini) { mini.remove(); mini = null; }
    $("#drawerBody").innerHTML = html;
    $("#drawer").classList.add("open"); $("#drawer").setAttribute("aria-hidden", "false"); $("#drawer").scrollTop = 0;
    after && setTimeout(after, 60);
  }
  const closeDrawer = () => { $("#drawer").classList.remove("open"); $("#drawer").setAttribute("aria-hidden", "true"); };
  $("#drawerClose").onclick = closeDrawer;
  const closeModal = () => $("#modal").classList.remove("open");
  document.addEventListener("keydown", e => { if (e.key === "Escape") { closeDrawer(); closeModal(); } });
  $("#modal").onclick = e => { if (e.target.id === "modal") closeModal(); };

  /* ---------------- questy ---------------- */
  function viewQuests() {
    const real = W.quests.length > 0;
    const quests = real ? W.quests.map(q => ({ id: q.id, name: q.name, npc: q.npc, icon: q.icon, dlc: q.dlc, missable: q.missable, confidence: q.confidence, parent: q.parent,
      // tryb bez spoilerów: niezaliczone kroki w wersji, która nie zdradza losów postaci (quest_spoilers.py)
      steps: questSteps(q).map(s => { const safe = spoilers() && !s.done;
        return { text: (safe && s.text_safe) || s.text, where: s.where || "", done: s.done, skipped: s.skipped, why: s.why, alt: !!s.alt, end: !!s.end, next: (safe && s.next_safe) || (safe && s.text_safe) || s.next }; }),
      locks: (q.locks || []).map(l => ({ text: (spoilers() && l.warning_safe) || l.warning })) }))
      : D.quests.map(q => ({ ...q, icon: D.questIcons[q.id] }));
    // progress without alternative steps; an ending (e.g. the character's death) finishes the quest
    const progress = x => { const st = x.steps.filter(s => !s.alt), d = st.filter(s => s.done).length;
      return { d, n: st.length, fin: x.steps.some(s => s.end && s.done) || (d > 0 && d === st.length) }; };
    for (const q of quests) { const i = progress(q).fin ? -1 : q.steps.findIndex(s => !s.done && !s.alt);
      q.steps.forEach((s, k) => s.current = k === i);
      if (real) q.next = i >= 0 ? { text: q.steps[i].next || q.steps[i].text, hint: q.steps[i].where } : { text: "Quest ukończony", hint: "" }; }
    // status of a whole thread (quest + side threads): done when it and every started side thread are finished
    const family = x => [x, ...quests.filter(c => c.parent === x.id).flatMap(family)];
    const qStatus = x => { const fam = family(x).map(progress);
      return fam[0].fin && fam.every(p => p.fin || !p.d) ? "done" : fam.some(p => p.d) ? "active" : "new"; };
    // a finished quest whose started side thread is still open points at it
    for (const x of quests) { const open = real && progress(x).fin && family(x).slice(1).find(c => { const p = progress(c); return p.d && !p.fin; });
      if (open) x.next = { text: `Quest ukończony. Otwarty powiązany wątek: ${open.name}.`, hint: "" }; }
    // „Mój postęp”: tylko wątki odkryte (choć jeden zrobiony krok); z kroków widać zrobione i bieżący
    const seen = x => !state.mine || family(x).some(f => f.steps.some(s => s.done));
    const allRoots = quests.filter(x => !x.parent || !quests.some(p => p.id === x.parent));
    const roots = allRoots.filter(gameOk).filter(seen), shown = roots.flatMap(family);
    const visible = x => state.mine ? x.steps.filter(s => s.done || s.current) : x.steps;
    const q = quests.find(x => x.id === state.quest && seen(x) && gameOk(x)) || shown[0];
    if (!q) { main.innerHTML = `<div class="view"><div class="view-head"><div><div class="eyebrow">Losy napotkanych dusz</div><h1 class="title">Questy</h1>
      <div class="view-sub">Nie masz jeszcze żadnego odkrytego questu. Pojawi się tu, gdy zrobisz jego pierwszy krok.</div></div></div></div>`; return; }
    for (let p = q.parent; p; p = quests.find(x => x.id === p)?.parent) state.qOpen.add(p);   // rozwiń przodków wybranego
    const blur = s => spoilers() && !s.done && !s.current;
    const total = shown.reduce((a, x) => a + progress(x).n, 0), doneAll = shown.reduce((a, x) => a + progress(x).d, 0);
    main.innerHTML = `<div class="view">
      <div class="view-head"><div><div class="eyebrow">Losy napotkanych dusz</div><h1 class="title">Questy</h1>
        <div class="view-sub">${real ? `${pl(roots.length, "wątek", "wątki", "wątków")} · kroki odhaczają się z flag zapisu gry` : "Dane przykładowe, zbiór questów jeszcze się buduje."}</div></div>
        ${ring(doneAll, total, "kroków za tobą")}</div>
      <div class="filters">${[["all", "Wszystkie"], ["active", "W toku"], ...(state.mine ? [] : [["new", "Nierozpoczęte"]]), ["done", "Ukończone"]]
        .map(([k, l]) => `<button class="chip ${state.qFilter === k ? "on" : ""}" data-qf="${k}">${l}<small class="chip-n">${roots.filter(r => k === "all" || qStatus(r) === k).length}</small></button>`).join("")}</div>
      <div class="quests"><div class="qlist">${[["active", "W toku"], ["new", "Nierozpoczęte"], ["done", "Ukończone"]]
        .filter(([k]) => state.qFilter === "all" || state.qFilter === k).map(([k, l]) => { const list = roots.filter(r => qStatus(r) === k); if (!list.length) return "";
          return `<div class="qsection ${k}"><div class="qsection-head">${l}<span>${list.length}</span></div>${list.map(x => qNode(x, 0)).join("")}</div>`; }).join("")
        || '<p class="view-sub">Brak questów w tej grupie.</p>'}</div>
      <article class="qdetail corners">
        ${q.parent ? `<button class="q-parent" data-q="${esc(q.parent)}">↖ Część questu: ${esc(quests.find(p => p.id === q.parent)?.name || q.parent)}</button>` : ""}
        <div class="q-head">${portrait(q.icon, "qd-portrait", "knight")}
        <div style="flex:1"><div class="eyebrow">${esc(q.npc)}</div><h2 class="q-title">${esc(q.name)}</h2></div>
        <div class="view-sub">${state.mine ? pl(progress(q).d, "krok za tobą", "kroki za tobą", "kroków za tobą") : `${progress(q).d} z ${pl(progress(q).n, "kroku", "kroków", "kroków")}`}</div></div>
        ${(progress(q).fin ? [] : q.locks || []).filter(l => l.text).map(l => `<p class="note warn" style="margin-top:20px">⚠ ${esc(l.text)}</p>`).join("")}
        ${q.missable ? `<p class="note warn" style="margin-top:12px">Ten quest można przegapić. Postępuj według kolejności kroków.</p>` : ""}
        <div class="next"><div class="eyebrow">Co dalej</div><div class="next-text">${linkify(q.next.text)}</div><div class="next-hint">${linkify(q.next.hint || "")}</div></div>
        <ol class="timeline">${visible(q).map(s => `<li class="${s.done ? "done" : s.current ? "current" : "future"}${s.alt ? " alt" : ""}${s.skipped ? " skipped" : ""}"><span class="diamond"></span>${s.skipped ? '<span class="alt-tag">za tobą</span>' : ""}${s.alt ? `<span class="alt-tag">${s.end ? "zakończenie" : "alternatywa"}</span>` : ""}
          ${blur(s) ? `<span style="filter:blur(5px)">${esc(s.text)}</span>` : linkify(s.text)}<span class="where">${blur(s) ? "ukryte w trybie bez spoilerów" : linkify(s.where)}</span>${s.why ? `<span class="why">${linkify(s.why)}</span>` : ""}</li>`).join("")}</ol>
        ${kidsOf(q.id).length ? `<div class="d-section"><h4>Powiązane wątki</h4>${kidsOf(q.id).map(k => { const p = progress(k);
          return `<button class="reward q-link" data-q="${esc(k.id)}"><span class="rw">${portrait(k.icon, "q-mini", "knight")}${esc(k.name)}</span><span>${frac(p.d, p.n)}</span></button>`; }).join("")}</div>` : ""}
      </article></div></div>`;
    // klik w quest: wybiera go, a quest nadrzędny od razu rozwija (ponowny klik w już wybrany — zwija)
    main.querySelectorAll("[data-q]").forEach(b => b.onclick = () => { const id = b.dataset.q;
      if (kidsOf(id).length) { if (state.quest === id && state.qOpen.has(id)) state.qOpen.delete(id); else state.qOpen.add(id); }
      state.quest = id; viewQuests(); });
    main.querySelectorAll("[data-qt]").forEach(b => b.onclick = e => { e.stopPropagation(); const id = b.dataset.qt;
      state.qOpen.has(id) ? state.qOpen.delete(id) : state.qOpen.add(id); viewQuests(); });
    main.querySelectorAll("[data-qf]").forEach(b => b.onclick = () => { state.qFilter = b.dataset.qf; viewQuests(); });

    function kidsOf(id) { return quests.filter(c => c.parent === id && seen(c)); }
    function qNode(x, depth) {
      const kids = kidsOf(x.id), open = state.qOpen.has(x.id), { d, n, fin } = progress(x);
      const kd = kids.reduce((a, k) => a + progress(k).d, 0), kt = kids.reduce((a, k) => a + progress(k).n, 0);
      return `<div class="qnode ${depth ? "child" : ""} ${kids.length ? "has-kids" : ""} ${open ? "open" : ""}">
        <div class="qrow">${kids.length ? `<button class="qtoggle ${open ? "open" : ""}" data-qt="${esc(x.id)}" aria-expanded="${open}" aria-label="${open ? "Zwiń" : "Rozwiń"} powiązane wątki">▸</button>` : `<span class="qtoggle-sp">${depth ? "↳" : ""}</span>`}
          <button class="qitem ${x.id === q.id ? "on" : ""} ${fin ? "finished" : ""} ${x.locks?.length && !fin ? "warned" : ""}" data-q="${esc(x.id)}">
            ${portrait(x.icon, "q-portrait", "knight")}<span class="qitem-name">${esc(x.name)}</span><span class="qitem-frac">${frac(d, n)}</span>
            <span class="qitem-npc">${esc(x.npc)}${x.dlc ? " · DLC" : ""}${kids.length ? ` · <em class="q-kids">${pl(kids.length, "wątek", "wątki", "wątków")} (${frac(kd, kt)})</em>` : ""}</span>
            ${state.mine ? "" : `<span class="qbar"><i style="width:${fin ? 100 : d / Math.max(1, n) * 100}%"></i></span>`}</button></div>
        ${kids.length && open ? `<div class="qchildren">${kids.map(k => qNode(k, depth + 1)).join("")}</div>` : ""}</div>`;
    }
  }

  /* ---------------- przedmioty ---------------- */
  // never obtainable: bare-fist and naked-body placeholders, the Ragged set (armor 610000-611100) removed in patch 1.03
  const unobtainable = i => (i.category === "weapon" && i.id === 110000) || (i.category === "armor" && (i.id < 101000 || (i.id >= 610000 && i.id < 612000)));
  const CATS = [
    { id: "weapons", name: "Broń", f: i => i.category === "weapon" && i.icon > 0 && !(i.stats?.class >= 81 && i.stats?.class <= 86) && i.stats?.class !== 33 && !unobtainable(i) },
    { id: "armor", name: "Zbroje", f: i => i.category === "armor" && i.icon > 0 && !unobtainable(i) },
    { id: "talismans", name: "Talizmany", f: i => i.category === "talisman" },
    { id: "spells", name: "Czary i inkantacje", f: i => i.kind === "sorcery" || i.kind === "incantation" },
    { id: "aow", name: "Popioły wojny", f: i => i.category === "ash_of_war" && !/dummy/i.test(i.name) },
    { id: "spirits", name: "Prochy duchów", f: i => i.kind === "spirit_ash" && !/\+\d+\s*$/.test(i.name) },
    // przedmioty moda: osobna zakładka, poza licznikami kolekcji (widoczna, gdy mod jest zainstalowany)
    { id: "coop", name: "Seamless Coop", f: i => i.kind === "seamless", extra: true },
  ];
  // the same item can sit in the save under another id (`alt_ids`, extract_icons.py)
  const isId = (it, id) => id === it.id || !!it.alt_ids?.includes(id);
  // posiadanie: ekwipunek z backendu (gdy już go podaje) → popioły wojny z flag → demo
  function have(i) {
    if (live.on && live.inventory) {
      const inv = live.inventory, pool = { weapon: inv.weapons, armor: inv.armor, talisman: inv.talismans, ash_of_war: inv.ashes,
        goods: [...(inv.goods || []), ...(inv.key_items || [])] }[i.category] || [];
      // broń: po base_id (ulepszenia/nasycenia); prochy duchów +1…+10: ID bazowe = ID − ID % 100
      return pool.some(x => isId(i, x.base_id ?? x.id) || isId(i, x.id) || (i.category === "goods" && i.id % 100 === 0 && x.id - x.id % 100 === i.id && x.id >= 200000));
    }
    if (live.on) return live.aow?.has(i.name_en) ? live.aow.get(i.name_en) : null;
    return hashPct(i.id) < 38;
  }
  const sameItem = (x, it) => x.cat === it.category && (isId(it, x.id) || (it.category === "weapon" && x.id - (x.id % 10000) === it.id));
  const whereItem = it => W.items.filter(t => t.items.some(x => sameItem(x, it)));

  /* ---------------- szczegóły przedmiotu: statystyki z gry, opis z gry, notka „do czego służy” ---------------- */
  let ITEMS = null;
  async function itemsIndex() {
    if (!ITEMS) ITEMS = new Map((await load("items") || []).flatMap(i => [i.id, ...(i.alt_ids || [])].map(id => [`${i.category}:${id}`, i])));
    return ITEMS;
  }
  const findItem = (cat, id) => ITEMS?.get(`${cat}:${id}`) || ITEMS?.get(`${cat}:${id - (cat === "weapon" ? id % 10000 : 0)}`);
  const ATTR = { str: "Siła", dex: "Zręczność", int: "Inteligencja", fai: "Wiara", arc: "Tajemność" };
  const DMG = { phys: "Fizyczne", magic: "Magiczne", fire: "Ogień", lightning: "Błyskawice", holy: "Święte" };
  const ABS = { phys: "Fizyczna", slash: "Cięcie", strike: "Obuch", pierce: "Pchnięcie", magic: "Magia", fire: "Ogień", lightning: "Błyskawice", holy: "Święta" };
  const ATTR_INS = { str: "Siłą", dex: "Zręcznością", int: "Inteligencją", fai: "Wiarą", arc: "Tajemnością" };
  const num = v => (+v).toLocaleString("pl-PL", { maximumFractionDigits: 1 });
  // odmiana: plural(5, "punkt", "punkty", "punktów") → „punktów”
  const plural = (n, one, few, many) => { n = Math.abs(n); if (n === 1) return one; const d = n % 10, t = n % 100;
    return d >= 2 && d <= 4 && (t < 12 || t > 14) ? few : many; };
  // czas gry: „2 h 05 min”, „45 min” (zaokrąglone do minut, bez „60 min”)
  const playtime = s => { const m = Math.round(s / 60); return m >= 60 ? `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, "0")} min` : `${m} min`; };
  const pl = (n, one, few, many) => `${fmt(n)} ${plural(n, one, few, many)}`;
  const grade = v => v >= 175 ? "S" : v >= 140 ? "A" : v >= 90 ? "B" : v >= 60 ? "C" : v >= 25 ? "D" : v > 0 ? "E" : "–";
  const KIND_NOTE = {
    golden_seed: "Złote nasiono: przy miejscu łaski zwiększa liczbę użyć świętej butelki. Jedne z najcenniejszych znalezisk na początku gry.",
    sacred_tear: "Święta Łza: przy miejscu łaski zwiększa moc świętej butelki, więc Butelka szkarłatnych łez leczy więcej PŻ.",
    memory_stone: "Kamień pamięci: daje dodatkowe miejsce na zapamiętane czary.",
    smithing_stone: "Kamień kowalski: ulepsza zwykłe bronie u kowala (np. Hewg w Twierdzy Okrągłego Stołu).",
    somber_stone: "Ponury kamień kowalski: ulepsza bronie unikatowe, czyli te, których nie da się nasycić.",
    whetblade: "Osełka: odblokowuje nowe nasycenia broni przy łasce (popioły wojny i powinowactwa).",
    bell_bearing: "Dzwonek kulisty: oddaj go Cieniom bliźniaczej służki w Twierdzy Okrągłego Stołu, a doda nowe towary do sklepu.",
    cookbook: "Receptury: odblokowują nowe przepisy w Zestawie do wytwarzania.",
    stonesword_key: "Klucz kamiennego miecza: otwiera pieczęć na posągu impa (zwykle 1–2 klucze). Za pieczęcią czeka łup albo przejście.",
    map_fragment: "Fragment mapy: odsłania w menu kolejny region mapy.",
    crystal_tear: "Kryształowa łza: wkładasz ją do Butelki niesamowitego eliksiru przy łasce. Dwie łzy naraz dają czasowe wzmocnienie.",
    dlc_blessing: "Wzmacnia w Królestwie Cieni błogosławieństwo Ostrodrzewa (twoją obronę i siłę) albo przyzywane duchy.",
    golden_rune: "Złoty run: zużyj, by dostać runy. Warto je chomikować i wydać na poziom, gdy brakuje niewiele.",
    material: "Materiał do Zestawu do wytwarzania. Robisz z niego strzały, bomby i maści.",
    key_item: "Przedmiot kluczowy: otwiera drogę albo popycha do przodu któryś z questów.",
    remembrance: "Wizerunek: wymień go u Enii w Twierdzy Okrągłego Stołu na jedną z dwóch unikatowych nagród (lub na runy).",
    great_rune: "Wielki run: przywróć mu moc w Boskiej Wieży, załóż przy łasce i użyj Łuku runicznego, by aktywować jego błogosławieństwo.",
    note: "Notatka lub list. Podpowiada, gdzie szukać łupu albo jak pchnąć quest.",
    consumable: "Przedmiot użytkowy do szybkiego użycia w walce lub eksploracji.",
    ammo: "Amunicja do łuków i kusz.",
  };
  // ---------- ramki przedmiotów: rzadkość × żywioł/status (np. legendarny + mróz) ----------
  // a box about a damage type or status gets that element's look (styles: [data-el])
  const elAttr = k => AFF[k] ? ` data-el="${k}" style="--c:${AFF[k][1]}"` : "";
  const statCell = (label, value, el, cls = "") => `<span class="neg${cls ? " " + cls : ""}"${elAttr(el)}>${label}<b>${value}</b></span>`;
  const AFF = { bleed: ["Krwotok", "#c8283c"], frost: ["Odmrożenie", "#8fdcff"], poison: ["Trucizna", "#8fbf3a"], rot: ["Szkarłatna zgnilizna", "#e0662a"],
    sleep: ["Sen", "#b39cf0"], madness: ["Szaleństwo", "#ffbe2e"], death: ["Plaga śmierci", "#8a6fa0"],
    magic: ["Magia", "#5b9cff"], fire: ["Ogień", "#ff6a1f"], lightning: ["Błyskawica", "#f7e65c"], holy: ["Święte", "#fff0c2"] };
  const RARITY = ["", "Zwykły", "Rzadki", "Legendarny"];
  // nasycenie broni z ID w ekwipunku: (id % 10000) / 100
  const INFUSE = { 1: ["Ciężki"], 2: ["Ostry"], 3: ["Wyważony"], 4: ["Ognisty", "fire"], 5: ["Płomiennej sztuki", "fire"], 6: ["Błyskawiczny", "lightning"],
    7: ["Uświęcony", "holy"], 8: ["Magiczny", "magic"], 9: ["Mroźny", "frost"], 10: ["Zatruty", "poison"], 11: ["Krwawy", "bleed"], 12: ["Okultystyczny"] };
  function affinities(it, rawId) {
    const s = it?.stats, out = [];
    Object.entries(s?.status || {}).sort((a, b) => b[1] - a[1]).forEach(([k, v]) => out.push({ k, v }));
    Object.entries(s?.attack || {}).filter(([k, v]) => k !== "phys" && v > 0).sort((a, b) => b[1] - a[1]).forEach(([k, v]) => out.push({ k, v }));
    const inf = it?.category === "weapon" && rawId ? INFUSE[Math.floor((rawId % 10000) / 100)] : null;
    if (inf?.[1] && !out.some(a => a.k === inf[1])) out.unshift({ k: inf[1], v: 0, infuse: true });
    return { list: out, infuse: inf?.[0] || null };
  }
  // klasy + zmienne CSS ramki i „klejnoty” żywiołów w rogach
  function frame(it, rawId) {
    if (!it) return { cls: "", style: "", gems: "" };
    const { list } = affinities(it, rawId), r = it.rarity || 0, c = k => AFF[k][1];
    return { cls: `fr fr-r${r} ${list.length ? "fr-aff" : ""} ${list.length > 1 ? "fr-dual" : ""}`,
      style: list.length ? `--a1:${c(list[0].k)};--a2:${c((list[1] || list[0]).k)}` : "",
      gems: list.slice(0, 2).map((a, i) => `<i class="fr-gem g${i}" style="--c:${c(a.k)}" title="${AFF[a.k][0]}${a.v ? " " + a.v : ""}"></i>`).join("") };
  }
  function rarityTags(it, rawId) {
    const { list, infuse } = affinities(it, rawId), r = it?.rarity || 0;
    const tags = [r >= 2 ? `<span class="rtag r${r}">${RARITY[r]}</span>` : "", infuse ? `<span class="rtag">${infuse}</span>` : "",
      ...list.map(a => `<span class="rtag"${elAttr(a.k)}>${AFF[a.k][0]}${a.v && it.stats?.status?.[a.k] ? " " + a.v : ""}</span>`)].filter(Boolean);
    return tags.length ? `<div class="rtags">${tags.join("")}</div>` : "";
  }
  function usageNote(it) {
    const kind = it.kind;
    const s = it.stats;
    if (it.category === "weapon" && s) {
      const sc = Object.entries(s.scaling).filter(([, v]) => v > 0).sort((a, b) => b[1] - a[1]);
      const req = Object.entries(s.requires).filter(([, v]) => v > 0).map(([k, v]) => `${ATTR[k]} ${v}`).join(", ");
      const elem = Object.entries(s.attack).filter(([k, v]) => k !== "phys" && v > 0).map(([k]) => DMG[k].toLowerCase());
      const w = s.weight, heft = w < 4 ? "lekka" : w < 10 ? "średnia" : "ciężka";
      if (s.attack.phys < 60 && s.scaling.int >= 90) return `Kostur do rzucania czarów. Moc czarów rośnie z Inteligencją (skalowanie ${grade(s.scaling.int)}). Wymaga: ${req || "nic"}.`;
      if (s.attack.phys < 60 && (s.scaling.fai >= 60 || s.scaling.arc >= 60)) return `Pieczęć do inkantacji. Moc rośnie z ${s.scaling.arc > s.scaling.fai ? "Tajemnością" : "Wiarą"}. Wymaga: ${req || "nic"}.`;
      if (/tarcza/i.test(it.name)) return `Tarcza: trzymasz ją w lewej ręce i blokujesz ciosy (L1). ${w >= 10 ? "Ciężka tarcza: świetnie chroni, ale mocno obciąża. Dla postaci z dużą Siłą i Wytrzymałością." : w >= 4 ? "Średnia tarcza: dobry kompromis między ochroną a wagą." : "Lekka tarcza: niewiele waży, dobra do parowania."} Wymaga: ${req || "nic"}. Waga ${num(w)}.`;
      const top = sc.slice(0, 2).map(([k, v]) => `${ATTR_INS[k]} (${grade(v)})`).join(" i ");
      const build = !sc.length ? "dowolnej postaci" : sc[0][0] === "str" ? (sc[1]?.[0] === "dex" && sc[1][1] >= sc[0][1] * .7 ? "jakościowej (Siła + Zręczność)" : "siłowej")
        : sc[0][0] === "dex" ? "zręcznościowej" : sc[0][0] === "int" ? "czarodzieja" : sc[0][0] === "fai" ? "wiary" : "tajemności (krwawienie, trucizna)";
      return `Broń dla postaci ${build}: ${top ? `najlepiej skaluje się z ${top}` : "nie skaluje się z atrybutami"}. ${elem.length ? `Zadaje też obrażenia: ${elem.join(", ")}. ` : ""}Wymaga: ${req || "nic"}. To ${heft} broń (waga ${num(w)}).`;
    }
    if (it.category === "armor" && s) {
      const best = Object.entries(s.absorb).sort((a, b) => b[1] - a[1]).slice(0, 2).map(([k]) => ABS[k].toLowerCase());
      return `Element zbroi: najlepiej chroni przed obrażeniami: ${best.join(" i ")}. ${s.weight < 4 ? "Lekki" : s.weight < 9 ? "Średni" : "Ciężki"} (waga ${num(s.weight)}). Pilnuj obciążenia, żeby nie stracić szybkiego uniku.`;
    }
    if (it.category === "talisman") return "Talizman: załóż go w wolnym gnieździe talizmanu. Kolejne gniazda dają Sakwy na talizman (nagrody za niektórych bossów).";
    if (it.category === "ash_of_war") return "Popiół wojny: przy łasce nadaj go broni. Zmienia jej umiejętność, a często też dostępne nasycenia.";
    if (s?.fp != null) return `${kind === "incantation" ? "Inkantacja" : "Czar"}: zapamiętaj przy łasce i rzucaj ${s.requires.fai > s.requires.int ? "pieczęcią" : "kosturem"}. Koszt ${s.fp} PS. Wymaga: ${[s.requires.int ? `Inteligencja ${s.requires.int}` : "", s.requires.fai ? `Wiara ${s.requires.fai}` : ""].filter(Boolean).join(", ") || "nic"}.`;
    if (kind === "spirit_ash") return "Prochy duchów: przyzwij ducha Dzwonkiem przyzwania, gdy w pobliżu stoi kamień wskrzeszenia. Ulepszysz je u Roderiki w Twierdzy Okrągłego Stołu.";
    return KIND_NOTE[kind] || null;
  }
  function statsHTML(it) {
    const s = it.stats; if (!s) return "";
    const tbl = rows => `<div class="neg-grid two">${rows.map(([label, v, el]) => statCell(label, v, el)).join("")}</div>`;
    if (it.category === "weapon") return `<div class="d-section"><h4>Statystyki</h4>
      ${tbl(Object.entries(s.attack).filter(([, v]) => v > 0).map(([k, v]) => [DMG[k], v, k]))}
      <div class="stat-sub">Skalowanie</div>${tbl(Object.entries(s.scaling).filter(([, v]) => v > 0).map(([k, v]) => [ATTR[k], grade(v)]))}
      <div class="stat-sub">Wymagania</div>${tbl(Object.entries(s.requires).filter(([, v]) => v > 0).map(([k, v]) => [ATTR[k], v]))}
      ${tbl([["Waga", num(s.weight)]])}</div>`;
    if (it.category === "armor") return `<div class="d-section"><h4>Ochrona</h4>${tbl(Object.entries(s.absorb).map(([k, v]) => [ABS[k], num(v) + "%", k]))}${tbl([["Waga", num(s.weight)]])}</div>`;
    if (s.fp != null) return `<div class="d-section"><h4>Statystyki</h4>${tbl([["Koszt PS", s.fp], ...(s.requires.int ? [["Inteligencja", s.requires.int]] : []), ...(s.requires.fai ? [["Wiara", s.requires.fai]] : [])])}</div>`;
    return "";
  }
  // opis miejsca skarbu (zebrane, kraina, najbliższa łaska), w karcie przedmiotu i w liście skarbu
  // a one-time drop of a specific enemy (scarab, NPC…) is drawn like a treasure; who drops it
  const dropFrom = t => t.enemy ? (t.enemy.name ? `: ${esc(t.enemy.name)}` : " z przeciwnika") : "";
  function spotNote(t) {
    const ng = nearestGrace(t);
    return `${dropFrom(t) ? `Jednorazowy łup${dropFrom(t)}. ` : ""}${isSet(t.flag) ? "Zebrane" : "Do zebrania"}${t.region_pl ? " · " + esc(t.region_pl) : ""}${ng ? ` · najbliższa łaska „${esc(ng.name)}” (${ng.inside ? "w tym samym lochu, " : ""}${ng.dist} m)` : ""}${t.approx ? ". Znacznik na mapie stoi przy wejściu do lochu." : "."}`;
  }
  // skarb z mapy: jeden przedmiot od razu w karcie; kilka: lista, klik otwiera kartę
  async function openSpot(t) {
    await itemsIndex();
    const found = t.items.map(x => findItem(x.cat, x.id));
    if (found.length === 1 && found[0]) return openItem(found[0], { spot: t });
    drawer(`<div class="eyebrow">${esc(KINDS[t.kind]?.[0] || "")}</div>
      <div class="d-title" style="text-align:left;font-size:23px">${t.enemy ? "Łup" : "Skarb"}: ${pl(t.items.length, "przedmiot", "przedmioty", "przedmiotów")}</div>
      <p class="view-sub" style="margin:10px 0 0">${spotNote(t)}</p>
      ${t.enemy?.stats ? bossStatsHtml(t.enemy.stats) : ""}${live.on && t.enemy?.stats ? '<div class="d-section" id="hitsBox"></div>' : ""}
      <div class="rule"></div>
      <div class="d-section">${t.items.map((x, i) => !found[i] ? listRow(null, null, esc(x.name || "Nieznany przedmiot"), "")
        : hiddenItem(found[i]) ? listRow(`data-spot-item="${i}"`, null, "· · ·", esc(CATS.find(c => c.f(found[i]))?.name || ""))
        : listRow(`data-spot-item="${i}"`, ICON(found[i].icon), esc(found[i].name), esc(KINDS[found[i].kind]?.[0] || ""))).join("")}</div>`,
      () => { if (t.enemy?.stats) fillHits(t.enemy.stats); document.querySelectorAll("[data-spot-item]").forEach(b => b.onclick = () => openItem(found[+b.dataset.spotItem], { spot: t })); });
  }
  // ---------- przedmioty: grupowanie / sortowanie / filtry ----------
  const WEP_TYPE = { 1: "Sztylety", 3: "Miecze proste", 5: "Wielkie miecze", 7: "Kolosalne miecze", 9: "Miecze zakrzywione", 11: "Wielkie miecze zakrzywione",
    13: "Katany", 14: "Ostrza bliźniacze", 15: "Miecze kłujące", 16: "Ciężkie miecze kłujące", 17: "Topory", 19: "Wielkie topory", 21: "Młoty",
    23: "Wielkie młoty", 24: "Cepy", 25: "Włócznie", 28: "Wielkie włócznie", 29: "Halabardy", 31: "Kosy", 33: "Bez broni", 35: "Broń pięściowa",
    37: "Pazury", 39: "Bicze", 41: "Kolosalna broń", 50: "Łuki lekkie", 51: "Łuki", 53: "Wielkie łuki", 55: "Kusze", 56: "Balisty",
    57: "Kostury", 61: "Święte pieczęcie", 65: "Małe tarcze", 67: "Średnie tarcze", 69: "Wielkie tarcze", 81: "Strzały", 83: "Wielkie strzały",
    85: "Bełty", 86: "Bełty balisty", 87: "Pochodnie", 88: "Walka wręcz", 89: "Flakony perfum", 90: "Tarcze kłujące", 91: "Ostrza do rzucania",
    92: "Ostrza odwrotne", 93: "Lekkie wielkie miecze", 94: "Wielkie katany", 95: "Pazury bestii" };
  const ARMOR_SLOT = ["Hełmy", "Zbroje", "Rękawice", "Nagolenniki"];
  const RARITY_GROUP = { 3: "Legendarne", 2: "Rzadkie", 1: "Zwykłe", 0: "Pozostałe" };
  // główny atrybut skalowania (np. „Siła”, „Siła + Zręczność” gdy różnica < 15%)
  function mainScaling(it) {
    const sc = Object.entries(it.stats?.scaling || {}).filter(([, v]) => v > 0).sort((a, b) => b[1] - a[1]);
    if (!sc.length) return "Bez skalowania";
    const ORD = ["str", "dex", "int", "fai", "arc"];
    return sc.filter(([, v]) => v >= sc[0][1] * 0.85).slice(0, 2).map(([k]) => k).sort((a, b) => ORD.indexOf(a) - ORD.indexOf(b)).map(k => ATTR[k]).join(" + ");
  }
  const GROUPS = {
    rarity: { name: "Rzadkość", key: it => it.rarity ?? 0, label: k => RARITY_GROUP[k] || "Pozostałe", order: (a, b) => b - a },
    type: { name: "Typ", cats: ["weapons", "armor", "spells"],
      key: it => it.category === "weapon" ? it.stats?.class ?? 0 : it.category === "armor" ? it.stats?.slot ?? 0 : it.kind === "sorcery" ? 0 : 1,
      label: (k, cat) => cat === "weapons" ? WEP_TYPE[k] || "Inne" : cat === "armor" ? ARMOR_SLOT[k] || "Inne" : k == 0 ? "Czary" : "Inkantacje",
      order: (a, b) => a - b },
    scaling: { name: "Skalowanie", cats: ["weapons"], key: mainScaling, label: k => k,
      order: (a, b) => (a === "Bez skalowania") - (b === "Bez skalowania") || a.localeCompare(b, "pl") },
    element: { name: "Żywioł / status", cats: ["weapons"], key: it => affinities(it).list[0]?.k || "phys",
      label: k => k === "phys" ? "Tylko fizyczne" : AFF[k][0],
      order: (a, b) => (a === "phys") - (b === "phys") || (a === "phys" ? 0 : AFF[a][0].localeCompare(AFF[b]?.[0] || "", "pl")) },
    owned: { name: "Posiadanie", key: it => have(it) ? 0 : 1, label: k => k == 0 ? "Posiadane" : "Brakujące", order: (a, b) => a - b },
    none: { name: "Bez grup", key: () => 0, label: () => "", order: () => 0 },
  };
  const sumv = o => Object.values(o || {}).reduce((a, v) => a + (+v || 0), 0);
  const SORTS = {
    rarity: { name: "Rzadkość", f: (a, b) => (b.rarity ?? 0) - (a.rarity ?? 0) || a.name.localeCompare(b.name, "pl") },
    name: { name: "Nazwa", f: (a, b) => a.name.localeCompare(b.name, "pl") },
    game: { name: "Kolejność gry", f: (a, b) => a.id - b.id },
    attack: { name: "Atak", cats: ["weapons"], f: (a, b) => sumv(b.stats?.attack) - sumv(a.stats?.attack) },
    weight: { name: "Waga", cats: ["weapons", "armor"], f: (a, b) => (a.stats?.weight ?? 0) - (b.stats?.weight ?? 0) },
    req: { name: "Wymagania", cats: ["weapons", "spells"], f: (a, b) => sumv(a.stats?.requires) - sumv(b.stats?.requires) },
    absorb: { name: "Ochrona", cats: ["armor"], f: (a, b) => sumv(b.stats?.absorb) - sumv(a.stats?.absorb) },
    fp: { name: "Koszt PS", cats: ["spells"], f: (a, b) => (a.stats?.fp ?? 0) - (b.stats?.fp ?? 0) },
  };
  const avail = (o, cat) => Object.entries(o).filter(([, v]) => !v.cats || v.cats.includes(cat.id));
  const itf = () => (state.itf ??= { group: {}, sort: {}, q: "", own: "all", aff: "" });
  function itemToolbar(cat) {
    const f = itf(), g = f.group[cat.id] || "rarity", so = f.sort[cat.id] || "rarity";
    const sel = (name, opts, cur) => `<select class="it-sel" data-it="${name}">${opts.map(([k, v]) => `<option value="${k}" ${k === cur ? "selected" : ""}>${v.name}</option>`).join("")}</select>`;
    const chip = (name, val, label, cur) => `<button class="chip ${cur === val ? "on" : ""}" data-itc="${name}" data-v="${val}">${label}</button>`;
    const affs = cat.id === "weapons" ? Object.keys(AFF).filter(k => cat.list.some(it => affinities(it).list.some(a => a.k === k))) : [];
    return `<div class="it-bar">
      <input class="search it-q" type="search" placeholder="Szukaj przedmiotu…" value="${esc(f.q)}">
      <label class="it-lbl"><span>Grupuj</span>${sel("group", avail(GROUPS, cat), g)}</label>
      <label class="it-lbl"><span>Sortuj</span>${sel("sort", avail(SORTS, cat), so)}</label>
      ${state.mine ? "" : `<span class="it-chips">${chip("own", "all", "Wszystkie", f.own)}${chip("own", "have", "Posiadane", f.own)}${chip("own", "missing", "Brakujące", f.own)}</span>`}
      ${affs.length ? `<span class="it-chips it-aff">${chip("aff", "", "Każdy żywioł", f.aff)}${affs.map(k => `<button class="chip aff-chip ${f.aff === k ? "on" : ""}" data-itc="aff" data-v="${k}" style="--c:${AFF[k][1]}">${AFF[k][0]}</button>`).join("")}</span>` : ""}
    </div>`;
  }
  function itemGroups(cat) {
    const f = itf(), gdef = GROUPS[f.group[cat.id] || "rarity"] || GROUPS.rarity, sdef = SORTS[f.sort[cat.id] || "rarity"] || SORTS.rarity;
    const q = f.q.trim().toLowerCase();
    const list = cat.list.filter(it => (!q || it.name.toLowerCase().includes(q) || (it.name_en || "").toLowerCase().includes(q))
      && (state.mine || f.own === "all" || (f.own === "have") === !!have(it))
      && (!f.aff || cat.id !== "weapons" || affinities(it).list.some(a => a.k === f.aff))).sort(sdef.f);
    if (!list.length) return `<p class="view-sub">Nic nie pasuje do filtrów.</p>`;
    const groups = new Map();
    for (const it of list) { const k = gdef.key(it); if (!groups.has(k)) groups.set(k, []); groups.get(k).push(it); }
    return [...groups.entries()].sort((a, b) => gdef.order(a[0], b[0])).map(([k, l]) => {
      const label = gdef.label(k, cat.id), owned = l.filter(have).length;
      return `<section class="igroup ${gdef === GROUPS.rarity ? "rg-" + k : ""}">${label ? `<div class="igroup-head"><span>${esc(label)}</span><small>${frac(owned, l.length)}</small></div>` : ""}
        <div class="igrid">${l.map(it => cellHTML(it)).join("")}</div></section>`; }).join("");
  }
  // tryb bez spoilerów: rzadkie i legendarne przedmioty, których nie masz, są ukryte, dopóki ich nie odsłonisz
  const itemKey = it => "i:" + it.category + ":" + it.id;
  // (makieta bez backendu: ukryty co trzeci, żeby było widać, jak to wygląda)
  const hiddenItem = it => spoilers() && have(it) === false && (it.rarity || 0) >= 2 && !(state.revealed ??= new Set()).has(itemKey(it))
    && (live.on || hashPct(it.id) % 3 === 0);
  function cellHTML(it) {
    const h = have(it), hid = hiddenItem(it);
    const f = hid ? { cls: "", style: "", gems: "" } : frame(it);
    return `<button class="icell ${f.cls} ${h ? "have" : ""} ${h === null ? "unknown" : ""} ${hid ? "hid" : ""}" style="${f.style}" data-item="${it.category}:${it.id}" title="${hid ? "Nieodkryty" : esc(it.name)}">
      <img src="${ICON(it.icon)}" alt="" loading="lazy">${f.gems}<span class="iname">${hid ? "· · ·" : esc(it.name)}</span>${it.dlc ? '<span class="dlc-dot" title="DLC"></span>' : ""}</button>`;
  }
  let bindItemCells = () => {};
  function bindItemToolbar(cat) {
    const f = itf(), redraw = () => { $(".igroups").innerHTML = itemGroups(cat); bindItemCells(); };
    main.querySelectorAll("[data-it]").forEach(s => s.onchange = () => { f[s.dataset.it][cat.id] = s.value; redraw(); });
    main.querySelectorAll("[data-itc]").forEach(b => b.onclick = () => { f[b.dataset.itc] = b.dataset.v;
      main.querySelectorAll(`[data-itc="${b.dataset.itc}"]`).forEach(x => x.classList.toggle("on", x === b)); redraw(); });
    const q = $(".it-q"); let t; q.oninput = () => { clearTimeout(t); t = setTimeout(() => { f.q = q.value; redraw(); }, 150); };
  }
  async function viewItems() {
    main.innerHTML = `<div class="view"><div class="view-sub">Wczytywanie przedmiotów z gry…</div></div>`;
    const items = await load("items") || [];
    if (location.hash !== "#items") return;
    const cats = CATS.map(c => { const l = items.filter(c.f).filter(gameOk).filter(it => !state.mine || have(it)); return { ...c, list: l, have: l.filter(have).length }; })
      .filter(c => !c.extra || c.list.length), coll = cats.filter(c => !c.extra);
    const cat = cats.find(c => c.id === state.cat) || cats[0];
    state.cat = cat.id;
    const done = coll.reduce((a, c) => a + c.have, 0), total = coll.reduce((a, c) => a + c.list.length, 0);
    main.innerHTML = `<div class="view">
      <div class="view-head"><div><div class="eyebrow">Skarbiec Zmatowiałego</div><h1 class="title">Przedmioty</h1>
        <div class="view-sub">${state.mine ? "Wszystko, co już masz. Kliknij, by zobaczyć szczegóły." : "Złote masz. Ciemne wciąż gdzieś czekają. Kliknij, by zobaczyć, gdzie leżą."}</div></div>
        ${ring(done, total, "posiadanych")}</div>
      <div class="cats">${cats.map(c => `<button class="cat ${c.id === state.cat ? "on" : ""}" data-cat="${c.id}">${c.name}<small>${frac(c.have, c.list.length)}</small></button>`).join("")}</div>
      ${itemToolbar(cat)}
      <div class="items-wrap"><div class="igroups">${itemGroups(cat)}</div>
      <aside class="cat-progress corners"><div class="eyebrow" style="margin-bottom:16px">Kolekcja</div>
        ${coll.map(c => `<div class="cp-row"><span>${c.name}</span><span>${frac(c.have, c.list.length)}</span>${state.mine ? "" : `<span class="qbar"><i style="width:${c.have / Math.max(1, c.list.length) * 100}%"></i></span>`}</div>`).join("")}
        <div class="rule"></div><p class="view-sub" style="margin:0">${live.on ? (live.inventory ? "Stan posiadania z ekwipunku w save'ie." : "Ekwipunek z save'a jeszcze niedostępny, znamy tylko popioły wojny.") : "Stan posiadania w makiecie jest losowy."}</p></aside></div></div>`;
    main.querySelectorAll("[data-cat]").forEach(b => b.onclick = () => { state.cat = b.dataset.cat; viewItems(); });
    bindItemToolbar(cat);
    (bindItemCells = () => main.querySelectorAll("[data-item]").forEach(b => b.onclick = () => {
      const [c, id] = b.dataset.item.split(":"), it = items.find(x => x.category === c && x.id === +id);
      if (it) openItem(it);
    }))();
  }

  /* ---------------- mapa (Leaflet + filtry) ---------------- */
  const tileUrl = m => `${ASSETS}/map/${m}/{z}/{x}/{y}.png`;
  function baseMap(el, m, opts = {}) {
    const map = L.map(el, { crs: L.CRS.Simple, minZoom: opts.minZoom ?? 1, maxZoom: MAXZ + 1, zoomSnap: .25, zoomControl: false, attributionControl: false, preferCanvas: true, ...opts });
    L.tileLayer(tileUrl(m), { tileSize: 256, maxNativeZoom: MAXZ, minNativeZoom: 0, noWrap: true,
      bounds: L.latLngBounds(map.unproject([0, L0], MAXZ), map.unproject([L0, 0], MAXZ)) }).addTo(map);
    return map;
  }
  const ll = (map, px, py) => map.unproject([px, py], MAXZ);
  const divIcon = (html, size, cls = "") => L.divIcon({ html, className: "mk " + cls, iconSize: [size, size], iconAnchor: [size / 2, size / 2] });
  // actions: [{ label, run, primary }] — po kliknięciu w mini-mapę pokazujemy okienko z wyborem
  function miniMap(el, m, px, py, icon, actions) {
    if (!el || !window.L) return;
    mini = baseMap(el, m, { dragging: false, scrollWheelZoom: false, doubleClickZoom: false, boxZoom: false, keyboard: false, touchZoom: false, minZoom: 3 });
    mini.setView(ll(mini, px, py), 4.5);
    L.marker(ll(mini, px, py), { icon: divIcon(`<span class="mk-boss big">${icon != null ? `<img src="${ICON(icon)}">` : ""}</span>`, 44) }).addTo(mini);
    if (!actions?.length) return;
    el.classList.add("mm-click");
    el.insertAdjacentHTML("beforeend", `<span class="mm-hint">⌖ kliknij, by otworzyć na mapie</span>`);
    const close = () => el.querySelector(".mm-pop")?.remove();
    mini.on("click", () => {
      if (el.querySelector(".mm-pop")) return close();
      el.insertAdjacentHTML("beforeend", `<div class="mm-pop" role="dialog"><p>Pokazać to miejsce na dużej mapie?</p>
        <div class="mm-btns">${actions.map((a, i) => `<button class="mm-btn ${a.primary ? "primary" : ""}" data-mm="${i}">${esc(a.label)}</button>`).join("")}<button class="mm-btn" data-mm="x">Anuluj</button></div></div>`);
      el.querySelectorAll("[data-mm]").forEach(b => b.onclick = ev => { ev.stopPropagation(); const k = b.dataset.mm; close(); if (k !== "x") actions[+k].run(); });
    });
  }
  let bigMap, mapLayers = {}, playerMarker = null, mapRenderer = null;
  // mapy gry: powierzchnia, podziemia (Siofra, Ainsel, Głębiny) i Królestwo Cieni — dostępne wg zakresu gry
  const MAPS = { M00: "Ziemie Pomiędzy", M01: "Podziemia", M10: "Królestwo Cieni (DLC)" };
  const mapsFor = g => (g === "dlc" ? ["M10"] : g === "base" ? ["M00", "M01"] : ["M00", "M01", "M10"])
    .filter(k => !mapMine() || !W.pieces?.[k] || travelArea(k));          // „Mój postęp”: tylko mapy, na których byłeś
  // obszar mapy jak w grze: prostokąty otwartych fragmentów (zebrane mapy + obszar startowy) i okolice miejsc,
  // w których byłeś (łaski, zebrane przedmioty, pokonani bossowie, śmierci, pozycja) — [lewo, prawo, góra, dół]
  function travelArea(m) {
    const ps = W.pieces?.[m]; if (!ps) return null;
    let a = null;
    const add = r => { a = a ? [Math.min(a[0], r[0]), Math.max(a[1], r[1]), Math.min(a[2], r[2]), Math.max(a[3], r[3])] : [...r]; };
    for (const p of ps) if (isSet(p.f, 70)) add(p.r);
    for (const p of revealPoints(m)) add([p.px - 500, p.px + 500, p.py - 500, p.py + 500]);
    if (!a) return null;
    const cx = (a[0] + a[1]) / 2, cy = (a[2] + a[3]) / 2, w = Math.max(a[1] - a[0], 1600) / 2, h = Math.max(a[3] - a[2], 1000) / 2;
    return [cx - w, cx + w, cy - h, cy + h];
  }
  // stany świata: grafika mapy się nie zmienia, zmieniają się napisy miejsc (z flag w save'ie, np. krater po Radahnie)
  // flagi pokazania miejsc, które zmieniają się w trakcie gry (Enir-Ilim w DLC); pozostałe miejsca są zawsze na mapie
  const WORLD_FLAGS = [62890];
  // napis miejsca: ostatni włączony i niewyłączony (WorldMapPointParam); null = miejsca jeszcze (albo już) nie ma na mapie
  const textOn = ([, on, off]) => (!on || isSet(on)) && !(off && isSet(off));
  const poiName = p => p.names ? p.names.filter(textOn).pop()?.[0] ?? null : p.name;
  // characters the game writes under a place once you have met them; without spoiler hiding also those who come later
  function poiPeople(p) {
    const now = [...new Set((p.people || []).filter(textOn).map(n => n[0]))];
    return { now, later: spoilers() ? [] : [...new Set((p.people || []).map(n => n[0]))].filter(n => !now.includes(n)) };
  }
  // the game's own character markers (WorldMapPointParam with names only, name null) belong to the characters layer
  const npcMarker = p => p.name === null;
  const poiShown = p => (npcMarker(p) ? Object.values(poiPeople(p)).some(l => l.length) : poiName(p) !== null) && (!WORLD_FLAGS.includes(p.flag) || isSet(p.flag));
  const poiLayer = p => npcMarker(p) ? "npc" : "poi:" + p.category;
  // a character from the map files standing where the game has its own marker for them: one marker is enough
  const hasGameMarker = n => W.pois.some(p => npcMarker(p) && p.map === n.map && p.people.some(x => x[0] === n.name) && (p.px - n.px) ** 2 + (p.py - n.py) ** 2 < 40 ** 2);
  // icon variants without a parameter row: icon -> [flag, icon shown once the flag is set]
  // - Leyndell 60 -> 62 (burning tree, "Capital of Ash" on wiki.gg) on flag 118, the same flag that switches the name
  //   to the ashen capital (Maliketh defeated);
  // - Belurat 210 -> 212 (tower without the black thorns): burning the Sealing Tree drives the shadow off Belurat in
  //   a cutscene and moves you to Enir-Ilim, whose map point shows on flag 62890
  const ICON_AFTER = { 60: [118, 62], 210: [62890, 212] };
  const poiIcon = p => ICON_AFTER[p.icon] && isSet(ICON_AFTER[p.icon][0]) ? ICON_AFTER[p.icon][1] : p.icon;
  // Twierdza Okrągłego Stołu (m11_10): gra pokazuje ją jedną ikoną w morzu na zachód od Pogrobna; jej punkty zbieramy w liście
  const atRoundtable = o => (o.map_id || "").startsWith("m11_10");
  // widok nie wychodzi poza mapę z gry („Mój postęp”: poza odkryty obszar), a najmniejsze przybliżenie wypełnia nią ekran
  function applyArea(map, keep) {
    const a = (mapMine() && travelArea(state.map)) || [0, L0, 0, L0];
    const b = L.latLngBounds(ll(map, a[0], a[3]), ll(map, a[1], a[2]));
    map.options.maxBoundsViscosity = 1;
    map.setMaxBounds(b);
    // przybliżenie, przy którym obszar wypełnia okno (liczone wprost — getBoundsZoom przycina do bieżącego minZoom,
    // więc po powiększeniu obszaru minimum by nie spadło)
    const s = map.getSize(), fill = Math.max(s.x / (a[1] - a[0]), s.y / (a[3] - a[2]));
    const z = Math.min(MAXZ + 1, Math.ceil((MAXZ + Math.log2(fill)) * 4) / 4);
    map.setMinZoom(z);
    const p = D.position;
    if (!keep) map.setView(p && p.map === state.map && b.contains(ll(map, p.px, p.py)) ? ll(map, p.px, p.py) : b.getCenter(), Math.max(z, Math.min(3.5, MAXZ)), { animate: false });
    else if (map.getZoom() < z) map.setZoom(z, { animate: false });
    map.panInsideBounds(b, { animate: false });
  }
  // warstwy wyłączone: osobno dla zwykłego trybu (bez drobnicy) i „Mojego postępu” (tam widać też runy, materiały…)
  const offLayers = () => state.mine ? state.offMine : state.off;
  function mapCounts() {
    const m = state.map, c = {}, mine = state.mine, near = mine ? revealTest(m) : null;
    // „Mój postęp”: tylko zaliczone; miejsca i postacie (bez stanu) tylko w odkrytych okolicach
    const add = (k, done, pos) => { if (mine && (done === false || (done == null && !near(pos)))) return;
      c[k] ??= [0, 0]; c[k][1]++; if (done) c[k][0]++; };
    for (const g of W.graces) if (g.map === m) add("grace", isSet(g.flag, 60));               // Twierdza: jeden znacznik w warstwie łask
    for (const b of bossList()) if (b.map === m && !hiddenBoss(b)) add("boss", b.defeated);
    for (const x of W.invaders) if (x.map === m && !atRoundtable(x)) add("invader", isSet(x.flag), x);
    for (const w of W.warps) if (w.src.map === m) add("teleport", null, w.src);
    for (const s of W.summons) if (s.map === m) add("summon", null, s);
    for (const p of W.pois) if (p.map === m && poiShown(p)) add(poiLayer(p), null, p);
    for (const t of W.items) if (t.map === m && !atRoundtable(t)) add(t.kind, isSet(t.flag));
    for (const n of W.npcs) if (n.map === m && !atRoundtable(n) && !hasGameMarker(n)) add("npc", null, n);
    for (const d of dlcMarks(m)) add("dlc", mine ? null : d.done, d);
    const nd = (D.deathPoints || []).filter(d => d.map === m).length; if (nd) c.deaths = [0, nd];
    return c;
  }
  function viewMap() {
    const avail = mapsFor(state.game);
    if (!avail.includes(state.map)) state.map = avail[0];
    const off = offLayers(), cnt = mapCounts(), on = k => !off.has(k);
    const row = (k, label, sw, tip) => cnt[k] ? `<button class="layer ${on(k) ? "on" : ""}" data-layer="${k}"${tip ? ` title="${esc(tip)}"` : ""}><span class="sw">${sw}</span>${esc(label)}
      <span class="cnt">${layerCount(cnt[k])}</span></button>` : "";
    const group = (title, keys, body) => { const rows = body.filter(Boolean).join(""); if (!rows) return "";
      const allOn = keys.every(on); return `<div class="lgroup"><button class="lgroup-head" data-group="${keys.join(",")}">${esc(title)}<span>${allOn ? "ukryj" : "pokaż"} wszystkie</span></button>${rows}</div>`; };
    const dot = col => `<span class="sw-dot" style="background:${col}"></span>`;
    const poiKeys = Object.keys(POI).map(k => "poi:" + k), kindKeys = KIND_GROUPS.flatMap(g => g[1]);
    main.innerHTML = `<div class="mapview"><div class="mapcanvas" id="mapc"></div>
      <div class="map-panel corners"><div class="eyebrow">${MAPS[state.map]}</div><h2 class="title">Mapa</h2>
        ${avail.length > 1 ? `<div class="maptabs">${avail.map(k => `<button class="chip ${state.map === k ? "on" : ""}" data-m="${k}">${MAPS[k]}</button>`).join("")}</div>` : ""}
        <input class="search map-search" id="mq" type="search" placeholder="Szukaj: przedmiot, boss, miejsce…" value="${esc(state.mapQuery)}">
        ${state.mapFocus && !state.mapDrops ? `<button class="chip on map-filter-chip" id="focusClear">Pokazuję: ${esc(state.mapFocus.title)} · pokaż resztę ✕</button>` : ""}
        ${state.mapDrops ? `<button class="chip on map-filter-chip" id="dropsClear">Gdzie wypada: ${esc(state.mapDrops.title)} (${state.mapDrops.pts.filter(p => p[0] === state.map).length}) ✕</button>` : ""}
        ${state.mapPeek ? `<p class="view-sub mine-note">Pokazuję miejsce poza odkrytym terenem. <button class="chip" id="peekBack">Wróć do mojego postępu</button></p>` : ""}
        ${state.mine ? `<p class="view-sub mine-note">Mapa jak w grze: widać tylko części odsłonięte zebranymi fragmentami mapy. Do tego odkryte łaski, pokonani bossowie i zebrane przedmioty.</p>`
          : `<label class="toggle hide-done" title="Ukrywa zebrane przedmioty, pokonanych bossów i odkryte miejsca łaski"><input type="checkbox" id="hideDone" ${state.hideDone ? "checked" : ""}>
            <span class="toggle-track"><span class="toggle-thumb"></span></span><span class="toggle-label">Ukryj zaliczone</span></label>`}
        <button class="chip all-layers" id="allLayers">${Object.keys(cnt).some(on) ? "Ukryj wszystko" : "Pokaż wszystko"}</button>
        <div class="layers-scroll">
        ${group("Na mapie", ["grace", "boss", "invader", "npc", "teleport", "summon", "deaths", "dlc"], [row("dlc", "Wejście do DLC", '<span class="sw-dlc">✦</span>'), row("grace", "Miejsca łaski", '<span class="sw-grace"></span>'), row("boss", "Bossowie", '<span class="sw-boss"></span>'), row("invader", "Najeźdźcy", '<span class="sw-invader"></span>', "Czerwone fantomy NPC: najeźdźcy i pojedynki ze znaku przywołania"),
          row("npc", "Postacie (NPC)", '<span class="sw-quest"></span>'), row("teleport", "Teleporty", '<span class="sw-poi">⟲</span>', "Bramy, skrzynie-pułapki i inne przejścia, które przenoszą w inne miejsce"),
          row("summon", "Znaki przywołania", '<span class="sw-poi">✧</span>', "Znaki, którymi przyzywasz postać do pomocy (np. Nepheli przy Godricku) albo do pojedynku"), row("deaths", "Miejsca śmierci", '<span class="sw-death"></span>', "Save pamięta tylko liczbę śmierci i ostatnią plamę krwi. Miejsca wcześniejszych śmierci aplikacja zbiera sama, od kiedy działa")])}
        ${group("Miejsca i lochy", poiKeys, Object.entries(POI).map(([k, [l, g]]) => row("poi:" + k, l, `<span class="sw-poi">${g}</span>`)))}
        ${KIND_GROUPS.map(([title, keys]) => group(title, keys, keys.map(k => row(k, KINDS[k][0], dot(KINDS[k][1]))))).join("")}
        </div>
        <p class="view-sub" style="margin:10px 0 0;font-size:15.5px">${live.on ? "Stan z twojego save'a." : "Stan przykładowy (backend wyłączony)."} Przedmioty z lochów stoją przy wejściu.</p>
      </div>
      <div class="map-legend">◆ twoja pozycja z ostatniego zapisu · kółko myszy: przybliżenie · klik: szczegóły</div>
      <div class="map-zoom"><button id="zin" aria-label="Przybliż">+</button><button id="zout" aria-label="Oddal">−</button></div></div>`;
    main.querySelectorAll("[data-m]").forEach(b => b.onclick = () => { state.map = b.dataset.m; state.mapPeek = false; state.mapFocus = null; viewMap(); });
    // warstwy i grupy: tylko przełączenie znaczników i przycisków (bez przebudowy mapy i panelu)
    const syncGroups = () => main.querySelectorAll("[data-group]").forEach(h => {
      const ks = h.dataset.group.split(","); h.querySelector("span").textContent = `${ks.every(on) ? "ukryj" : "pokaż"} wszystkie`; });
    const setLayers = (keys, visible) => { keys.forEach(k => visible ? off.delete(k) : off.add(k));
      main.querySelectorAll("[data-layer]").forEach(l => l.classList.toggle("on", on(l.dataset.layer)));
      $("#allLayers").textContent = Object.keys(cnt).some(on) ? "Ukryj wszystko" : "Pokaż wszystko";
      syncGroups(); refreshLayers(); };
    main.querySelectorAll("[data-layer]").forEach(b => b.onclick = () => { const k = b.dataset.layer; setLayers([k], off.has(k)); });
    main.querySelectorAll("[data-group]").forEach(b => b.onclick = () => { const keys = b.dataset.group.split(","); setLayers(keys, !keys.every(on)); });
    $("#allLayers").onclick = () => setLayers(Object.keys(cnt), !Object.keys(cnt).some(on));
    if ($("#hideDone")) $("#hideDone").onchange = e => { state.hideDone = e.target.checked; buildLayers(); };
    if ($("#focusClear")) $("#focusClear").onclick = () => { state.mapFocus = null; $("#focusClear").remove(); buildLayers(); };
    if ($("#dropsClear")) $("#dropsClear").onclick = () => { state.mapDrops = null; state.mapFocus = null;
      if (state.mapPeek) { state.mapPeek = false; viewMap(); } else { $("#dropsClear").remove(); buildLayers(); } };
    if ($("#peekBack")) $("#peekBack").onclick = () => { state.mapPeek = false; state.mapDrops = null; state.mapFocus = null; viewMap(); };
    // wyszukiwanie: tylko znaczniki i żeton filtra (pole zostaje, mapa się nie przebudowuje)
    const syncChip = () => {
      $("#mqClear")?.remove();
      if (state.mapQuery) {
        $("#mq").insertAdjacentHTML("afterend", `<button class="chip on map-filter-chip" id="mqClear">Filtr: ${esc(state.mapQuery)}${state.mapExact ? " (dokładnie)" : ""} ✕</button>`);
        $("#mqClear").onclick = () => { state.mapQuery = ""; state.mapExact = null; $("#mq").value = ""; syncChip(); buildLayers(); };
      }
    };
    let t; $("#mq").oninput = e => { clearTimeout(t); t = setTimeout(() => { state.mapQuery = e.target.value; state.mapExact = null; state.mapFocus = null; $("#focusClear")?.remove(); syncChip(); buildLayers(); }, 350); };
    syncChip();
    if (!window.L) { $("#mapc").innerHTML = '<p class="view-sub" style="padding:40px">Brak biblioteki Leaflet (offline?).</p>'; return; }
    const keepView = viewMap.keep && bigMap && viewMap.keep.map === state.map ? { c: bigMap.getCenter(), z: bigMap.getZoom() } : null;
    if (bigMap) bigMap.remove();
    const map = bigMap = baseMap($("#mapc"), state.map);
    // the container narrows when the drawer becomes a column on wide screens; Leaflet itself only tracks the window
    new ResizeObserver(() => bigMap === map && map.invalidateSize()).observe($("#mapc"));
    mapRenderer = L.canvas({ padding: .4 });
    map.createPane("drops").style.zIndex = 640;                     // „Gdzie wypada”: nad ikonami innych znaczników
    const p = D.position;
    if (keepView) map.setView(keepView.c, keepView.z, { animate: false });
    applyArea(map, !!keepView);
    viewMap.keep = null;
    $("#zin").onclick = () => map.zoomIn(.75); $("#zout").onclick = () => map.zoomOut(.75);
    if (p && p.map === state.map) playerMarker = L.marker(ll(map, p.px, p.py), { icon: divIcon('<span class="mk-player"></span>', 28), zIndexOffset: 1000 })
      .bindTooltip(`<b>Tu jesteś</b>${esc(p.name)} · ostatni zapis${p.approx ? " · w lochu (znacznik przy wejściu)" : ""}`, { direction: "top", offset: [0, -12], className: "er-tip" }).addTo(map);
    buildLayers();
  }
  function viewMapKeep() { viewMap.keep = { map: state.map }; viewMap(); }
  function buildLayers() {
    const map = bigMap; if (!map) return;
    for (const g of Object.values(mapLayers)) g.remove();
    mapLayers = {};
    const m = state.map, q = state.mapQuery.trim().toLowerCase(), mine = state.mine, hide = state.hideDone && !mine, renderer = mapRenderer;
    const near = mine ? revealTest(m) : () => true;
    drawFog(map, m);
    const grp = k => mapLayers[k] ??= L.layerGroup();
    const match = (...names) => !q || names.some(n => state.mapExact ? (n || "").toLowerCase() === q : (n || "").toLowerCase().includes(q));
    // focus (opened from another page): only the target, whatever the layer, search and progress filters say
    const foc = state.mapFocus;
    const pinned = o => foc.at.some(a => a.map === o.map && Math.abs(a.px - o.px) < 2 && Math.abs(a.py - o.py) < 2);
    const show = (o, ok) => foc ? pinned(o) : ok;
    const rt = roundtable(), rtg = rt.grace, rtFound = isSet(rtg.flag, 60);
    if (rtg.map === m && show(rtg, (!mine || rtFound) && !(hide && rtFound) && match("okrągły stół", "twierdza", rtg.name,
      ...rt.npcs.flatMap(n => [n.name, n.name_en]), ...rt.invaders.flatMap(x => [x.name, x.name_en]), ...rt.spots.flatMap(t => t.items.flatMap(i => [i.name, i.name_en])))))
      L.marker(ll(map, rtg.px, rtg.py), { icon: divIcon(`<span class="mk-place"><img src="${MAP_ICON(48)}" alt=""></span>`, 44), zIndexOffset: 700, riseOnHover: true })
        .bindTooltip(`<b>Twierdza Okrągłego Stołu</b><span class="tip-sub">klik: postacie, skarby i łaska</span>`, { direction: "top", offset: [0, -18], className: "er-tip" })
        .on("click", openRoundtable).addTo(grp("grace"));
    for (const g of W.graces) { if (g.map !== m || atRoundtable(g)) continue; const v = isSet(g.flag, 60); if (!show(g, match(g.name, g.region) && !(hide && v) && !(mine && !v))) continue;
      L.marker(ll(map, g.px, g.py), { icon: divIcon(`<span class="mk-grace ${v ? "on" : ""}"></span>`, 22) })
        .bindTooltip(`<b>${esc(g.name || "Miejsce łaski")}</b>${esc(g.region || "")} · ${v ? "odkryte" : "nieodkryte"}`, { direction: "top", offset: [0, -8], className: "er-tip" }).addTo(grp("grace")); }
    for (const b of bossList()) { if (b.map !== m || hiddenBoss(b) || !show(b, match(b.name, b.name_en) && !(hide && b.defeated) && !(mine && !b.defeated))) continue;
      L.marker(ll(map, b.px, b.py), { icon: divIcon(`<span class="mk-boss ${b.defeated ? "done" : ""}">${b.icon != null ? `<img src="${ICON(b.icon)}">` : ""}</span>`, 34), riseOnHover: true })
        .bindTooltip(`<b>${esc(b.name)}</b>${b.defeated ? "pokonany" : "niepokonany"} · ${pl(b.runes || 0, "run", "runy", "runów")}${b.approx ? " · w lochu" : ""}`, { direction: "top", offset: [0, -16], className: "er-tip" })
        .on("click", () => openBoss(b.id)).addTo(grp("boss")); }
    for (const x of W.invaders) { const done = isSet(x.flag), hid = hiddenInvader(x);
      if (x.map !== m || atRoundtable(x) || !show(x, match(hid ? "" : x.name, hid ? "" : x.name_en, "najeźdźca") && !(hide && done) && !(mine && !done))) continue;
      L.marker(ll(map, x.px, x.py), { icon: divIcon(`<span class="mk-invader ${done ? "done" : ""}"></span>`, 24), riseOnHover: true })
        .bindTooltip(`<b>${hid ? (x.summoned ? "Przeciwnik" : "Najeźdźca") : esc(x.name)}</b>${x.summoned ? "pojedynek ze znaku · " : ""}${done ? "pokonany" : "niepokonany"}${hid || !x.rewards.length ? "" : " · " + esc(x.rewards[0].name) + (x.rewards.length > 1 ? " i inne" : "")}`, { direction: "top", offset: [0, -10], className: "er-tip" })
        .on("click", () => openInvader(x)).addTo(grp("invader")); }
    for (const w of W.warps) { const to = nearestGrace(w.dst);
      if (w.src.map !== m || !show(w.src, match(WARP[w.kind], to?.name) && near(w.src))) continue;
      L.marker(ll(map, w.src.px, w.src.py), { icon: divIcon('<span class="mk-poi mk-warp">⟲</span>', 22), riseOnHover: true })
        .bindTooltip(`<b>${WARP[w.kind]}</b>${to ? "do: " + esc(to.name) : "przenosi w inne miejsce"}<span class="tip-sub">klik: dokąd prowadzi</span>`, { direction: "top", offset: [0, -10], className: "er-tip" })
        .on("click", () => openWarp(w)).addTo(grp("teleport")); }
    for (const s of W.summons) { if (s.map !== m || !show(s, match(s.name, "znak przywołania") && near(s))) continue;
      const boss = bossList().filter(b => b.map === m && !hiddenBoss(b)).map(b => [b, Math.hypot(b.px - s.px, b.py - s.py)]).filter(([, d]) => d < 150).sort((x, y) => x[1] - y[1])[0]?.[0];
      L.marker(ll(map, s.px, s.py), { icon: divIcon('<span class="mk-poi mk-sign">✧</span>', 22), riseOnHover: true })
        .bindTooltip(`<b>${esc(s.name)}</b>${s.helper ? "znak pomocnika" : "znak przywołania"}${boss ? " · przy bossie: " + esc(boss.name) : ""}<span class="tip-sub">klik: karta postaci</span>`,
          { direction: "top", offset: [0, -10], className: "er-tip" })
        .on("click", () => openNpc(s.name)).addTo(grp("summon")); }
    // „Gdzie wypada”: wszystkie miejsca przeciwników z wybranym łupem (z karty przedmiotu)
    for (const [pm, px, py] of state.mapDrops?.pts || []) if (pm === m)
      L.circleMarker(ll(map, px, py), { pane: "drops", radius: 8, color: "#fff4e0", weight: 2, fillColor: "#e0483a", fillOpacity: 1 })
        .bindTooltip(`<b>${esc(state.mapDrops.title)}</b>tu się pojawia`, { direction: "top", className: "er-tip" }).addTo(grp("drops"));
    for (const pnt of W.pois) { const who = poiPeople(pnt), npc = npcMarker(pnt), icon = poiIcon(pnt);
      const name = npc ? who.now.join(" · ") || "Postać" : poiName(pnt), here = npc ? [] : who.now;
      const person = npc && (who.now[0] || who.later[0]);
      if (pnt.map !== m || !poiShown(pnt) || !show(pnt, match(name, ...who.now, ...who.later) && near(pnt))) continue;
      // Divine Tower: Great Rune restored or not (extract_landmarks.py); mausoleum: remembrance duplication
      const about = (pnt.restore || []).map(r => `<span class="tip-sub">${esc(r.rune)}: ${isSet(r.flag) ? "przywrócony" : "przywrócisz go tu, przy posągu na szczycie"}</span>`).join("")
        + (pnt.walking != null ? `<span class="tip-sub">powielisz tu wizerunek bossa${pnt.walking ? " · chodzi po okolicy, to miejsce startu" : ""}</span>` : "");
      L.marker(ll(map, pnt.px, pnt.py), { icon: icon != null ? divIcon(`<span class="mk-place"><img src="${MAP_ICON(icon)}" alt=""></span>`, 36)
        : divIcon(`<span class="mk-poi">${POI[pnt.category]?.[1] || "◇"}</span>`, 22) })
        .on("click", () => { if (person) openNpc(person); })
        .bindTooltip(`<b>${esc(name)}</b>${npc ? "postać · klik: karta postaci" : esc(POI[pnt.category]?.[0] || "")}${about}${here.length ? `<span class="tip-sub">tu jest: ${esc(here.join(" · "))}</span>` : ""}${
          who.later.length ? `<span class="tip-sub">w innym momencie gry: ${esc(who.later.join(" · "))}</span>` : ""}`, { direction: "top", offset: [0, -12], className: "er-tip" }).addTo(grp(poiLayer(pnt))); }
    for (const d of dlcMarks(m)) { if (!show({ ...d, map: m }, match("wejście do dlc", "dlc", d.name) && !(mine && !near(d)))) continue;
      L.marker(ll(map, d.px, d.py), { icon: divIcon(`<span class="mk-dlc ${d.done ? "done" : ""}">✦</span>`, 30), zIndexOffset: 800, riseOnHover: true })
        .bindTooltip(`<b>${d.title}</b>${esc(d.sub)}<span class="tip-sub">klik: jak się tam dostać</span>`, { direction: "top", offset: [0, -14], className: "er-tip" })
        .on("click", () => goQuest("dlc-entry")).addTo(grp("dlc")); }
    for (const n of W.npcs) { if (n.map !== m || atRoundtable(n) || hasGameMarker(n) || !show(n, match(n.name, n.name_en) && near(n))) continue;
      (n.render ? L.marker(ll(map, n.px, n.py), { icon: divIcon(`<span class="mk-npc"><img src="${ICON("r:" + n.render)}" alt=""></span>`, 28), riseOnHover: true })
        : L.circleMarker(ll(map, n.px, n.py), { renderer, radius: 5, color: "#cfe3ea", weight: 1.2, fillColor: "#2f4a5a", fillOpacity: .95 }))
        .bindTooltip(`<b>${esc(n.name)}</b>postać · klik: karta postaci`, { direction: "top", className: "er-tip" })
        .on("click", () => openNpc(n.name)).addTo(grp("npc")); }
    for (const t of W.items) { if (t.map !== m || atRoundtable(t)) continue;
      const done = isSet(t.flag); if (!show(t, match(...t.items.map(i => i.name), ...t.items.map(i => i.name_en)) && !(hide && done) && !(mine && !done))) continue;
      const col = KINDS[t.kind]?.[1] || "#999", dim = done && !mine;      // „Mój postęp” pokazuje tylko zebrane: bez przygaszania
      L.circleMarker(ll(map, t.px, t.py), { renderer, radius: q ? 7 : 4.5, color: dim ? "#8a7a5a" : "#1a140c", weight: 1, fillColor: col, fillOpacity: dim ? .5 : .95 })
        .on("click", () => selectSpot(t))
        .bindTooltip(`${t.items.map(i => `<span class="tip-item">${i.icon != null ? `<img src="${ICON(i.icon)}">` : ""}<b>${esc(i.name || "?")}</b>${i.count > 1 ? ` ×${i.count}` : ""}</span>`).join("")}
          <span class="tip-sub">${KINDS[t.kind]?.[0] || ""}${t.region_pl ? " · " + esc(t.region_pl) : ""}${t.enemy ? " · łup" + dropFrom(t) : ""}${done ? " · zebrane" : ""}${t.approx ? " · w lochu" : ""}</span>`, { direction: "top", className: "er-tip" })
        .addTo(grp(t.kind)); }
    if (live.on && !foc) for (const d of (D.deathPoints || []).filter(d => d.map === m))
      L.circleMarker(ll(map, d.px, d.py), { renderer, radius: d.last ? 8 : 5, color: "#f0c9a0", weight: d.last ? 1.5 : 0, fillColor: "#9b3428", fillOpacity: .7 })
        .bindTooltip(d.last ? `<b>Plama krwi</b>${d.runes > 0 ? pl(d.runes, "run", "runy", "runów") + " do odzyskania" : "ostatnia śmierć"}` : "<b>Śmierć</b>", { direction: "top", className: "er-tip" }).addTo(grp("deaths"));
    refreshLayers();
  }
  // „Mój postęp”: odkryte okolice = odwiedzone łaski, zebrane skarby, pokonani bossowie, miejsca śmierci i pozycja gracza
  const FOG_R = 560, FOG_PX = 1024;                     // promień odkrytej okolicy (piksele mapy) · rozdzielczość mgły
  function revealPoints(m) {
    const pts = [];
    for (const g of W.graces) if (g.map === m && isSet(g.flag, 60)) pts.push(g);
    for (const t of W.items) if (t.map === m && isSet(t.flag)) pts.push(t);
    for (const b of bossList()) if (b.map === m && b.defeated) pts.push(b);
    for (const d of D.deathPoints || []) if (d.map === m) pts.push(d);
    if (D.position?.map === m) pts.push(D.position);
    return pts.filter(p => p.px != null);
  }
  function revealTest(m) {
    const pts = revealPoints(m), r2 = (FOG_R * .8) ** 2;
    return o => !o || pts.some(p => (p.px - o.px) ** 2 + (p.py - o.py) ** 2 < r2);
  }
  let fogLayer = null, fogToken = 0;
  // maska fragmentów (assets/map/<M>/pieces.png, build_map_pieces.mjs): kanały R,G,B = bity fragmentów w danym miejscu
  const pieceData = {};
  const pieceMask = m => pieceData[m] ??= new Promise(res => {
    const im = new Image();
    im.onload = () => { const c = document.createElement("canvas"); c.width = im.width; c.height = im.height;
      const x = c.getContext("2d", { willReadFrequently: true }); x.drawImage(im, 0, 0); res(x.getImageData(0, 0, c.width, c.height)); };
    im.onerror = () => res(null);
    im.src = `${ASSETS}/map/${m}/pieces.png`;
  });
  const NOTHING = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7";
  function drawFog(map, m) {
    if (fogLayer) { fogLayer.remove(); fogLayer = null; }
    const token = ++fogToken;
    if (!state.mine) return;
    if (W.pieces?.[m]) return pieceMask(m).then(data => {
      if (token !== fogToken || bigMap !== map) return;
      if (!data) return circleFog(map, m);
      // jak w grze: widać tylko to, co odsłaniają zebrane fragmenty mapy; resztę kryje pusta faktura z gry
      let have = 0;
      W.pieces[m].forEach((p, i) => { if (i < 24 && isSet(p.f, 70)) have |= 1 << i; });
      const c = document.createElement("canvas"); c.width = data.width; c.height = data.height;
      const x = c.getContext("2d"), out = x.createImageData(c.width, c.height), d = data.data;
      for (let i = 0; i < d.length; i += 4) { const bits = d[i] | d[i + 1] << 8 | d[i + 2] << 16; if (bits && !(bits & have)) out.data[i + 3] = 255; }
      x.putImageData(out, 0, 0);
      const url = c.toDataURL();
      fogLayer = L.imageOverlay(NOTHING, L.latLngBounds(ll(map, 0, L0), ll(map, L0, 0)), { className: "fog pieces-fog", interactive: false }).addTo(map);
      const el = fogLayer.getElement();
      el.style.backgroundImage = `url(${ASSETS}/map/blank.png)`;
      el.style.webkitMaskImage = el.style.maskImage = `url(${url})`;
      el.style.webkitMaskSize = el.style.maskSize = "100% 100%";
      const size = () => { el.style.backgroundSize = `${256 * 2 ** (map.getZoom() - MAXZ)}px`; };
      size(); map.on("zoomend", size); fogLayer.on("remove", () => map.off("zoomend", size));
    });
    circleFog(map, m);
  }
  // bez masek fragmentów (stare dane): mgła wokół odwiedzonych miejsc
  function circleFog(map, m) {
    const pad = 1500, span = L0 + 2 * pad, k = FOG_PX / span, c = document.createElement("canvas");
    c.width = c.height = FOG_PX;
    const x = c.getContext("2d");
    x.fillStyle = "#070605"; x.fillRect(0, 0, FOG_PX, FOG_PX);                // nieodkryte: całkowicie zakryte
    x.globalCompositeOperation = "destination-out";
    const r = FOG_R * k;
    for (const p of revealPoints(m)) {
      const cx = (p.px + pad) * k, cy = (p.py + pad) * k, gr = x.createRadialGradient(cx, cy, r * .35, cx, cy, r);
      gr.addColorStop(0, "rgba(0,0,0,1)"); gr.addColorStop(1, "rgba(0,0,0,0)");
      x.fillStyle = gr; x.beginPath(); x.arc(cx, cy, r, 0, Math.PI * 2); x.fill();
    }
    fogLayer = L.imageOverlay(c.toDataURL(), L.latLngBounds(ll(map, -pad, L0 + pad), ll(map, L0 + pad, -pad)), { className: "fog", interactive: false }).addTo(map);
  }
  // zaznaczenie wybranego skarbu: pulsujący złoty pierścień + panel szczegółów
  let selMarker = null;
  function selectSpot(t) {
    if (selMarker) selMarker.remove();
    selMarker = L.marker(ll(bigMap, t.px, t.py), { icon: divIcon('<span class="mk-select"></span>', 40), interactive: false, zIndexOffset: 900 }).addTo(bigMap);
    openSpot(t);
  }
  $("#drawerClose").addEventListener("click", () => { if (selMarker) { selMarker.remove(); selMarker = null; } });
  function refreshLayers() { const off = offLayers(); for (const [k, g] of Object.entries(mapLayers)) off.has(k) && !state.mapQuery && !state.mapFocus ? g.remove() : g.addTo(bigMap); }

  // ---------- powiązania między widokami: przedmiot ↔ mapa ↔ boss ↔ quest ----------
  let pendingAfter = null;
  function navTo(hash, after) { if (location.hash === hash) { closeDrawer(); if (after) after(); return; } pendingAfter = after; location.hash = hash; }
  function focusMap(o, spot) {
    if (!bigMap || !o?.map) return;
    bigMap.setView(ll(bigMap, o.px, o.py), 5, { animate: false });
    if (spot) return selectSpot(spot);
    if (selMarker) selMarker.remove();
    selMarker = L.marker(ll(bigMap, o.px, o.py), { icon: divIcon('<span class="mk-select"></span>', 40), interactive: false, zIndexOffset: 900 }).addTo(bigMap);
  }
  function goMap(o, spot) {
    if (!o?.map) return;
    // „Mój postęp”: rzecz spoza odkrytych okolic pokazujemy zaznaczeniem, bez granic widoku i bez wyłączania trybu
    const unveil = mapMine() && (spot ? !isSet(spot.flag) : true) && !revealTest(o.map)(o);
    if (unveil) state.mapPeek = true;
    state.mapFocus = { title: o.name || spot?.items?.map(i => i.name).join(", ") || "wybrane miejsce", at: [o, ...(spot ? [spot] : [])] };
    ensureGame({ dlc: o.map === "M10" });
    if (location.hash === "#map") { closeDrawer(); state.map = o.map; viewMap(); focusMap(o, spot); return; }
    state.map = o.map; navTo("#map", () => focusMap(o, spot));
  }
  // ---------- NPC card: where they stand, quest, shop, gifts, drops (opened from the map; the quest is one click further) ----------
  // shop and services per talk script (talks.json, extract_sources.py): sold-out and unlock flags read from the save
  const npcTalks = async name => { const all = await load("talks") || {}, talks = new Set(W.npcs.filter(n => n.name === name).map(n => String(n.talk)));
    return Object.entries(all).filter(([t, s]) => talks.has(t) || (!talks.size && s.who === name)).map(([, s]) => s); };
  async function shopRows(name) {
    const rows = [...new Map((await npcTalks(name)).flatMap(s => s.rows).map(r => [r.item, r])).values()];
    // bought pieces are a binary counter in the flags from `sold` on: flag sold+k is worth 2^k (extract_sources.py)
    const bits = r => r.qty > 0 && r.sold ? [...Array(r.qty.toString(2).length).keys()].map(k => r.sold + k) : [];
    const ids = [...new Set(rows.flatMap(r => [...bits(r), r.unlock]).filter(Boolean))];
    const flags = live.on && ids.length ? await readFlags(ids) : {};
    return rows.map(r => ({ ...r, it: itemByKey(r.item),
      bought: live.on ? bits(r).reduce((n, f, k) => n + (flags[f] ? 2 ** k : 0), 0) : 0,
      locked: live.on && !!r.unlock && !flags[r.unlock] })).filter(r => r.it);
  }
  const stockText = r => r.locked ? "jeszcze niedostępne" : r.qty <= 0 ? "" : r.bought >= r.qty ? "wyprzedane"
    : r.bought ? `kupione ${r.bought} z ${r.qty}` : `${r.qty} szt.`;
  // portrait rendered from the game's 3D model (render_portraits.py); the last placement usually has the late-game look
  const npcRender = name => W.npcs.filter(n => n.name === name && n.render).pop()?.render || null;
  async function openNpc(name) {
    await Promise.all([sourcesIndex(), itemsIndex()]);
    const stock = await shopRows(name), services = [...new Set((await npcTalks(name)).flatMap(s => s.services || []))];
    // one row per region: the same character stands in a few spots of one area during the quest
    const spots = [...new Map([...W.npcs.filter(n => n.name === name && n.map), ...W.pois.filter(p => npcMarker(p) && p.people.some(x => x[0] === name))]
      .map(p => [p.region_pl || p.map_id, p])).values()];
    const now = W.pois.filter(p => p.people?.some(x => x[0] === name && textOn(x)));
    const gifts = itemsFrom(s => s.gifts?.some(g => g.who === name)), loot = itemsFrom(s => s.enemies?.some(e => e.who === name));
    const drops = W.items.filter(t => t.enemy?.name === name), inv = W.invaders.filter(x => x.name === name && !hiddenInvader(x)), q = npcQuest({ name });
    const signs = W.summons.filter(s => s.name === name);
    const itemRow = (it, right) => listRow(`data-go="item:${it.category}:${it.id}"`, ICON(it.icon), esc(hiddenItem(it) ? "· · ·" : it.name), right);
    const here = now[0] || spots[0], render = npcRender(name);
    drawer(`<div class="d-hero">${portrait(render && "r:" + render, "hero-portrait", "knight")}<div class="eyebrow">Postać</div><div class="d-title">${esc(name)}</div>
      <div class="d-loc">${esc(here?.region_pl || "")}</div></div>
      ${now.length ? `<div class="d-section"><h4>Teraz</h4>${now.map(p => listRow(null, null, esc(p.name || "znacznik postaci z gry"), esc(p.region_pl || ""))).join("")}
        <p class="view-sub" style="margin:8px 0 0">Według mapy gry i flag z Twojego save'a.</p></div>` : ""}
      ${q ? questLinks([q]) : ""}
      ${services.length ? `<div class="d-section"><h4>Usługi</h4><div class="rtags">${services.map(s => `<span class="rtag">${esc(s)}</span>`).join("")}</div></div>` : ""}
      ${stock.length ? `<div class="d-section"><h4>Sklep</h4>${stock.filter(r => !(spoilers() && r.locked)).map(r => itemRow(r.it, [r.trade ? "za: " + esc(r.trade) : r.price ? pl(r.price, "run", "runy", "runów") : "",
          stockText(r)].filter(Boolean).join(" · "))).join("")}
        ${live.on ? `<p class="view-sub" style="margin:8px 0 0">Stan z Twojego save'a: ile sztuk z limitu już kupiłeś; „jeszcze niedostępne” pojawi się
          później (np. po oddaniu dzwonka kulistego)${spoilers() ? ", w trybie bez spoilerów ukryte" : ""}.</p>` : ""}</div>` : ""}
      ${gifts.length ? `<div class="d-section"><h4>Daje w rozmowie</h4>${gifts.map(it => itemRow(it, have(it) ? "masz" : "")).join("")}</div>` : ""}
      ${drops.length || loot.length ? `<div class="d-section"><h4>Po śmierci zostawia</h4>${drops.flatMap(t => t.items.map(x => findItem(x.cat, x.id)).filter(Boolean).map(it => itemRow(it, isSet(t.flag) ? "zebrane" : "")))
          .concat(loot.map(it => itemRow(it, have(it) ? "masz" : ""))).join("")}
        ${loot.some(it => it.kind === "bell_bearing") ? '<p class="view-sub" style="margin:8px 0 0">Dzwonek kulisty oddany Cieniom bliźniaczej służki w Twierdzy Okrągłego Stołu odblokowuje u nich towar tej postaci.</p>' : ""}</div>` : ""}
      ${signs.length ? `<div class="d-section"><h4>Znaki przywołania</h4>${signs.map((s, i) => listRow(`data-npc-sign="${i}"`, null, esc(s.region_pl || nearestGrace(s)?.name || s.map_id),
          s.helper ? "pomoc · na mapie" : "na mapie")).join("")}</div>` : ""}
      ${inv.length ? `<div class="d-section"><h4>Najazdy</h4>${inv.map(x => listRow(`data-go="invader:${x.id}"`, null, esc(x.name), isSet(x.flag) ? "pokonany" : "niepokonany")).join("")}</div>` : ""}
      ${spots.length ? `<div class="d-section"><h4>Gdzie bywa</h4>${spots.slice(0, 8).map((p, i) => listRow(`data-npc-spot="${i}"`, null, esc(p.region_pl || p.map_id || ""), "na mapie")).join("")}</div>` : ""}
      ${here?.map ? `<div class="d-section"><h4>Na mapie</h4><div class="minimap" id="minimap"></div></div>` : ""}`,
      () => { document.querySelectorAll("[data-npc-spot]").forEach(b => b.onclick = () => goMap({ ...spots[+b.dataset.npcSpot], name }));
        document.querySelectorAll("[data-npc-sign]").forEach(b => b.onclick = () => goMap({ ...signs[+b.dataset.npcSign], name: name + ": znak" }));
        if (here?.map) miniMap($("#minimap"), here.map, here.px, here.py, null, [{ label: "Pokaż na mapie", primary: true, run: () => goMap({ ...here, name }) }]); });
  }
  // ---------- teleports (warps.json): where they lead, what they need; a button moves the map to the destination ----------
  const WARP = { waygate: "Brama teleportu", trap_chest: "Skrzynia-pułapka", local: "Przejście", short: "Przejście", cutscene: "Przejście ze scenką" };
  async function openWarp(w) {
    await itemsIndex();
    const from = nearestGrace(w.src), to = nearestGrace(w.dst), keys = (w.items || []).map(id => findItem("goods", id)).filter(Boolean);
    const open = w.flag ? isSet(w.flag) : null;
    drawer(`<div class="eyebrow">${esc(w.src.map === w.dst.map ? MAPS[w.src.map] : MAPS[w.src.map] + " → " + MAPS[w.dst.map])}</div>
      <div class="d-title" style="text-align:left;font-size:23px">${WARP[w.kind]}</div>
      <div class="d-section"><h4>Skąd</h4><p class="view-sub" style="margin:0">${from ? `przy łasce „${esc(from.name)}”${from.region ? ", " + esc(from.region) : ""}` : esc(w.src.map_id)}</p></div>
      <div class="d-section"><h4>Dokąd</h4><p class="view-sub" style="margin:0">${to ? `przy łasce „${esc(to.name)}”${to.region ? ", " + esc(to.region) : ""}` : esc(w.dst.map_id)}${w.dst.approx ? " (w lochu, znacznik przy wejściu)" : ""}</p></div>
      ${w.kind === "trap_chest" ? '<p class="note">Otwarcie skrzyni przenosi cię w to miejsce. Nie da się wrócić tą samą drogą.</p>' : ""}
      ${open !== null ? `<p class="view-sub">${open ? "Brama jest już otwarta w Twoim świecie." : "Brama jest zamknięta: gra wymaga spełnienia warunku (np. włożenia klucza albo postępu fabuły)."}</p>` : ""}
      ${keys.length ? `<div class="d-section"><h4>Wymaga</h4>${keys.map(it => listRow(`data-go="item:goods:${it.id}"`, ICON(it.icon), esc(it.name), have(it) ? "masz" : "")).join("")}</div>` : ""}
      <div class="d-section"><h4>Cel na mapie</h4><div class="minimap" id="minimap"></div></div>`,
      () => miniMap($("#minimap"), w.dst.map, w.dst.px, w.dst.py, null, [
        { label: "Przenieś do celu", primary: true, run: () => goMap({ ...w.dst, name: WARP[w.kind] + ": cel" }) },
        { label: "Pokaż wejście", run: () => goMap({ ...w.src, name: WARP[w.kind] }) }]));
  }
  // quest postaci: po imieniu NPC (pierwszy człon przed przecinkiem)
  const npcQuest = n => { const stem = (n.name || "").split(",")[0].trim(); return stem.length >= 3 ? W.quests.find(q => (q.npc || "").split(",")[0].trim() === stem) : null; };
  function goQuest(id) { state.quest = id; state.qFilter = "all"; ensureGame(W.quests.find(q => q.id === id)); if (location.hash === "#quests") { closeDrawer(); render(); } else navTo("#quests"); }
  // nazwy w tekstach questów: przedmioty (≥ 6 znaków), bossowie ważniejszych rang (rdzeń imienia), miejsca (łaski, lochy)
  const GENERIC = new Set(["rycerz", "strażnik", "nocna", "żołnierz", "duch", "ptak", "smok", "latający", "magmowy", "gnijący", "wielki", "starożytna", "starożytny", "bestia", "człowiek", "zabójca", "łowca", "onyksowy", "pradawny", "krwawy", "szalony", "królewski", "marynarz", "cmentarny", "dowódca", "awatar", "duet", "upadły", "apostoł", "szlachcic", "orędownik", "pobratymiec", "boska", "rudy", "dorosła"]);
  let refIdx = null;
  function refIndex() {
    if (refIdx || !ITEMS) return refIdx;
    const items = [...ITEMS.values()].filter(i => i.name && i.name.length >= 6 && i.icon > 0);
    const bossKeys = bossList().filter(b => ["great_rune", "legend", "major"].includes(b.tier)).map(b => {
      const stem = (b.name || "").split(/[ ,]/)[0]; return stem.length >= 5 && !GENERIC.has(stem.toLowerCase()) ? { b, stem } : null; }).filter(Boolean);
    const places = new Map();
    for (const g of W.graces) if (g.name && g.map) places.set(g.name, g);
    for (const p of W.pois) if (p.name && p.map) places.set(p.name, p);
    refIdx = { items, bossKeys, places };
    return refIdx;
  }
  let byName = null;
  const itemByName = n => { if (!ITEMS) return null; if (!byName) { byName = new Map(); for (const i of ITEMS.values()) if (!byName.has(i.name)) byName.set(i.name, i); } return byName.get(n) || null; };
  const questText = q => q.steps.map(st => (st.text || "") + " " + (st.next || "") + " " + (st.where || "")).join(" ");
  function questsFor(name) { return name && name.length >= 5 ? W.quests.filter(q => questText(q).includes(name)) : []; }
  function bossQuests(b) { const stem = (b.name || "").split(/[ ,]/)[0];
    return stem.length >= 5 && !GENERIC.has(stem.toLowerCase()) ? W.quests.filter(q => questText(q).includes(stem)) : []; }
  // tekst z linkami (bezpieczny: najpierw escapujemy, potem podmieniamy znalezione nazwy na przyciski)
  function linkify(text) {
    const R = refIndex(); let html = esc(text);
    if (!R) return html;
    const hits = [];
    for (const it of R.items) if (text.includes(it.name)) hits.push([it.name, `item:${it.category}:${it.id}`]);
    for (const { b, stem } of R.bossKeys) if (text.includes(stem)) hits.push([stem, `boss:${b.id}`]);
    for (const [n, pl] of R.places) if (n.length >= 6 && text.includes(n)) hits.push([n, `place:${n}`]);
    hits.sort((a, b) => b[0].length - a[0].length);                     // najpierw dłuższe nazwy
    const used = [];
    for (const [n, go] of hits) {
      const e = esc(n), i = html.indexOf(e);
      if (i < 0 || used.some(([a, z]) => i < z && i + e.length > a)) continue;
      const tag = `<a class="xlink x-${go.split(":")[0]}" data-go="${esc(go)}">${e}</a>`;
      html = html.slice(0, i) + tag + html.slice(i + e.length);
      used.forEach(u => { if (u[0] > i) { u[0] += tag.length - e.length; u[1] += tag.length - e.length; } });
      used.push([i, i + tag.length]);
    }
    return html;
  }
  // sekcja „Powiązania” w szufladzie przedmiotu i bossa: questy, w których występuje
  const questLinks = qs => qs.length ? `<div class="d-section"><h4>Powiązania</h4><div class="xlinks">
      ${qs.map(q => `<button class="xbtn x-quest" data-go="quest:${esc(q.id)}">✦ Quest<small>${esc(q.name)}</small></button>`).join("")}</div></div>` : "";
  document.addEventListener("click", async e => {
    const a = e.target.closest("[data-go]"); if (!a) return;
    e.preventDefault(); e.stopPropagation();
    const [k, ...r] = a.dataset.go.split(":"), v = r.join(":");
    if (k === "item") { await itemsIndex(); const it = findItem(r[0], +r[1]); if (it) openItem(it); }
    else if (k === "boss") openBoss(+v);
    else if (k === "bossmap") { const b = bossList().find(x => x.id === +v); if (b) goMap(b); }
    else if (k === "spot") { const t = W.items[+v]; if (t) goMap(t, t); }
    else if (k === "pin") { const o = pins[+v]; if (o) goMap(o); }
    else if (k === "drops") showDrops(drops[+v]);
    else if (k === "invader") { const x = W.invaders.find(i => i.id === +v); if (x) openInvader(x); }
    else if (k === "npc") openNpc(v);
    else if (k === "quest") goQuest(v);
    else if (k === "place") { const pl = refIndex()?.places.get(v); if (pl) goMap(pl); }
  });
  // ---------- jak zdobyć: bossowie, kupcy, łup z przeciwników, nagrody ze zdarzeń (extract_sources.py) ----------
  let SRC = null;
  async function sourcesIndex() { if (!SRC) SRC = await load("item_sources") || {}; return SRC; }
  const pins = [], drops = [];                             // miejsca do przejścia na mapę (data-go="pin:N"), grupy przeciwników ("drops:N")
  const pinGo = o => { pins.push(o); return `data-go="pin:${pins.length - 1}"`; };
  function sourcesHTML(it) {
    const src = SRC?.[`${it.category}:${it.id}`]; if (!src) return "";
    const rows = [];
    for (const id of src.bosses || []) { const b = W.bosses.find(x => x.id === id); if (!b) continue;
      rows.push(`<button class="xbtn x-boss" data-go="boss:${b.id}">⚔ Nagroda za bossa<small>${esc(b.name)}${b.region_pl ? " · " + esc(b.region_pl) : ""}</small></button>`); }
    for (const wk of src.on_weapon || []) {
      const [c, id] = wk.split(":"), w = findItem(c, +id);
      if (!w) continue;
      rows.push(`<button class="xbtn x-event" data-go="item:${wk}">◇ Na broni<small>${esc(w.name)} · zdejmij popiół przy łasce</small></button>`);
    }
    for (const g of src.gifts || []) { const ng = !g.who && g.map && nearestGrace(g);
      rows.push(`<button class="xbtn x-event" ${g.map ? pinGo(g) : "disabled"}>✦ Podarunek w rozmowie<small>${g.who ? esc(g.who) : "postać albo obiekt" + (ng ? " · okolice: " + esc(ng.name) : "")}${g.map ? " · ⌖ na mapie" : ""}</small></button>`); }
    for (const sh of src.shops || []) {
      if (sh.who.startsWith("Przeróbka")) { rows.push(`<button class="xbtn x-shop" disabled>✂ Przeróbka odzienia<small>przy miejscu łaski${sh.trade ? " · z: " + esc(sh.trade) : ""}</small></button>`); continue; }
      rows.push(`<button class="xbtn x-shop" ${sh.map ? pinGo(sh) : "disabled"}>⚖ ${sh.trade ? "Wymiana" : "U kupca"}<small>${esc(sh.who)}${sh.trade ? " · za: " + esc(sh.trade)
        : sh.price >= 10 ? " · " + pl(sh.price, "run", "runy", "runów") : ""}${sh.map ? " · ⌖ na mapie" : ""}</small></button>`); }
    for (const id of src.invaders || []) { const x = W.invaders.find(v => v.id === id); if (!x) continue; const hid = hiddenInvader(x);
      rows.push(`<button class="xbtn x-boss" data-go="invader:${x.id}">☠ Nagroda za najeźdźcę<small>${hid ? "nieznany najeźdźca" : esc(x.name)}${x.region_pl ? " · " + esc(x.region_pl) : ""}</small></button>`); }
    for (const e of src.enemies || []) { drops.push({ title: e.who ? `${it.name} (${e.who})` : it.name, at: e.at });
      rows.push(`<button class="xbtn x-enemy" ${e.at.length ? `data-go="drops:${drops.length - 1}"` : "disabled"}>☠ Łup z przeciwnika<small>${e.who ? esc(e.who) : "przeciwnik"} · szansa ${num(e.chance)}% · ${pl(e.count, "przeciwnik", "przeciwników", "przeciwników")}${e.at.length ? " · ⌖ pokaż na mapie" : ""}</small></button>`); }
    for (const ev of src.events || []) {
      if (ev.map_id === "common" || !ev.map) { rows.push(`<button class="xbtn x-event" disabled>✦ Nagroda ze zdarzenia<small>za postęp w grze lub queście</small></button>`); continue; }
      const ng = nearestGrace(ev);
      rows.push(`<button class="xbtn x-event" ${pinGo(ev)}>✦ Nagroda ze zdarzenia<small>quest albo postać${ng ? " · okolice: " + esc(ng.name) : ""} · ⌖ na mapie</small></button>`); }
    return rows.length ? `<div class="d-section"><h4>Jak zdobyć</h4><div class="xlinks">${rows.join("")}</div></div>` : "";
  }
  // wszystkie miejsca przeciwników z danym łupem na mapie (enemies.json wczytywany dopiero tutaj, ok. 0,4 MB)
  async function showDrops(g) {
    const all = await load("enemies"), pts = all && g.at.map(i => all[i]);
    if (!pts || pts.some(p => !p)) return banner("Brak miejsc przeciwników", "Plik enemies.json nie pasuje do danych. Przygotuj dane od nowa.");
    const per = {}; for (const p of pts) per[p[0]] = (per[p[0]] || 0) + 1;
    const m = Object.entries(per).sort((a, b) => b[1] - a[1])[0][0];
    state.mapDrops = { title: g.title, pts };
    state.mapFocus = { title: g.title, at: [] };          // only the drop places, the rest of the map hidden
    if (state.mine && pts.some(([pm, px, py]) => !revealTest(pm)({ px, py }))) state.mapPeek = true;
    ensureGame({ dlc: m === "M10" });
    state.map = m;
    const fit = () => { const here = pts.filter(p => p[0] === m).map(p => ll(bigMap, p[1], p[2]));
      if (bigMap && here.length) bigMap.fitBounds(L.latLngBounds(here).pad(.3), { maxZoom: 4.5, animate: false }); };
    if (location.hash === "#map") { closeDrawer(); viewMap(); fit(); } else navTo("#map", fit);
  }
  // ukryte statystyki z SpEffectParam: talizmany, zbroje, bronie (gdy w ręce)
  function effectsHTML(it) {
    const fx = W.effects?.[`${it.category}:${it.id}`];
    if (!fx?.length) return "";
    return `<div class="d-section"><h4>Ukryte statystyki</h4><div class="fx-list">${fx.map(f => `<div class="fx ${f.good ? "up" : "down"}">
      <span>${esc(f.label)}${f.cond ? `<small>${esc(f.cond)}</small>` : ""}</span><b>${esc(f.v)}</b></div>`).join("")}</div>
      <p class="view-sub fx-note">Dokładne liczby z parametrów gry${it.category === "weapon" ? " (działają, gdy broń jest w ręce)" : ""}.</p></div>`;
  }
  // jedna karta przedmiotu we wszystkich widokach; ctx.eq: założony egzemplarz z Postaci (ulepszenie, nasycenie),
  // ctx.spot: skarb z mapy, z którego ją otwarto
  // remembrance exchanges at Enia: items whose shop source is paid with this remembrance (item_sources.json)
  // catalogue item of an item_sources.json key ("weapon:9000000"); items whose sources pass a test
  const itemByKey = k => findItem(...k.split(":").map((v, i) => i ? +v : v));
  const itemsFrom = test => Object.entries(SRC || {}).filter(([, s]) => test(s)).map(([k]) => itemByKey(k)).filter(Boolean);
  const runesNote = it => it.runes ? `<p class="ib-note"><b>Runy za użycie:</b> ${fmt(it.runes)}</p>` : "";
  function remembranceHTML(it) {
    const ex = itemsFrom(s => s.shops?.some(sh => sh.trade === it.name));
    return `${runesNote(it)}
      ${ex.length ? `<div class="d-section"><h4>Wymiana u Enii</h4>${ex.map(x => listRow(`data-go="item:${x.category}:${x.id}"`, ICON(x.icon),
        esc(hiddenItem(x) ? "· · ·" : x.name), have(x) ? "masz" : "")).join("")}
        <p class="view-sub" style="margin:8px 0 0">Jeden wizerunek wymienisz na jedną rzecz. Drugą dostaniesz po skopiowaniu wizerunku w wędrującym mauzoleum.</p></div>` : ""}`;
  }
  function openItem(it, ctx = {}) {
    pins.length = 0; drops.length = 0;
    if (!ctx.eq && hiddenItem(it)) return drawer(`<div class="d-hero"><span class="portrait hero-portrait item alive"></span><div class="d-title">Nieodkryty przedmiot</div>
        <div class="d-loc">${esc(CATS.find(c => c.f(it))?.name || "")} · ${["", "zwykły", "rzadki", "legendarny"][it.rarity || 0]}</div></div><div class="rule"></div>
        <p class="note">Jeszcze go nie masz. Tryb bez spoilerów ukrywa rzadkie i legendarne przedmioty, których nie zdobyłeś.</p>
        <button class="btn" id="revealOne">Odsłoń ten przedmiot</button>`, () => $("#revealOne").onclick = () => { state.revealed.add(itemKey(it));
          if (location.hash === "#items") viewItems().then(() => openItem(it, ctx)); else openItem(it, ctx); });
    const h = ctx.eq ? true : have(it), spots = whereItem(it), cat = CATS.find(c => c.f(it)), srcHTML = sourcesHTML(it), linksHTML = questLinks(questsFor(it.name));
    const note = usageNote(it), raw = ctx.eq?.id, fr = frame(it, raw), up = ctx.eq?.upgrade ? ` +${ctx.eq.upgrade}` : "";
    const t = ctx.spot, here = t || spots[0];
    drawer(`<div class="d-hero"><span class="portrait hero-portrait item ${fr.cls} ${h ? "" : "alive"}" style="${fr.style}"><img src="${ICON(it.icon)}" alt="">${fr.gems}</span>
      <div class="eyebrow">${cat ? cat.name : esc(KINDS[it.kind]?.[0] || "")}${it.dlc ? " · DLC" : ""}</div><div class="d-title">${esc(it.name + up)}</div><div class="d-loc">${esc(it.name_en)}</div>${rarityTags(it, raw)}</div>
      ${t ? `<div class="d-section"><h4>To miejsce</h4><p class="view-sub" style="margin:0">${spotNote(t)}</p></div>` : ""}
      ${t?.enemy?.stats ? bossStatsHtml(t.enemy.stats) : ""}${live.on && t?.enemy?.stats ? '<div class="d-section" id="hitsBox"></div>' : ""}
      <div class="d-stats"><div><b>${h ? "✓" : h === null ? "?" : "—"}</b><span>${h ? "Posiadane" : h === null ? "Nieznane" : "Brakujące"}</span></div><div><b>${spots.length}</b><span>Na mapie</span></div><div><b>${["–", "Zw.", "Rz.", "Leg."][it.rarity || 0]}</b><span>Rzadkość</span></div></div>
      ${it.info ? `<p class="ib-info">„${esc(it.info)}”<span>${it.kind === "seamless" ? "opis z moda" : "opis z gry"}</span></p>` : ""}
      ${note ? `<p class="ib-note"><b>Do czego służy:</b> ${esc(note)}</p>` : ""}
      ${it.kind === "remembrance" ? remembranceHTML(it) : runesNote(it)}
      ${srcHTML}
      ${linksHTML}
      ${effectsHTML(it)}
      ${statsHTML(it)}
      ${spots.length ? `<div class="d-section"><h4>Gdzie leży</h4>${spots.slice(0, 6).map(t => { const ng = nearestGrace(t);
        return `<div class="reward"><span>${esc(t.region_pl || t.map_id)}${ng ? ` · przy łasce „${esc(ng.name)}”` : ""}</span><span>${isSet(t.flag) ? "zebrane" : "do zebrania"}</span></div>`; }).join("")}${spots.length > 6 ? `<p class="view-sub" style="margin:8px 0 0">i jeszcze ${pl(spots.length - 6, "miejsce", "miejsca", "miejsc")}. Wszystkie pokaże mapa (kliknij mini-mapę).</p>` : ""}</div>`
        : srcHTML || linksHTML ? "" : '<p class="note">Nie leży na mapie i nie znamy jeszcze źródła w danych gry (np. łup ze zwłok przy obiekcie albo podarunek postaci).</p>'}
      ${here?.map ? `<div class="d-section"><h4>Na mapie</h4><div class="minimap" id="minimap"></div></div>` : ""}`,
      () => { if (t?.enemy?.stats) fillHits(t.enemy.stats); if (here?.map) miniMap($("#minimap"), here.map, here.px, here.py, it.icon, [
        { label: spots.length > 1 ? "To miejsce" : "Pokaż na mapie", primary: true, run: () => goMap(here, here) },
        ...(spots.length > 1 ? [{ label: `Wszystkie miejsca (${spots.length})`, run: () => { goMap({ ...spots[0] }); state.mapFocus = null; state.mapQuery = it.name; state.mapExact = true; viewMapKeep(); } }] : [])]); });
  }
  /* ---------------- postać: założony ekwipunek (z save'a) ---------------- */
  const CLASS_PL = { vagabond: "Włóczęga", warrior: "Wojownik", hero: "Bohater", bandit: "Bandyta", astrologer: "Astrolog", prophet: "Prorok",
    samurai: "Samuraj", prisoner: "Więzień", confessor: "Spowiednik", wretch: "Nędzarz" };
  const eqItem = (e, cat) => { if (!e) return null; const id = cat === "weapon" ? (e.base_id ?? e.id) : e.id;
    const it = findItem(cat, id) || (cat === "goods" ? findItem("goods", id - id % 100) : null); return it ? { ...it, eq: e } : null; };
  // portret głowy: render 3D z plików gry (twarz i włosy w kolorach z save'a + założony hełm,
  // tools/extract/render_character.py); gdy renderu brak — sama ikona hełmu
  // brak renderu → ikona hełmu (albo nic)
  window.__hpFallback = img => { img.onerror = null; if (img.dataset.fb) { img.src = img.dataset.fb; img.className = "hp-icon"; } else img.remove(); };
  // wersja portretu z backendu (zdarzenie SSE 'portrait' po ponownym renderze) — wymusza odświeżenie obrazka
  const portraitVer = {};
  const headSrc = (file, slot, eq) => `${ASSETS}/renders/char_${file}_${slot}.png?h=${eq?.head?.id ?? 0}&v=${encodeURIComponent(portraitVer[file + ":" + slot] || "")}`;
  function doll(eq, cls = "", file = live.file, slot = live.slot) {
    const it = eq?.head && findItem("armor", eq.head.id);
    return `<div class="headp ${cls}">${file != null ? `<img class="hp-render" src="${headSrc(file, slot, eq)}" alt="${esc(it?.name || "")}"
      data-fb="${it ? ICON(it.icon) : ""}" onerror="__hpFallback(this)">` : it ? `<img class="hp-icon" src="${ICON(it.icon)}" alt="">` : sigil("knight")}</div>`;
  }
  const stateCache = new Map();
  const charState = (file, slot) => { const k = file + ":" + slot;
    if (!stateCache.has(k)) stateCache.set(k, api(`/api/state?file=${file}&slot=${slot}&sections=equipment`, 15000).catch(() => null));   // portret + klasa: wystarczy ekwipunek (~2 KB zamiast ~1,5 MB)
    return stateCache.get(k); };
  function slot(it, label, opts = {}) {
    const up = it?.eq?.upgrade ? ` +${it.eq.upgrade}` : "";
    const f = frame(it, it?.eq?.id), inf = it && affinities(it, it.eq?.id).infuse;
    return `<button class="eq-slot ${f.cls} ${opts.active ? "active" : ""} ${it ? "" : "empty"} ${opts.big ? "big" : ""}" style="${f.style}" ${it ? `data-eq="${it.category}:${it.id}:${it.eq?.id ?? ""}:${it.eq?.upgrade ?? ""}"` : "disabled"} title="${esc(it ? (inf ? inf + " " : "") + it.name + up : label + ": pusto")}">
      ${it ? `<img src="${ICON(it.icon)}" alt="">${f.gems}` : `<span class="eq-empty">◇</span>`}${up ? `<span class="eq-up">${up.trim()}</span>` : ""}<span class="eq-label">${esc(label)}</span></button>`;
  }
  // ---------- atrybuty i miękkie progi (krzywe CalcCorrectGraph z plików gry → stat_curves.json) ----------
  // wartość krzywej dla x: progi s[i], wartości g[i], wykładnik krzywizny e[i] (jak w grze)
  function curve(c, x) {
    const s = c.stages, g = c.values, e = c.exp;
    x = Math.max(s[0], Math.min(s[4], x));
    for (let i = 0; i < 4; i++) if (x <= s[i + 1]) {
      let r = (x - s[i]) / (s[i + 1] - s[i] || 1);
      r = e[i] > 0 ? r ** e[i] : 1 - (1 - r) ** (-e[i]);
      return g[i] + (g[i + 1] - g[i]) * r;
    }
    return g[4];
  }
  // atrybut → co daje (krzywa, jednostka, opis); progi = środkowe progi krzywej (miękkie capy)
  const ATTR_INFO = [
    { k: "vigor", name: "Witalność", fx: [{ c: "hp", label: "PŻ", unit: "" }] },
    { k: "mind", name: "Umysł", fx: [{ c: "fp", label: "PS", unit: "" }] },
    { k: "endurance", name: "Wytrzymałość", fx: [{ c: "stamina", label: "Energia", unit: "" }, { c: "equip_load", label: "Udźwig", unit: "", dec: 1 }] },
    { k: "strength", name: "Siła", fx: [{ c: "phys_scaling", label: "Skalowanie broni (fizyczne)", unit: "%" }] },
    { k: "dexterity", name: "Zręczność", fx: [{ c: "phys_scaling", label: "Skalowanie broni (fizyczne)", unit: "%" }] },
    { k: "intelligence", name: "Inteligencja", fx: [{ c: "elem_scaling", label: "Skalowanie czarów i magii", unit: "%" }] },
    { k: "faith", name: "Wiara", fx: [{ c: "elem_scaling", label: "Skalowanie inkantacji i świętych", unit: "%" }] },
    { k: "arcane", name: "Tajemność", fx: [{ c: "status_scaling", label: "Kumulacja statusów (krwotok, trucizna…)", unit: "%" }] },
  ];
  const NEAR = 3;                                   // „blisko progu” = brakuje ≤ 3 punktów
  function attrRow(a, v, curves) {
    const main = curves[a.fx[0].c];
    if (!main) return "";
    // progi krzywej: „cap” gdy po progu każdy punkt daje wyraźnie mniej, „przyspieszenie” gdy więcej (np. PŻ po 25, PS po 15)
    const rate = (c, i) => (curve(c, c.stages[i + 1]) - curve(c, c.stages[i])) / Math.max(1, c.stages[i + 1] - c.stages[i]);
    const marks = [1, 2, 3].map(i => ({ t: Math.round(main.stages[i]), cap: rate(main, i) < rate(main, i - 1) * 0.95 }));
    const caps = marks.filter(m => m.cap).map(m => m.t), next = caps.find(t => v < t), last = caps[caps.length - 1];
    const knee = marks.find(m => !m.cap && v < m.t);
    const state = next != null && next - v <= NEAR ? "near" : last != null && v >= last ? "capped" : "";
    const fmtv = (fx, x) => { const val = curve(curves[fx.c], x); return fx.unit === "%" ? Math.round(val) + "%" : fx.dec ? num(Math.round(val * 10) / 10) : num(Math.floor(val + 1e-6)); };   // gra zaokrągla PŻ/PS/energię w dół
    const gain = fx => { const d = curve(curves[fx.c], v + 1) - curve(curves[fx.c], v); return d <= 0 ? "0" : (fx.unit === "%" ? num(Math.round(d * 10) / 10) + " pp" : "+" + (d >= 10 ? Math.round(d) : num(Math.round(d * 10) / 10))); };
    const pct = x => (Math.min(99, x) - 1) / 98 * 100;
    const stagesTip = fx => { const c = curves[fx.c], st = c.stages;
      return `<table class="cap-table"><tr><th>Przedział</th><th>${esc(fx.label)}</th><th>na punkt</th></tr>${[0, 1, 2, 3].map(i => {
        const lo = Math.max(1, Math.round(st[i])), hi = Math.round(st[i + 1]), d = (curve(c, hi) - curve(c, lo)) / Math.max(1, hi - lo);
        const on = v >= lo && v <= hi;
        return `<tr class="${on ? "on" : ""}"><td>${lo}–${hi}</td><td>${fmtv(fx, lo)} → ${fmtv(fx, hi)}</td><td>${fx.unit === "%" ? num(Math.round(d * 100) / 100) + " pp" : (d >= 10 ? Math.round(d) : num(Math.round(d * 10) / 10))}</td></tr>`; }).join("")}</table>`; };
    const note = [state === "near" ? `Jeszcze <b>${next - v}</b> ${next - v === 1 ? "punkt" : "punkty"} do miękkiego progu <b>${next}</b>. Warto dobić, potem każdy punkt daje mniej.`
      : state === "capped" ? `Powyżej ostatniego miękkiego progu (${last}). Kolejne punkty dają już niewiele.`
      : next != null ? `Następny miękki próg: <b>${next}</b> (brakuje ${next - v}).` : "",
      knee && (next == null || knee.t < next) ? `Od <b>${knee.t}</b> każdy punkt daje <b>więcej</b> niż teraz. Opłaca się tam dojść.` : ""].filter(Boolean).join(" ");
    return `<div class="attr ${state}" tabindex="0">
      <span class="attr-name">${a.name}</span><b class="attr-val">${v}</b>
      <span class="attr-bar"><i style="width:${pct(v)}%"></i>${marks.map(m => `<s class="${m.cap ? "cap" : "knee"}" style="left:${pct(m.t)}%" title="${m.cap ? "miękki próg" : "przyspieszenie"} ${m.t}"></s>`).join("")}</span>
      <span class="attr-fx">${a.fx.map(fx => `${esc(fx.label.split(" (")[0])}: <b>${fmtv(fx, v)}</b> <em>${gain(fx)}/pkt</em>`).join(" · ")}</span>
      <div class="attr-tip"><div class="eyebrow">${a.name} · ${v}</div>${a.fx.map(stagesTip).join("")}<p>${note}</p>
        <p class="src">Progi z plików gry (CalcCorrectGraph ${a.fx.map(f => curves[f.c].graph).join(", ")}).</p></div>
    </div>`;
  }
  function attrPanel(st, curves) {
    const at = st?.stats?.attributes;
    if (!at || !curves) return "";
    const eqw = ["head", "chest", "arms", "legs"].reduce((a, k) => a + (findItem("armor", st.equipment?.[k]?.id)?.stats?.weight || 0), 0)
      + [...(st.equipment?.right_weapons || []), ...(st.equipment?.left_weapons || [])].reduce((a, e) => a + (e ? findItem("weapon", e.base_id ?? e.id)?.stats?.weight || 0 : 0), 0);
    const load = curve(curves.equip_load, at.endurance), ratio = eqw / load;
    const roll = ratio <= .3 ? ["Lekki", "light"] : ratio <= .7 ? ["Średni", "mid"] : ratio <= 1 ? ["Ciężki", "heavy"] : ["Przeciążenie", "over"];
    const s = st.stats;
    const tile = (val, label, sub = "", cls = "", bar = null) => `<div class="ad-tile ${cls}"><span class="ad-label">${label}</span><b>${val}</b>${sub ? `<small>${sub}</small>` : ""}${bar != null ? `<span class="ad-bar"><i style="width:${Math.min(100, bar * 100)}%"></i></span>` : ""}</div>`;
    return `<div class="attr-panel"><div class="attr-head"><h4>Atrybuty</h4>
        <div class="attr-legend"><span><i class="lg-near"></i>blisko progu</span><span><i class="lg-capped"></i>powyżej progów</span><span><i class="lg-knee"></i>przyspieszenie</span></div></div>
      <div class="attr-derived">
        ${tile(fmt(s.hp.max), "PŻ")}${tile(fmt(s.fp.max), "PS")}${tile(fmt(s.stamina.max), "Energia")}
        ${tile(`${num(Math.round(eqw * 10) / 10)}<span class="ad-of"> / ${num(Math.round(load * 10) / 10)}</span>`, "Obciążenie", `${roll[0]} · ${Math.round(ratio * 100)}%`, "roll-" + roll[1], ratio)}</div>
      ${ATTR_INFO.map(a => attrRow(a, at[a.k], curves)).join("")}
      <p class="view-sub attr-hint">Najedź na atrybut, by zobaczyć progi i ile daje każdy punkt. Obciążenie liczone z broni i zbroi (bez talizmanów).</p></div>`;
  }
  // zwiedzone obszary: regions_unlocked z save'a (PlayRegion) z nazwami z backendu — kraina → podregiony i lochy
  function visitedAreas(st) {
    const rs = (st?.regions || []).filter(r => r.name);
    if (!rs.length) return "";
    const by = new Map();
    for (const r of rs) {
      const k = r.region || (r.kind === "overworld" ? r.name : "Inne obszary");
      if (!by.has(k)) by.set(k, new Map());
      const nm = r.name === k && r.kind === "overworld" ? null : r.name;   // sama kraina — bez osobnego chipa
      if (nm) by.get(k).set(nm, r.kind);
    }
    const order = [...by.keys()].sort((a, b) => by.get(b).size - by.get(a).size || a.localeCompare(b, "pl"));
    return `<div class="areas corners"><div class="eq-head"><h4>Zwiedzone obszary</h4><span class="view-sub">${pl(by.size, "kraina", "krainy", "krain")} · ${pl([...by.values()].reduce((a, m) => a + m.size, 0), "miejsce", "miejsca", "miejsc")} (z twojego save'a)</span></div>
      ${order.map(k => `<div class="area-row"><span class="area-name">${esc(k)}</span><span class="area-chips">${[...by.get(k)].sort((a, b) => (a[1] === "dungeon") - (b[1] === "dungeon") || a[0].localeCompare(b[0], "pl"))
        .map(([n, kind]) => `<span class="chip area-chip ${kind === "dungeon" ? "dungeon" : ""}" title="${kind === "dungeon" ? "loch / zamknięty obszar" : "podregion"}">${esc(n)}</span>`).join("") || '<span class="view-sub">—</span>'}</span></div>`).join("")}</div>`;
  }
  async function viewCharacter() {
    await itemsIndex();
    const st = live.state, eq = st?.equipment, c = D.character, ch = st?.character || {};
    const head = `<div class="view-head"><div><div class="eyebrow">Zmatowiały</div><h1 class="title">${esc(c.name)}</h1>
      <div class="view-sub">${ch.archetype ? `${CLASS_PL[ch.archetype.name] || ch.archetype.name} · ` : ""}poziom ${c.level} · ${c.playtime_s < 3600 ? Math.round(c.playtime_s / 60) + " min" : Math.round(c.playtime_s / 3600) + " h"} w grze${c.last_grace ? ` · ostatnia łaska: ${esc(c.last_grace)}` : ""}</div></div></div>`;
    if (!eq) { main.innerHTML = `<div class="view">${head}<p class="note">Ekwipunek postaci pokaże się, gdy działa backend (python backend\\server.py), który czyta go z twojego save'a.</p></div>`; return; }
    const w = (arr, side) => arr.map((e, i) => slot(eqItem(e, "weapon"), `${side} ${i + 1}`, { active: eq.active_weapon?.[side === "Prawa" ? "right" : "left"] === i })).join("");
    const helm = eqItem(eq.head, "armor"), curves = await load("stat_curves");
    if (location.hash !== "#character") return;
    main.innerHTML = `<div class="view">${head}
      <div class="char-sheet">
        <div class="char-hero corners">${doll(eq, "big")}
          <div class="char-hero-name">${esc(c.name)}</div><div class="view-sub">${ch.archetype ? esc(CLASS_PL[ch.archetype.name] || "") : ""}${ch.body_type ? ` · typ ciała ${esc(ch.body_type.name)}` : ""}</div>
          <div class="char-mini"><div><b>${c.level}</b><span>Poziom</span></div><div><b>${fmt(c.deaths)}</b><span>Śmierci</span></div><div><b>${c.runes_memory < 1e6 ? fmt(c.runes_memory) : num(c.runes_memory / 1e6) + " mln"}</b><span>Pamięć run</span></div></div>
          ${attrPanel(st, curves)}</div>
        <div class="eq-groups">
          <div class="eq-group"><h4>Zbroja</h4><div class="eq-row">${slot(helm, "Głowa")}${slot(eqItem(eq.chest, "armor"), "Tułów")}${slot(eqItem(eq.arms, "armor"), "Ręce")}${slot(eqItem(eq.legs, "armor"), "Nogi")}</div></div>
          <div class="eq-group"><h4>Prawa ręka</h4><div class="eq-row">${w(eq.right_weapons || [], "Prawa")}</div></div>
          <div class="eq-group"><h4>Lewa ręka</h4><div class="eq-row">${w(eq.left_weapons || [], "Lewa")}</div></div>
          <div class="eq-group"><h4>Talizmany</h4><div class="eq-row">${(eq.talismans || []).map((e, i) => slot(eqItem(e, "talisman"), `Talizman ${i + 1}`)).join("")}</div></div>
          <div class="eq-group"><h4>Wielki run i czary</h4><div class="eq-row">${slot(eqItem(eq.great_rune, "goods"), "Wielki run")}${(eq.spells || []).filter(Boolean).map((e, i) => slot(eqItem(e, "goods"), `Czar ${i + 1}`, { active: eq.active_spell === i })).join("") || '<span class="view-sub" style="align-self:center">brak zapamiętanych czarów</span>'}</div></div>
          <div class="eq-group"><h4>Szybkie przedmioty i sakwa</h4><div class="eq-row wrap">${[...(eq.quick_items || []), ...(eq.pouch || [])].filter(Boolean).map((e, i) => slot(eqItem(e, "goods"), "Przedmiot", { active: eq.active_quick_item === i })).join("")}</div></div>
        </div></div>${visitedAreas(st)}</div>`;
    main.querySelectorAll("[data-eq]").forEach(b => b.onclick = () => { const [cat, id, raw, upgrade] = b.dataset.eq.split(":"), it = findItem(cat, +id);
      if (it) openItem(it, { eq: { id: raw ? +raw : null, upgrade: upgrade ? +upgrade : 0 } }); });
  }

  /* ---------------- kronika ---------------- */
  // postęp szczegółowy z backendu (progress_detail): bossowie obowiązkowi, łaski gra/DLC, skarby z map, zwiedzone krainy
  function progressEntries() {
    const pd = live.state?.progress_detail;
    if (!live.on || !pd) return "";
    const e = (g, txt) => `<div class="entry"><time>—</time><span class="glyph">${g}</span><span class="txt">${txt}</span></div>`;
    const of = x => `<em>${fmt(x.done)} z ${fmt(x.total)}</em>`;
    const lands = new Set((live.state.regions || []).map(r => r.region).filter(Boolean)).size;
    return [pd.bosses_required && e("♛", `Bossowie potrzebni do zakończenia gry: ${of(pd.bosses_required)}`),
      pd.graces && e("❦", `Łaski w podstawce: ${of(pd.graces.base)} · w DLC: ${of(pd.graces.dlc)}`),
      pd.map_treasures && e("❖", `Skarby zebrane z map: ${of(pd.map_treasures)}`),
      pd.quests && e("✦", `Ukończone questy: ${of({ done: pd.quests.base.done + pd.quests.dlc.done, total: pd.quests.base.total + pd.quests.dlc.total })}`),
      lands && e("◈", `Zwiedzone krainy: <em>${lands}</em>`)].filter(Boolean).join("");
  }
  function viewChronicle() {
    const entry = e => `<div class="entry ${e.kind}"><time>${e.t}</time><span class="glyph ${e.blood ? "blood" : ""}">${e.g}</span><span class="txt">${e.txt}</span>${e.sub ? `<span class="sub">${esc(e.sub)}</span>` : ""}</div>`;
    const head = `<div class="view-head"><div><div class="eyebrow">Zapisane w kamieniu</div><h1 class="title">Kronika</h1><div class="view-sub">Pisze się sama: każdy zapis gry dopisuje nowe wersy.</div></div></div>`;
    // tylko łaski z nazwą — techniczne (np. flaga 200, bez nazwy w grze) są w save'ie ustawione od startu
    const bl = bossList(), defeated = bl.filter(b => b.defeated).length, graces = W.graces.filter(g => g.name && isSet(g.flag, 60)).length;
    if (D.chronicleFailed) {
      main.innerHTML = `<div class="view">${head}<p class="note warn">Nie udało się wczytać kroniki z backendu: ${esc(D.chronicleFailed)}</p></div>`;
      return;
    }
    if (!D.chronicle.length) {
      main.innerHTML = `<div class="view">${head}<div class="book corners"><div class="page"><p class="chron-intro dropcap">Karty tej kroniki są jeszcze puste. Zmatowiały zwany <em style="color:var(--gold-hi);font-style:normal">${esc(D.character.name)}</em>
        dopiero je zapisze. Pierwsze wersy pojawią się, gdy gra zapisze postęp: nowa łaska, pokonany wróg, zdobyty przedmiot.</p>
        <p class="view-sub">Kronika liczy się od chwili, gdy backend pierwszy raz zobaczył tę postać.</p></div>
        <div class="page"><div class="day">Stan na dziś</div>
        <div class="entry"><time>—</time><span class="glyph">▲</span><span class="txt">Poziom <em>${D.character.level}</em></span></div>
        <div class="entry"><time>—</time><span class="glyph blood">☠</span><span class="txt">Śmierci: <em>${fmt(D.character.deaths)}</em></span></div>
        <div class="entry"><time>—</time><span class="glyph">⚔</span><span class="txt">Pokonani bossowie: <em>${defeated} z ${bl.length}</em></span></div>
        <div class="entry"><time>—</time><span class="glyph">❦</span><span class="txt">Odkryte miejsca łaski: <em>${graces} z ${W.graces.filter(g => g.name).length}</em></span></div>
        ${D.character.last_grace ? `<div class="entry"><time>—</time><span class="glyph">❦</span><span class="txt">Ostatnia łaska: <em>${esc(D.character.last_grace)}</em></span></div>` : ""}
        ${progressEntries()}</div></div></div>`;
      return;
    }
    const [today, ...older] = D.chronicle;
    const dayHead = d => `<div class="day">${d.day}</div>${d.summary ? `<p class="day-sum">${esc(d.summary)}</p>` : ""}`;
    main.innerHTML = `<div class="view">${head}<div class="book corners"><div class="page">
      <p class="chron-intro dropcap">Zmatowiały zwany <em style="color:var(--gold-hi);font-style:normal">${esc(D.character.name)}</em> zgasił już ${pl(defeated, "wielkiego wroga", "wielkich wrogów", "wielkich wrogów")}, odnalazł ${pl(graces, "miejsce łaski", "miejsca łaski", "miejsc łaski")} i padł ${pl(D.character.deaths, "raz", "razy", "razy")}, by za każdym razem powstać na nowo.</p>
      ${dayHead(today)}${today.entries.map(entry).join("")}</div>
      <div class="page">${older.map(d => `${dayHead(d)}${d.entries.map(entry).join("")}`).join("")}
      ${progressEntries() ? `<div class="day">Stan na dziś</div>${progressEntries()}` : ""}
      <div class="rule" style="margin-top:30px"></div>${D.daysMore ? '<button class="btn ghost" id="olderDays">Starsze dni</button>'
        : '<p class="view-sub" style="text-align:center">Kronika zaczyna się od pierwszego zapisu, który zobaczyła aplikacja.</p>'}</div></div></div>`;
    if ($("#olderDays")) $("#olderDays").onclick = async () => {
      const r = await api(`/api/days?${qs()}&limit=7&before=${D.daysMore}`).catch(e => banner("Kronika", "Nie udało się wczytać starszych dni: " + (e.message || e)));
      if (!r) return;
      D.chronicle.push(...r.days.map(dayModel));
      D.daysMore = r.more ? r.days.at(-1).date : null;
      viewChronicle();
    };
  }

  /* ---------------- podsumowanie sesji ---------------- */
  $("#sessionBtn").onclick = () => {
    const s = D.session;
    const empty = s && !s.bosses && !s.graces && !s.items && !s.deaths && !s.levels && !(s.highlights || []).length;
    $("#modalCard").innerHTML = !s || empty ? `<div class="eyebrow">Podsumowanie sesji</div><h2 class="title" style="font-size:29px;margin-top:8px">Brak sesji</h2>
        <p class="view-sub" style="margin-top:18px">Backend nie widział jeszcze zapisów tej postaci. Zagraj chwilę, sesja liczy się od pierwszego zapisu gry.</p><button class="btn ghost" id="closeSum">Zamknij</button>`
      : `<div class="eyebrow">${s.active === false ? "Ostatnia sesja" : s.active ? "Trwająca sesja" : "Koniec sesji"} · ${s.duration}</div><h2 class="title" style="font-size:31px;margin-top:8px">${s.active ? "Dzisiejsza wyprawa" : "Ostatnia wyprawa"}</h2>
      <div class="sum-grid"><div><b>${s.bosses}</b><span>Bossowie</span></div><div><b>${s.graces}</b><span>Łaski</span></div><div><b>${s.items}</b><span>Przedmioty</span></div>
        <div><b>${s.deaths}</b><span>Śmierci</span></div><div><b>+${s.levels}</b><span>Poziomy</span></div><div><b>${s.hours ?? s.duration.split(" ")[0]} h</b><span>W grze</span></div></div>
      <div class="sum-list">${s.highlights.length ? s.highlights.map(h => `<div class="reward"><span><span class="diamond on"></span>&nbsp;&nbsp;${esc(h)}</span><span></span></div>`).join("") : '<p class="view-sub" style="text-align:center">Spokojna sesja, bez nowych bossów i łask.</p>'}</div>
      <button class="btn ghost" id="closeSum">Zamknij</button>`;
    $("#modal").classList.add("open"); $("#closeSum").onclick = closeModal;
  };

  /* ---------------- zdarzenia na żywo ---------------- */
  function banner(title, sub) {
    $("#felledText").textContent = title; $("#felledSub").textContent = sub;
    const f = $("#felled"); f.classList.remove("show"); void f.offsetWidth; f.classList.add("show");
  }
  function connectEvents() {
    const es = new EventSource(API + "/api/events");
    es.addEventListener("portrait", e => {           // backend przerenderował głowę po zmianie hełmu/wyglądu
      const d = JSON.parse(e.data); portraitVer[d.file + ":" + d.slot] = d.version;
      stateCache.delete(d.file + ":" + d.slot);
      if (d.file === live.file && d.slot === live.slot) { topbar(); if (location.hash === "#character") render(); }
      document.querySelectorAll(`[data-doll="${d.file}:${d.slot}"] img.hp-render`).forEach(img => { img.src = headSrc(d.file, d.slot, { head: { id: d.head_id } }); });
    });
    es.addEventListener("save", async e => {
      const d = JSON.parse(e.data);
      if (d.slot == null) return;
      const mine = d.file === live.file && d.slot === live.slot;
      if (!mine && live.pinned) return;
      const before = new Set(bossList().filter(b => b.defeated).map(b => b.id)), beforeG = new Set(W.graces.filter(g => isSet(g.flag)).map(g => g.flag));
      if (!mine) { live.file = d.file; live.slot = d.slot; }
      await loadLive();
      const felled = bossList().filter(b => b.defeated && !before.has(b.id)), graces = mine ? W.graces.filter(g => isSet(g.flag) && !beforeG.has(g.flag)) : [];
      if (mine && felled.length) banner("Wróg pokonany", felled.map(b => b.name).join(" · "));
      else if (graces.length) banner("Odkryto łaskę", graces.map(g => g.name).join(" · "));
      topbar(); quietRender();
    });
    es.onerror = () => $(".nav-note").textContent = "backend: łączę ponownie…";
    es.addEventListener("hello", () => live.on && ($(".nav-note").textContent = `na żywo · ${D.save.file} · slot ${live.slot}`));
  }
  async function switchCharacter(file, slot) { live.file = file; live.slot = slot; live.pinned = true; closeDrawer(); await loadLive(); topbar(); render(); }

  const demo = document.createElement("button");
  demo.className = "session-btn"; demo.style.marginTop = "8px"; demo.textContent = "▶ Symuluj zapis gry";
  demo.onclick = () => { const b = bossList().find(x => !x.defeated && x.discovered && x.icon); if (!b) return;
    demoSet.add(b.flag); saveAgo = 0; banner("Wróg pokonany", b.name); quietRender(); };
  $(".nav-foot").insertBefore(demo, $(".nav-note"));

  // zmiana trybu spoilerów: otwarte szczegóły (boss, przedmiot…) mogły pokazywać to, co teraz ma być ukryte
  $("#spoilerToggle").onchange = e => { state.spoilers = e.target.checked; closeDrawer(); render(); };
  $("#mineToggle").onchange = e => setMine(e.target.checked);
  $("#fontToggle").checked = pref("font", "") === "plain";
  $("#fontToggle").onchange = e => setPlainFont(e.target.checked);
  syncMine();
  document.querySelectorAll("[data-game]").forEach(b => { b.classList.toggle("on", b.dataset.game === state.game); b.onclick = () => setGame(b.dataset.game); });
  $("#charSwitch").onclick = () => live.on && live.characters ? drawer(`<div class="eyebrow">Twoje save'y</div><div class="d-title" style="text-align:left">Postacie</div>
    ${live.characters.files.map(f => `<div class="d-section"><h4>${f.file === "co2" ? "Seamless Coop · ER0000.co2" : "Oficjalna gra · ER0000.sl2"}</h4>
      ${(f.characters || []).map(c => `<button class="reward char-row ${f.file === live.file && c.slot === live.slot ? "on" : ""}" data-file="${f.file}" data-slot="${c.slot}">
        <span class="char-row-main"><span class="char-row-doll" data-doll="${f.file}:${c.slot}"><span class="headp mini loading"></span></span>
          <span><span class="char-row-name">${esc(c.name)}</span><span class="char-row-sub" data-cls="${f.file}:${c.slot}"></span></span></span>
        <span>poziom ${c.level} · ${c.playtime_s < 3600 ? Math.round(c.playtime_s / 60) + " min" : Math.round(c.playtime_s / 3600) + " h"}</span></button>`).join("")}</div>`).join("")}
    <p class="view-sub" style="margin-top:18px">Domyślnie aplikacja sama przełącza się na postać, której save zmienił się ostatnio. Wybór ręczny ją przypina.</p>
    ${live.pinned ? `<button class="btn" id="autoFollow">Śledź automatycznie</button>` : ""}`,
    async () => { document.querySelectorAll(".char-row").forEach(b => b.onclick = () => switchCharacter(b.dataset.file, +b.dataset.slot));
      if ($("#autoFollow")) $("#autoFollow").onclick = async () => { live.pinned = false; const a = live.characters?.active; if (a) { live.file = a.file; live.slot = a.slot; }
        closeDrawer(); await loadLive(); topbar(); render(); };
      await itemsIndex();
      for (const el of document.querySelectorAll("[data-doll]")) {   // portrety dociągane w tle (stan każdej postaci z backendu)
        const [file, sl] = el.dataset.doll.split(":");
        charState(file, +sl).then(st => { if (!st || !el.isConnected) return; el.innerHTML = doll(st.equipment, "mini", file, +sl);
          const cl = document.querySelector(`[data-cls="${file}:${sl}"]`), a = st.character?.archetype?.name;
          if (cl && a) cl.textContent = CLASS_PL[a] || a; });
      } })
    : drawer(`<div class="eyebrow">Tryb demo</div><div class="d-title" style="text-align:left">Postacie</div><div class="rule"></div>
      <p class="view-sub">Uruchom backend (<code>python backend\\server.py</code>), żeby wybierać prawdziwe postacie z save'ów.</p>`);

  /* ---------------- router ---------------- */
  const VIEWS = { character: viewCharacter, map: viewMap, bosses: viewBosses, quests: viewQuests, items: viewItems, chronicle: viewChronicle };
  // Odświeżenie po zapisie gry bez „mrugania”: bez animacji wejścia, z zachowaniem przewinięcia list i paneli;
  // na mapie tylko znaczniki, liczniki i pozycja gracza (mapa i kafle zostają).
  const SCROLLERS = [".qlist", ".qdetail", ".layers-scroll", ".region-aside", ".cat-progress", ".drawer-body"];
  function quietRender() {
    const v = (location.hash || "#bosses").slice(1);
    if (v === "map" && bigMap) {
      // nowa mapa w „Moim postępie” (pierwsze zejście do podziemi) — przebuduj panel z zakładkami
      const tabs = [...document.querySelectorAll(".maptabs [data-m]")].map(b => b.dataset.m).join() || state.map;
      if (mapsFor(state.game).join() !== tabs) return viewMapKeep();
      applyArea(bigMap, true);                                       // obszar mapy mógł urosnąć (nowa łaska, fragment)
      buildLayers();
      const c = mapCounts();
      document.querySelectorAll(".layer[data-layer]").forEach(b => { const n = c[b.dataset.layer], el = b.querySelector(".cnt");
        if (n && el) el.textContent = layerCount(n); });
      const p = D.position;
      if (playerMarker && p && p.map === state.map) playerMarker.setLatLng(ll(bigMap, p.px, p.py));
      return;
    }
    const pos = { main: main.scrollTop, ...Object.fromEntries(SCROLLERS.map(sel => [sel, document.querySelector(sel)?.scrollTop || 0])) };
    document.body.classList.add("quiet");
    Promise.resolve(render(true)).then(() => {
      main.scrollTop = pos.main;
      for (const sel of SCROLLERS) { const el = document.querySelector(sel); if (el) el.scrollTop = pos[sel]; }
      requestAnimationFrame(() => requestAnimationFrame(() => document.body.classList.remove("quiet")));
    });
  }
  function render(keepMap) {
    const v = (location.hash || "#bosses").slice(1);
    document.querySelectorAll(".nav a").forEach(a => a.classList.toggle("active", a.dataset.view === v));
    if (v !== "map" && bigMap) { bigMap.remove(); bigMap = null; }
    if (v !== "map") { state.mapQuery = ""; state.mapExact = null; state.mapPeek = false; state.mapDrops = null; state.mapFocus = null; }
    if (v === "map" && keepMap && bigMap) { viewMapKeep(); return; }
    return (VIEWS[v] || viewBosses)();
  }
  window.addEventListener("hashchange", () => { closeDrawer();
    Promise.resolve(render()).then(() => { const f = pendingAfter; pendingAfter = null; if (f) f(); }); });
  window.__er = { W, selectSpot, openBoss, bossList };   // pomoc przy testach makiety
  (async () => {
    await loadWorld();
    await itemsIndex();                          // nazwy przedmiotów do linków w questach i nagrodach
    await sourcesIndex();                        // skąd zdobyć przedmioty (kupcy, wrogowie, bossowie, zdarzenia)
    try {
      await api("/api/health", 1500);
      $(".nav-note").textContent = "łączenie z backendem…";
      await loadLive();
      demo.style.display = "none";
      connectEvents();
    } catch (err) {
      console.info("Backend niedostępny, tryb demo.", err?.message);
      $(".nav-note").textContent = "makieta · stan przykładowy (backend wyłączony)";
    }
    topbar(); render();
  })();
})();
