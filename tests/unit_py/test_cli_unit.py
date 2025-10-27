import argparse
from pathlib import Path
import sys
import types
import pytest

pytestmark = pytest.mark.unit


def _ensure_import():
    root = Path.cwd()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    src = root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


def test_load_configuration_default():
    _ensure_import()
    from neo_agent import cli
    cfg = cli.load_configuration(None)
    assert cfg.name and cfg.version


def test_load_configuration_missing_file(tmp_path: Path):
    _ensure_import()
    from neo_agent import cli
    with pytest.raises(FileNotFoundError):
        cli.load_configuration(tmp_path / "nope.json")


def test_main_runs_default_handler(monkeypatch):
    _ensure_import()
    import neo_agent.cli as cli

    # Fake runtime to avoid heavy behavior
    class FakeRuntime:
        def __init__(self, cfg):
            self.cfg = cfg
        def initialize(self):
            return None
        def dispatch(self, payload):
            return {"ok": True}

    monkeypatch.setattr(cli, "AgentRuntime", FakeRuntime)
    rc = cli.main([])
    assert rc == 0


def test_serve_command(monkeypatch):
    _ensure_import()
    import neo_agent.cli as cli

    class FakeApp:
        def __init__(self):
            self.called = False
        def serve(self, host=None, port=None):
            self.called = True

    fake_app = FakeApp()
    import neo_agent.intake_app as intake_mod
    monkeypatch.setattr(intake_mod, "create_app", lambda: fake_app)
    ns = argparse.Namespace(host="127.0.0.1", port=0)
    rc = cli._serve_command(ns)
    assert rc == 0
