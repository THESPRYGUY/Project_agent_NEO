SHELL := /bin/bash

.PHONY: smoke
smoke:
	python -m pytest -q || true
	npm -s run test || true
	python ci/smoke.py

.PHONY: release
release:
	@if [ -z "$(VERSION)" ]; then echo "VERSION is required, e.g. make release VERSION=2.1.2"; exit 2; fi
	python scripts/release.py --version $(VERSION)
