#!/usr/bin/env python3
"""Sprint-6 dual smoke: OFF and ON overlays with artifacts.

Writes artifacts to:
  _artifacts/sprint6/off/{repo.zip, INTEGRITY_REPORT.json, build.json}
  _artifacts/sprint6/on/{repo.zip, INTEGRITY_REPORT.json, build.json}
"""

from __future__ import annotations

import io
import json
import os
import shutil
import zipfile
from pathlib import Path
import sys

def _ensure_import_path(root: Path) -> None:
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    src = root / 'src'
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


def _ensure_paths() -> tuple[Path, Path, Path]:
    root = Path.cwd()
    off = root / "_artifacts" / "sprint6" / "off"
    on = root / "_artifacts" / "sprint6" / "on"
    for p in (off, on):
        p.mkdir(parents=True, exist_ok=True)
    return root, off, on


def _wsgi_call(app, method: str, path: str, body: dict | None = None):
    raw = json.dumps(body or {}).encode("utf-8")
    env = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": "",
        "SERVER_NAME": "smoketest",
        "SERVER_PORT": "80",
        "wsgi.version": (1, 0),
        "wsgi.url_scheme": "http",
        "wsgi.input": io.BytesIO(raw),
        "CONTENT_LENGTH": str(len(raw)),
    }
    status_headers = []
    def start_response(status, headers):
        status_headers.append((status, headers))
    resp = b"".join(app.wsgi_app(env, start_response))
    return status_headers[0][0], dict(status_headers[0][1]), resp


def _run_one(flag_on: bool, artifacts_dir: Path, profile: dict) -> dict:
    from neo_agent.intake_app import create_app
    from neo_build.contracts import CANONICAL_PACK_FILENAMES

    # Isolated out root
    work_root = Path('.pytest-tmp/sprint6').resolve()
    work_root.mkdir(parents=True, exist_ok=True)
    os.environ['NEO_REPO_OUTDIR'] = str(work_root)
    os.environ['NEO_APPLY_OVERLAYS'] = 'true' if flag_on else 'false'

    app = create_app(base_dir=work_root)

    st, _, body = _wsgi_call(app, 'POST', '/save', profile)
    assert st == '200 OK', body
    st, _, body = _wsgi_call(app, 'POST', '/build', {})
    assert st == '200 OK', body
    res = json.loads(body.decode('utf-8'))

    outdir = Path(res['outdir']).resolve()
    # Zip repo
    with zipfile.ZipFile(artifacts_dir / 'repo.zip', 'w', zipfile.ZIP_DEFLATED) as zf:
        for p in outdir.rglob('*'):
            zf.write(p, arcname=str(p.relative_to(outdir)))
    # Copy integrity
    shutil.copy2(outdir / 'INTEGRITY_REPORT.json', artifacts_dir / 'INTEGRITY_REPORT.json')
    # Build summary json
    file_count = sum(1 for n in CANONICAL_PACK_FILENAMES if (outdir / n).exists())
    build_json = {
        'outdir': str(outdir),
        'file_count': file_count,
        'parity': res.get('parity', {}),
        'integrity_errors': res.get('integrity_errors', []),
        'overlays_applied': bool(res.get('overlays_applied')),
    }
    (artifacts_dir / 'build.json').write_text(json.dumps(build_json, indent=2), encoding='utf-8')
    return build_json


def main() -> int:
    root, off_dir, on_dir = _ensure_paths()
    fixture = json.loads((root / 'fixtures' / 'sample_profile.json').read_text(encoding='utf-8'))

    _ensure_import_path(root)
    off = _run_one(False, off_dir, fixture)
    on = _run_one(True, on_dir, fixture)

    # Expectations
    assert off['file_count'] == 20 and len(off['integrity_errors']) == 0 and all(off['parity'].values())
    assert on['file_count'] == 20 and len(on['integrity_errors']) == 0 and all(on['parity'].values()) and on['overlays_applied'] is True

    print('SPRINT6 SMOKE OFF OK | files=20 | parity=ALL_TRUE | integrity_errors=0')
    print('SPRINT6 SMOKE ON  OK | files=20 | parity=ALL_TRUE | integrity_errors=0 | overlays_applied=true')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
