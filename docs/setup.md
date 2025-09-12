# System setup (Mac)

This guide assumes macOS (zsh) and VS Code.

## 1) Install prerequisites

```bash
# Ensure Python 3 is available
python3 --version

# Install pip if needed (on newer macOS it's bundled with Python 3)
python3 -m pip --version || curl -sS https://bootstrap.pypa.io/get-pip.py | python3 -

# Requests library (used by scripts)
python3 -m pip install --upgrade requests

Create minimal support pages so links aren’t broken:

`docs/setup.md`
```md
# Setup (Mac)
1. Install Python3 and VS Code.
2. `python3 -m pip install --upgrade requests`
3. Create `.env` with NOTION_TOKEN and NOTION_DB.
4. Use VS Code tasks to run daily/weekly.