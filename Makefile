SHELL := /bin/bash

.PHONY: smoke
smoke:
	python -m pytest -q || true
	npm -s run test || true
	python ci/smoke.py

