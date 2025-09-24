from pathlib import Path

import pytest

import neo_agent.pack_loader as pack_loader


@pytest.fixture()
def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def test_all_packs_load_and_validate(project_root: Path) -> None:
    json_files = pack_loader.discover_pack_files(project_root)
    assert json_files, "Expected to discover pack JSON files"

    for path in json_files:
        result = pack_loader.validate_pack(path)
        assert not result.missing_keys, f"{path} is missing required keys: {result.missing_keys}"
        assert isinstance(result.payload, dict)


def test_topological_order_matches_node_count() -> None:
    nodes = ["a", "b", "c"]
    edges = [("a", "b"), ("b", "c")]
    order = pack_loader.topological_order(nodes, edges)
    assert order == ["a", "b", "c"]


def test_cli_reports_cycle(project_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = pack_loader.main([str(project_root)])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "quality_feedback" in output
    assert "Warning: Workflow graph contains a cycle involving" in output

