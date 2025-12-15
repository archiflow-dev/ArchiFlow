"""
Allow running agent-cli as a module: python -m agent_cli
"""

from agent_cli.main import cli

if __name__ == "__main__":
    cli()
