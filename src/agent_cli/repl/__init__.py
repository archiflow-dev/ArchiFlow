"""
REPL (Read-Eval-Print Loop) engine for agent-cli.
"""

# Avoid circular import by using lazy import
def __getattr__(name):
    if name == "REPLEngine":
        from agent_cli.repl.engine import REPLEngine
        return REPLEngine
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = ["REPLEngine"]
