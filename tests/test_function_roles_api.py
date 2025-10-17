from __future__ import annotations

import json
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


def _wait_for_server(host: str, port: int, timeout: float = 5.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.05)
    raise TimeoutError(f"Server at {host}:{port} did not become ready in time")


def test_function_roles_api_scoped(tmp_path) -> None:
    host = "127.0.0.1"
    port = _reserve_port(host)

    app = create_app(base_dir=tmp_path)
    httpd = make_server(host, port, app.wsgi_app)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        _wait_for_server(host, port)
        url = f"http://{host}:{port}/api/function_roles?fn=Finance"
        with request.urlopen(url, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
        assert data.get("status") == "ok"
        items = data.get("items") or []
        assert isinstance(items, list)
        assert any(isinstance(r.get("code"), str) and r.get("code") for r in items)
    finally:
        httpd.shutdown()
        thread.join(timeout=5)
        httpd.server_close()

