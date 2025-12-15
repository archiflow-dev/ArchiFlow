#!/usr/bin/env python
"""Development runner for ArchiFlow. Run this instead of installing the package."""

import sys
from pathlib import Path

# Add src to Python path
project_root = Path(__file__).parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

# Now import and run archiflow
from agent_cli.main import cli

if __name__ == "__main__":
    cli()