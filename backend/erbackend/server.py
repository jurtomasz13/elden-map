"""Serwer HTTP (ThreadingHTTPServer) z API JSON i Server-Sent Events. Tylko 127.0.0.1."""
from __future__ import annotations

import datetime as dt
import json
import os
import logging
import queue
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from . import __version__
from .gamedata import KINDS
from .savefile import FILE_KINDS, SaveError
from .service import Service, now_iso

log = logging.getLogger("erbackend.http")

LOCAL_ORIGIN = re.compile(r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$")
LOCAL_HOST = re.compile(r"^(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$")
SSE_KEEPALIVE = 15.0


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def _limit_param(qs: dict, default: int, hi: int) -> int:
    limit = _int_param(qs, "limit")
    limit = default if limit is None else limit
    if not 1 <= limit <= hi:
        raise ApiError(400, f"parametr 'limit' musi być w zakresie 1–{hi}")
    return limit


def _int_param(qs: dict, name: str) -> int | None:
    v = qs.get(name, [None])[0]
    if v in (None, ""):
        return None
    try:
        return int(v)
    except ValueError:
        raise ApiError(400, f"parametr '{name}' musi być liczbą")


def _file_param(qs: dict) -> str | None:
    v = qs.get("file", [None])[0]
    if v in (None, ""):
        return None
    v = v.lower().lstrip(".")
    if v not in FILE_KINDS:
        raise ApiError(400, "parametr 'file' musi być 'sl2' albo 'co2'")
    return v


class Handler(BaseHTTPRequestHandler):
    server_version = f"elden-map-backend/{__version__}"
    protocol_version = "HTTP/1.1"
    service: Service  # ustawiane w make_server

    def log_message(self, fmt, *args):
        log.debug("%s %s", self.address_string(), fmt % args)

    # --- pomocnicze --------------------------------------------------------------------------
    def _cors(self):
        origin = self.headers.get("Origin")
        if origin and LOCAL_ORIGIN.match(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")

    def _json(self, status: int, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self._cors()
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _host_ok(self) -> bool:
        # ochrona przed DNS rebinding: akceptujemy tylko lokalne nazwy hosta
        host = self.headers.get("Host", "")
        return bool(LOCAL_HOST.match(host))

    # --- metody HTTP -------------------------------------------------------------------------
    def do_OPTIONS(self):
        self.send_response(HTTPStatus.NO_CONTENT)
        self._cors()
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Last-Event-ID")
        self.send_header("Access-Control-Max-Age", "600")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        if not self._host_ok():
            return self._json(403, {"error": "dozwolony tylko dostęp lokalny (Host: localhost/127.0.0.1)"})
        url = urlsplit(self.path)
        qs = parse_qs(url.query)
        path = url.path.rstrip("/") or "/"
        try:
            if path == "/api/events":
                return self._sse()
            if path in ("/", "/api", "/api/health"):
                return self._json(200, self._health())
            if path == "/api/characters":
                return self._json(200, self.service.characters())
            if path == "/api/state":
                secs = [x for x in ",".join(qs.get("sections", [])).split(",") if x] or None
                kinds = [x for x in ",".join(qs.get("item_kind", [])).split(",") if x] or None
                return self._json(200, self.service.state(_file_param(qs), _int_param(qs, "slot"), secs, kinds))
            if path == "/api/flags":
                raw = ",".join(qs.get("ids", []))
                try:
                    ids = [int(x) for x in raw.split(",") if x.strip()]
                except ValueError:
                    raise ApiError(400, "parametr 'ids' to lista liczb oddzielonych przecinkami")
                if not ids or len(ids) > 1000:
                    raise ApiError(400, "podaj od 1 do 1000 ID flag w parametrze 'ids'")
                return self._json(200, self.service.flags(ids, _file_param(qs), _int_param(qs, "slot")))
            if path == "/api/chronicle":
                limit = _limit_param(qs, 100, 1000)
                kinds = [k for k in ",".join(qs.get("kind", [])).split(",") if k] or None
                return self._json(200, self.service.chronicle(_file_param(qs), _int_param(qs, "slot"), limit,
                                                              _int_param(qs, "before_id"), kinds))
            if path == "/api/deaths":
                return self._json(200, self.service.deaths(_file_param(qs), _int_param(qs, "slot"),
                                                           _int_param(qs, "limit")))
            if path == "/api/days":
                limit = _limit_param(qs, 7, 60)
                before = (qs.get("before") or [None])[0]
                try:
                    before = dt.date.fromisoformat(before) if before else None
                except ValueError:
                    raise ApiError(400, "parametr 'before' to data RRRR-MM-DD")
                return self._json(200, self.service.days(_file_param(qs), _int_param(qs, "slot"), limit, before))
            if path == "/api/session":
                return self._json(200, self.service.session(_file_param(qs), _int_param(qs, "slot")))
            m = re.fullmatch(r"/api/data/(\w+)", path)
            if m and m.group(1) in KINDS:
                return self._json(200, self.service.gamedata.sets[m.group(1)])
            raise ApiError(404, f"nieznany endpoint {url.path}")
        except ApiError as e:
            return self._json(e.status, {"error": str(e)})
        except LookupError as e:
            return self._json(404, {"error": str(e.args[0]) if e.args else str(e)})
        except SaveError as e:
            return self._json(503, {"error": f"błąd odczytu save'a: {e}"})
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _health(self) -> dict:
        s = self.service
        return {"ok": True, "version": __version__, "save_dir": s.save_dir, "save_dirs": s.save_dirs, "time": now_iso(),
                "files": {k: {"loaded": k in s.saves, "error": s.errors.get(k)} for k in FILE_KINDS},
                "active": s.active,
                "history_db": s.history.path,
                "endpoints": ["/api/characters", "/api/state?file=sl2|co2&slot=N", "/api/events",
                              "/api/chronicle?file=&slot=&limit=&before_id=&kind=", "/api/deaths?file=&slot=",
                              "/api/session?file=&slot=", "/api/days?file=&slot=&limit=&before=RRRR-MM-DD",
                              "/api/flags?ids=1,2&file=&slot=",
                              "/api/data/{bosses|graces|items|quests}"]}

    # --- Server-Sent Events ------------------------------------------------------------------
    def _sse(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self._cors()
        self.end_headers()
        self.close_connection = True
        q = self.service.subscribe()
        try:
            self._send_event(0, "hello", {"time": now_iso(), "active": self.service.active,
                                          "save_dir": self.service.save_dir})
            while not self.server.stopping:
                try:
                    eid, event, data = q.get(timeout=SSE_KEEPALIVE)
                except queue.Empty:
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
                    continue
                self._send_event(eid, event, data)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            pass
        finally:
            self.service.unsubscribe(q)

    def _send_event(self, eid: int, event: str, data: dict):
        payload = json.dumps(data, ensure_ascii=False)
        msg = f"id: {eid}\nevent: {event}\nretry: 3000\ndata: {payload}\n\n"
        self.wfile.write(msg.encode("utf-8"))
        self.wfile.flush()


class Server(ThreadingHTTPServer):
    daemon_threads = True
    # Linux/macOS: po zamknięciu otwarte połączenia SSE zostają w TIME_WAIT (~60 s) i bez SO_REUSEADDR ponowne
    # uruchomienie kończy się „Address already in use”. Na Windows SO_REUSEADDR pozwoliłby dwóm procesom
    # nasłuchiwać na tym samym porcie, więc tam zostaje wyłączone.
    allow_reuse_address = os.name != "nt"
    stopping = False


def make_server(service: Service, host: str = "127.0.0.1", port: int = 8765) -> Server:
    handler = type("BoundHandler", (Handler,), {"service": service})
    return Server((host, port), handler)
