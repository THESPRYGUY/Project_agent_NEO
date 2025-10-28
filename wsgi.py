"""Gunicorn entrypoint for Project NEO intake service.

Exposes a WSGI application callable named ``app`` that wraps the
Project NEO intake application's ``wsgi_app``. Gunicorn command:

    gunicorn -w 2 -b 0.0.0.0:5000 wsgi:app
"""

from __future__ import annotations

import os

# Ensure ``src`` is visible when running from a container without installation
_here = os.path.abspath(os.path.dirname(__file__))
src_path = os.path.join(_here, "src")
if os.path.isdir(src_path) and src_path not in os.sys.path:
    os.sys.path.insert(0, src_path)

from neo_agent.intake_app import create_app  # type: ignore  # noqa: E402

# Gunicorn expects a WSGI callable. IntakeApplication provides ``wsgi_app``.
app = create_app().wsgi_app

