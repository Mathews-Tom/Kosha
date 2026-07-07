import pytest

from kosha.bench.acceptance import AcceptanceReport
from kosha.sync.cli_reference import (
    CLI_REFERENCE_PATH,
    README_PATH,
    write_cli_reference,
    write_readme_cli_overview,
)
from kosha.sync.status_surfaces import write_readme_acceptance_table
from kosha.sync.writer import GeneratedSectionWriter, MissingMarkerError


def test_preserve_hand_authored_prose():
    text = (
        "Hello world.\n\n"
        "<!-- kosha:sync:start test-section -->\n"
        "old content\n"
        "<!-- kosha:sync:end -->\n\n"
        "Goodbye."
    )
    writer = GeneratedSectionWriter("test-section")
    result = writer.write_section(text, "new content")

    assert "Hello world." in result
    assert "Goodbye." in result
    assert "old content" not in result
    assert "<!-- kosha:sync:start test-section -->\nnew content\n<!-- kosha:sync:end -->" in result


def test_missing_marker_raises():
    text = "Just some text without a marker."
    writer = GeneratedSectionWriter("test-section")
    with pytest.raises(MissingMarkerError, match="missing marker"):
        writer.write_section(text, "new content")


def test_missing_end_marker_raises():
    text = "<!-- kosha:sync:start test-section -->\nno end"
    writer = GeneratedSectionWriter("test-section")
    with pytest.raises(MissingMarkerError, match="missing marker"):
        writer.write_section(text, "new content")

def test_write_cli_reference(tmp_path):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    cli_ref = tmp_path / CLI_REFERENCE_PATH
    cli_ref.parent.mkdir(exist_ok=True)
    cli_ref.write_text(
        "<!-- kosha:sync:start cli-reference -->\n"
        "old\n"
        "<!-- kosha:sync:end -->"
    )

    write_cli_reference(tmp_path)

    content = cli_ref.read_text()
    assert "kosha [--version] [-h]" in content
    assert "kosha validate" in content

def test_write_readme_cli_overview(tmp_path):
    readme = tmp_path / README_PATH
    readme.write_text(
        "<!-- kosha:sync:start readme-cli-overview -->\n"
        "old\n"
        "<!-- kosha:sync:end -->"
    )

    write_readme_cli_overview(tmp_path)

    content = readme.read_text()
    assert "- `kosha validate`" in content

def test_write_readme_acceptance_table(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "kosha.sync.status_surfaces.run_default_acceptance_report",
        lambda root: AcceptanceReport("dummy", 0, "dummy", "dummy", ()),
    )
    readme = tmp_path / "README.md"
    readme.write_text(
        "<!-- kosha:sync:start readme-acceptance-table -->\n"
        "old\n"
        "<!-- kosha:sync:end -->"
    )

    write_readme_acceptance_table(tmp_path)

    content = readme.read_text()
    assert "| ID | Objective | Status |" in content
