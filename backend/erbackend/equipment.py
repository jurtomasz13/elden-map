"""Założony ekwipunek postaci (to, co widać na ekranie wczytywania) + klasa/dar startowy z profilu.

Pola slotu (offsety od końca GaItem map = `ge`, kolejność wg er-save-manager, zweryfikowane na 7 postaciach):
    ge+0x280  equipped_items_equip_index  22 × u32  (indeksy w ekwipunku)
    ge+0x2D8  active_weapon_slots_and_arm_style 7 × u32: [0] arm_style, [1] aktywny slot lewej ręki (0–2),
              [2] aktywny slot prawej ręki (0–2), reszta ?
    ge+0x2F4  equipped_items_item_id      22 × u32  (ID bez prefiksu typu; pusty = 0xFFFFFFFF)
    ge+0x34C  equipped_items_gaitem_handle 22 × u32
      kolejność 22 slotów: L1, P1, L2, P2, L3, P3, strzały1, bełty1, strzały2, bełty2, ?, ?,
                           głowa, tors, ręce, nogi, ?, talizman1..4, ?
    ge+0x93B4 equipped_spells  14 × (u32 id czaru, u32 ?) + u32 aktywny  (0x74)
    ge+0x9428 equipped_items   10 × (u32 handle, u32 equip_index) szybkie przedmioty, u32 aktywny,
                               6 × (handle, idx) sakwa, (handle, idx) wielka runa              (0x8C)
    za listą pocisków +0x9C: equipped_physics 2 × u32 item_id (0x4… = goods: łzy krystaliczne) + u32 ?
"""
from __future__ import annotations

import struct

from .inventory import AFFINITIES

EQUIP_INDEX = 0x280
ARM_STYLE = 0x2D8
ITEM_IDS = 0x2F4
HANDLES = 0x34C
SPELLS = 0x93B4
EQUIPPED_ITEMS = 0x9428
PHYSICS_AFTER_PROJECTILES = 0x9C

EMPTY = (0, 0xFFFFFFFF)
UNARMED = 110000
BARE_ARMOR = {10000, 10100, 10200, 10300, 100000, 100100, 100200, 100300}

# CharaInitParam 3000+n; potwierdzone: 0 (Ser Davick: zbroja Vagabond Knight), 1 (chuj: 2 bułaty + tarcza),
# 5 (postać 'prophet'), 9 (boink: bez zbroi); reszta wg kolejności w menu tworzenia postaci.
ARCHETYPES = ["vagabond", "warrior", "hero", "bandit", "astrologer", "prophet", "confessor", "samurai",
              "prisoner", "wretch"]
# 0 = brak (chuj: brak talizmanu), 1 = Crimson Amber Medallion (Ser Davick: talizman 1000); reszta wg menu.
STARTING_GIFTS = ["none", "crimson_amber_medallion", "lands_between_rune", "golden_seed", "fanged_imp_ashes",
                  "cracked_pot", "stonesword_key", "bewitching_branch", "boiled_prawn", "shabriris_woe"]
# 1 = typ A na 6 z 7 postaci użytkownika — prawdopodobne, niezweryfikowane w grze
BODY_TYPES = {0: "B", 1: "A"}


def _weapon(item_id: int, handle: int, gaitems: dict, weapon_ash: dict) -> dict | None:
    if item_id in EMPTY or item_id == UNARMED:
        return None
    rest = item_id % 10000
    aff = rest // 100
    ash = None
    ah = weapon_ash.get(handle)
    if ah and ah in gaitems:
        ash = gaitems[ah] & 0x0FFFFFFF
    return {"id": item_id, "base_id": item_id - rest, "upgrade": rest % 100,
            "affinity": AFFINITIES[aff] if aff < len(AFFINITIES) else aff, "ash_id": ash}


def _plain(item_id: int, skip=()) -> dict | None:
    if item_id in EMPTY:
        return None
    item_id &= 0x0FFFFFFF
    if item_id in skip:
        return None
    return {"id": item_id}


def _goods_handle(h: int) -> dict | None:
    if h in EMPTY:
        return None
    return {"id": h & 0x0FFFFFFF}


def parse(s: bytes, ge: int, projectiles_end: int, gaitems: dict, weapon_ash: dict) -> dict:
    ids = struct.unpack_from("<22I", s, ge + ITEM_IDS)
    hs = struct.unpack_from("<22I", s, ge + HANDLES)
    arm = struct.unpack_from("<3I", s, ge + ARM_STYLE)
    left = [_weapon(ids[i], hs[i], gaitems, weapon_ash) for i in (0, 2, 4)]
    right = [_weapon(ids[i], hs[i], gaitems, weapon_ash) for i in (1, 3, 5)]
    ammo = []
    for i, kind in zip((6, 7, 8, 9), ("arrow", "bolt", "arrow", "bolt")):
        w = _plain(ids[i])
        ammo.append({**w, "kind": kind} if w else None)
    sp = struct.unpack_from("<29I", s, ge + SPELLS)
    eq = struct.unpack_from("<35I", s, ge + EQUIPPED_ITEMS)
    phys = struct.unpack_from("<2I", s, projectiles_end + PHYSICS_AFTER_PROJECTILES)
    return {
        "head": _plain(ids[12], BARE_ARMOR), "chest": _plain(ids[13], BARE_ARMOR),
        "arms": _plain(ids[14], BARE_ARMOR), "legs": _plain(ids[15], BARE_ARMOR),
        "right_weapons": right, "left_weapons": left,
        "active_weapon": {"left": arm[1] if arm[1] < 3 else None, "right": arm[2] if arm[2] < 3 else None,
                          "arm_style": arm[0]},
        "talismans": [_plain(ids[i]) for i in (17, 18, 19, 20)],
        "ammo": ammo,
        "quick_items": [_goods_handle(eq[2 * i]) for i in range(10)],
        "active_quick_item": eq[20] if eq[20] < 10 else None,
        "pouch": [_goods_handle(eq[21 + 2 * i]) for i in range(6)],
        "great_rune": _goods_handle(eq[33]),
        "spells": [_plain(sp[2 * i]) for i in range(14)],
        "active_spell": sp[28] if sp[28] < 14 else None,
        "physick": [_plain(t) for t in phys],
    }


def profile_fields(profile: bytes, summary_off: int) -> dict:
    body, arch, gift = profile[summary_off + 0x242], profile[summary_off + 0x243], profile[summary_off + 0x244]
    return {
        "body_type": {"id": body, "name": BODY_TYPES.get(body)},
        "archetype": {"id": arch, "name": ARCHETYPES[arch] if arch < len(ARCHETYPES) else None},
        "starting_gift": {"id": gift, "name": STARTING_GIFTS[gift] if gift < len(STARTING_GIFTS) else None},
    }
