import pytest

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
