"""Token-protected loopback dashboard. No HTTP route can change hardware."""
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import threading
from urllib.parse import urlsplit
import webbrowser


def make_server(manager, port=0):
    token = secrets.token_urlsafe(32)
    html = (Path(__file__).parent / 'dashboard.html').read_bytes()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass

        def do_GET(self):
            host = f'127.0.0.1:{self.server.server_port}'
            if self.headers.get('Host') != host:
                self.send_error(403); return
            origin = self.headers.get('Origin')
            if origin and origin != 'http://' + host:
                self.send_error(403); return
            path = urlsplit(self.path).path
            if path == '/': body, kind = html, 'text/html; charset=utf-8'
            else:
                if not hmac.compare_digest(self.headers.get('X-GUPPI-Token', ''), token):
                    self.send_error(403); return
                try:
                    routes = {'/api/state': lambda: {'state': manager.get_state(), 'history': manager.history(120)},
                              '/api/inventory': manager.inventory, '/api/profiles': manager.profiles,
                              '/api/capabilities': manager.capabilities}
                    if path not in routes: self.send_error(404); return
                    body = json.dumps(routes[path](), ensure_ascii=False, allow_nan=False).encode('utf-8')
                    kind = 'application/json; charset=utf-8'
                except Exception:
                    self.send_error(503, 'Hardware data temporarily unavailable'); return
            self.send_response(200)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers(); self.wfile.write(body)

    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.daemon_threads = True
    return server, 'http://127.0.0.1:' + str(server.server_port) + '/#' + token


def serve(manager, port=0, open_browser=False):
    server, url = make_server(manager, port)
    stop = threading.Event()
    def sampler():
        while not stop.is_set():
            try: manager.get_state(fresh=True)
            except Exception: pass
            stop.wait(5)
    worker = threading.Thread(target=sampler, daemon=True); worker.start()
    print('GUPPI Hardware Manager:', url, flush=True)
    print('Local view; Captain changes through CLI. Ctrl+C stops the view.', flush=True)
    if open_browser: webbrowser.open(url)
    try: server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt: pass
    finally:
        stop.set(); server.server_close(); worker.join(timeout=15)
