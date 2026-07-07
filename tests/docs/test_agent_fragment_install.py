import json
from pathlib import Path

from kosha.cli import main


def test_agent_fragment_cli_creates_new(tmp_path: Path) -> None:
    target = tmp_path / "AGENTS.md"
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    
    code = main(["sync", "agent-fragment", "--target", str(target), "--bundle", str(bundle)])
    assert code == 0
    assert target.exists()
    
    content = target.read_text("utf-8")
    assert "<!-- KOSHA_AGENT_FRAGMENT_START -->" in content
    assert "<!-- KOSHA_AGENT_FRAGMENT_END -->" in content

def test_agent_fragment_cli_idempotent(tmp_path: Path) -> None:
    target = tmp_path / "AGENTS.md"
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    
    # First run
    main(["sync", "agent-fragment", "--target", str(target), "--bundle", str(bundle)])
    content1 = target.read_text("utf-8")
    
    # Second run
    code = main(
        ["sync", "agent-fragment", "--target", str(target), "--bundle", str(bundle), "--json"]
    )
    assert code == 0
    content2 = target.read_text("utf-8")
    
    assert content1 == content2

def test_agent_fragment_cli_json(tmp_path: Path, capsys) -> None:
    target = tmp_path / "AGENTS.md"
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    code = main(
        ["sync", "agent-fragment", "--target", str(target), "--bundle", str(bundle), "--json"]
    )
    assert code == 0
    
    out, _ = capsys.readouterr()
    data = json.loads(out)
    assert data["target"] == str(target)
    assert data["changed"] is True
