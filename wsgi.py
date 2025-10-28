"""Gunicorn entrypoint for Project NEO intake service.

Exposes a WSGI application callable named ``app`` that wraps the
Project NEO intake application's ``wsgi_app``. Gunicorn command:

    gunicorn -w 2 -b 0.0.0.0:5000 wsgi:app
"""

from __future__ import annotations

import os

# Ensure repository root is visible on sys.path (so `src` can be imported)
_here = os.path.abspath(os.path.dirname(__file__))
if _here not in os.sys.path:
    os.sys.path.insert(0, _here)

from src.neo_agent.intake_app import create_app  # type: ignore  # noqa: E402

# Expose the application object; IntakeApplication implements __call__ as WSGI.
app = create_app()
