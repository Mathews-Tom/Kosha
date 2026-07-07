import tomllib
from pathlib import Path


def test_no_provider_sdk_dependencies():
    """Guard against adding heavy vendor SDKs to the provider model."""
    pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)
        
    deps = data.get("project", {}).get("dependencies", [])
    
    # Extract package names (strip versions)
    pkg_names = []
    for dep in deps:
        name = dep.split(">=")[0].split("==")[0].split("<")[0].split("~=")[0].strip()
        pkg_names.append(name)
    
    forbidden_sdks = {
        "openai", 
        "anthropic", 
        "google-genai", 
        "google-generativeai",
        "cohere", 
        "boto3", 
        "mistralai"
    }
    
    violations = [pkg for pkg in pkg_names if pkg.lower() in forbidden_sdks]
    assert not violations, f"Forbidden provider SDKs found in dependencies: {violations}"
