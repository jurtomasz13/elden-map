"""Automatyczne portrety postaci: po zapisie gry, gdy zmieniła się zbroja albo wygląd (blok FACE), w tle uruchamiamy
tools/extract/render_character.py dla tego slotu (portret głowy i cała postać) i publikujemy zdarzenie SSE 'portrait'.

Render czyta pliki gry i save (tylko odczyt) i zapisuje PNG do assets/renders/ (lokalnie). Podpis ostatniego renderu
(id czterech części zbroi + skrót bloku FACE + wersja renderera) trzymamy w backend/var/portraits.json, żeby nie renderować w kółko,
a po zmianie renderera (nowa wersja aplikacji) odświeżyć portrety przy starcie.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import queue
import subprocess
import sys
import threading

log = logging.getLogger("erbackend.portraits")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCRIPT = os.path.join(ROOT, "tools", "extract", "render_character.py")
RENDERS = os.path.join(ROOT, "assets", "renders")
STATE = os.path.join(ROOT, "backend", "var", "portraits.json")


class Portraits:
    def __init__(self, service, python: str = sys.executable):
        self.service = service
        self.python = python
        self.enabled = os.path.exists(SCRIPT)
        self.version = self._renderer_version() if self.enabled else "-"
        try:
            self.done: dict[str, str] = json.load(open(STATE, encoding="utf-8"))
        except (OSError, ValueError):
            self.done = {}
        self.q: queue.Queue = queue.Queue()
        self.pending: set[str] = set()
        self.lock = threading.Lock()
        self._thread = threading.Thread(target=self._run, name="portraits", daemon=True)
        self._thread.start()

    def _renderer_version(self) -> str:
        """Version of the rendering code, from the render script itself (one place: export_model.renderer_version)."""
        r = subprocess.run([self.python, "-I", "-X", "utf8", SCRIPT, "--version"], cwd=ROOT, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=60)
        if r.returncode != 0:
            raise RuntimeError(f"render_character.py --version: {(r.stderr or r.stdout)[-300:]}")
        return r.stdout.strip()

    @staticmethod
    def signature(sf, slot: int, version: str = "-") -> tuple[str, int | None]:
        eq = sf.slot(slot).equipment or {}
        head = (eq.get("head") or {}).get("id")
        # the whole-figure render (char_<file>_<slot>_full.png) changes with any armour piece
        armour = "/".join(str((eq.get(k) or {}).get("id")) for k in ("head", "chest", "arms", "legs"))
        e = sf.entries[slot]
        raw = sf.data[e.offset:e.offset + e.size]
        k = raw.find(b"FACE")
        face = hashlib.md5(raw[k:k + 0x120]).hexdigest()[:12] if k >= 0 else "-"
        return f"{armour}:{face}:{version}", head

    def check(self, kind: str, slot: int, sf) -> None:
        """Wołane przez serwis po zmianie slotu (i przy starcie dla wszystkich postaci)."""
        if not self.enabled:
            return
        try:
            sig, head = self.signature(sf, slot, self.version)
        except Exception as e:                      # zepsuty slot nie może zatrzymać watchera
            log.debug("portret %s:%s — brak podpisu: %s", kind, slot, e)
            return
        key = f"{kind}:{slot}"
        pngs = [os.path.join(RENDERS, f"char_{kind}_{slot}{suffix}.png") for suffix in ("", "_full")]
        if self.done.get(key) == sig and all(os.path.exists(p) for p in pngs):
            return
        with self.lock:
            if key in self.pending:
                return
            self.pending.add(key)
        self.q.put((kind, slot, sig, head))

    def scan_all(self) -> None:
        for kind, sf in list(self.service.saves.items()):
            for i in sf.active_slots:
                self.check(kind, i, sf)

    def _run(self):
        while True:
            kind, slot, sig, head = self.q.get()
            key = f"{kind}:{slot}"
            try:
                r = subprocess.run([self.python, "-I", "-X", "utf8", SCRIPT, kind, str(slot)], cwd=ROOT,
                                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
                if r.returncode == 0:
                    self.done[key] = sig
                    os.makedirs(os.path.dirname(STATE), exist_ok=True)
                    with open(STATE, "w", encoding="utf-8") as f:
                        json.dump(self.done, f, indent=1)
                    log.info("portret %s odświeżony (hełm %s)", key, head)
                    self.service.publish("portrait", {"file": kind, "slot": slot, "head_id": head, "version": sig})
                else:
                    log.warning("portret %s: render nie powiódł się: %s", key, (r.stderr or r.stdout)[-400:])
            except Exception as e:
                log.warning("portret %s: %s", key, e)
            finally:
                with self.lock:
                    self.pending.discard(key)
