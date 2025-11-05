import os

import pytest

from neo_build.scaffolder import get_contract_mode

pytestmark = pytest.mark.unit


def test_mode_explicit_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setenv("NEO_CONTRACT_MODE", "full")
    assert get_contract_mode() == "full"
    monkeypatch.setenv("NEO_CONTRACT_MODE", "preview")
    assert get_contract_mode() == "preview"


def test_mode_ci_detection(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NEO_CONTRACT_MODE", raising=False)
    monkeypatch.setenv("CI", "1")
    assert get_contract_mode() == "preview"
    monkeypatch.setenv("CI", "")
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    assert get_contract_mode() == "preview"


def test_mode_local_default_is_full(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NEO_CONTRACT_MODE", raising=False)
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    assert get_contract_mode() == "full"
