from kosha.sync.agent_fragment import (
    END_MARKER,
    START_MARKER,
    render_agent_fragment_section,
    update_instructions,
)


def test_update_instructions_empty() -> None:
    result = update_instructions("")
    expected = render_agent_fragment_section() + "\n"
    assert result == expected


def test_update_instructions_append() -> None:
    original = "# My Agents\n\nSome custom instructions."
    result = update_instructions(original)

    assert result.startswith(original + "\n\n")
    assert START_MARKER in result
    assert END_MARKER in result
    assert result.endswith("\n")


def test_update_instructions_replace() -> None:
    original = f"""# My Agents

Some custom instructions.

{START_MARKER}
Old stale content
{END_MARKER}

More instructions after.
"""
    result = update_instructions(original)
    assert "Old stale content" not in result
    assert "Some custom instructions." in result
    assert "More instructions after." in result
    assert START_MARKER in result
    assert END_MARKER in result
