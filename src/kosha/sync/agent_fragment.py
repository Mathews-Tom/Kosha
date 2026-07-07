import re

from kosha.mcp.fallback import render_fallback_fragment

START_MARKER = "<!-- KOSHA_AGENT_FRAGMENT_START -->"
END_MARKER = "<!-- KOSHA_AGENT_FRAGMENT_END -->"

def render_agent_fragment_section() -> str:
    """Return the agent fragment section wrapped in markers."""
    return f"{START_MARKER}\n{render_fallback_fragment()}\n{END_MARKER}"

def update_instructions(content: str) -> str:
    """Update or insert the agent fragment section in the given content."""
    new_section = render_agent_fragment_section()
    
    pattern = re.compile(
        rf"{re.escape(START_MARKER)}.*?{re.escape(END_MARKER)}",
        re.DOTALL
    )
    
    if pattern.search(content):
        return pattern.sub(new_section, content)
    
    if content and not content.endswith("\n"):
        content += "\n"
    
    # If the file had content, we want a blank line before the new section
    if content:
        content += "\n"
        
    return content + new_section + "\n"
