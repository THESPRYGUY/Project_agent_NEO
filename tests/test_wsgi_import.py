from __future__ import annotations

def test_wsgi_import_and_callable():
    import importlib

    mod = importlib.import_module("wsgi")
    assert hasattr(mod, "app")
    # WSGI callable must be callable(environ, start_response)
    # Our exported app is neo_agent.intake_app.IntakeApplication.wsgi_app
    assert callable(mod.app)

