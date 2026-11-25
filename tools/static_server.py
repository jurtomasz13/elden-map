"""Serwer plików strony (tylko 127.0.0.1) z nagłówkiem Cache-Control: no-cache — przeglądarka zawsze sprawdza,
czy plik się zmienił (po aktualizacji aplikacji nie zostaje stara wersja app.js / styles.css).

    python tools/static_server.py [port=5180]      # serwuje katalog projektu; strona: /mockup/
"""
import functools
import http.server
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        p = self.path.split("?")[0]
        if not p.startswith("/assets/map/") and not p.startswith("/assets/icons/"):   # kafle i ikony mogą zostać w cache
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def log_message(self, fmt, *args):
        pass


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5180
    handler = functools.partial(NoCacheHandler, directory=ROOT)
    with http.server.ThreadingHTTPServer(("127.0.0.1", port), handler) as srv:
        srv.serve_forever()


if __name__ == "__main__":
    main()
