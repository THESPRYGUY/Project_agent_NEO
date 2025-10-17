from __future__ import annotations

import socket
import threading
import time
from urllib import request

from wsgiref.simple_server import make_server

from neo_agent.intake_app import create_app


def _reserve_port(host: str) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return sock.getsockname()[1]


def test_persona_tab_buttons_are_not_submit(tmp_path) -> None:
    host = "127.0.0.1"
    port = _reserve_port(host)

    app = create_app(base_dir=tmp_path)
    httpd = make_server(host, port, app.wsgi_app)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        deadline = time.time() + 5
        while time.time() < deadline:
            try:
                with socket.create_connection((host, port), timeout=0.2):
                    break
            except OSError:
                time.sleep(0.05)
        with request.urlopen(f"http://{host}:{port}/", timeout=5) as response:
            html = response.read().decode("utf-8")
        assert 'id="persona-tab-operator"' in html and 'type="button"' in html
        assert 'id="persona-tab-agent"' in html and 'type="button"' in html
    finally:
        httpd.shutdown()
        thread.join(timeout=5)
        httpd.server_close()

