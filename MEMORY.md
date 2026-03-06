# Session Memory

## Python Version Updates for Home Assistant 2025.10
**Last updated:** 2026-03-06

When updating Python version requirements for Home Assistant 2025.10+:
- Update `requires-python` in pyproject.toml
- Update all tool target-version settings (black, mypy, ruff)
- Create `.python-version` file for explicit version specification
- All tools must use consistent version (e.g., py313)

## Files Modified
- `pyproject.toml` - Python version requirements and tool configs
- `.python-version` - Created for explicit version specification
