"""
Manual test script for vagueness detection UI.

Run this script to see the vagueness detection in action with Rich formatting.

Usage:
    python tests/manual_test_vagueness_ui.py
"""

from rich.console import Console
from agent_cli.prompt_improvement import VaguenessDetector

console = Console()


def test_vagueness_ui():
    """Demonstrate vagueness detection with Rich UI."""
    detector = VaguenessDetector()

    console.print("\n[bold cyan]" + "=" * 80)
    console.print("[bold cyan]ArchiFlow Vagueness Detection - Manual Test")
    console.print("[bold cyan]" + "=" * 80 + "\n")

    test_prompts = [
        ("help", "Extremely vague"),
        ("fix the code", "Very vague"),
        ("review my code", "Moderately vague"),
        ("review authentication", "Some specificity"),
        ("review src/auth/middleware.py", "Clear file reference"),
        ("review src/auth/middleware.py for security", "Clear with objective"),
        ("Review src/auth/middleware.py for security vulnerabilities focusing on JWT validation", "Very clear"),
    ]

    for prompt, description in test_prompts:
        console.print(f"[bold]Test Prompt:[/bold] \"{prompt}\"")
        console.print(f"[dim]Expected: {description}[/dim]\n")

        result = detector.analyze(prompt)

        # Show score with color based on severity
        severity_colors = {
            "high": "red",
            "medium": "yellow",
            "low": "green"
        }
        severity_icons = {
            "high": "[!]",
            "medium": "[*]",
            "low": "[+]"
        }

        color = severity_colors.get(result.severity, "white")
        icon = severity_icons.get(result.severity, "[i]")

        console.print(f"{icon} [bold {color}]Score: {result.score}/100[/bold {color}] ({result.severity} severity)")

        if result.is_vague:
            console.print("[yellow]Status: VAGUE[/yellow]")
        else:
            console.print("[green]Status: CLEAR[/green]")

        if result.issues:
            console.print("\n[bold]Issues found:[/bold]")
            for issue in result.issues:
                console.print(f"  - [dim]{issue}[/dim]")

        if result.suggestions:
            console.print("\n[bold cyan]Suggestions:[/bold cyan]")
            for suggestion in result.suggestions:
                console.print(f"  - [cyan]{suggestion}[/cyan]")

        console.print("\n" + "-" * 80 + "\n")

    console.print("[bold green][+] Manual test complete!")
    console.print("\n[bold]To test in the actual REPL:[/bold]")
    console.print("1. Run: [cyan]py -m agent_cli[/cyan]")
    console.print("2. Try vague prompts like: [dim]'help', 'fix this', 'review my code'[/dim]")
    console.print("3. You'll see the vagueness warning with suggestions")
    console.print("4. Try clear prompts to see them pass through without warnings\n")


if __name__ == "__main__":
    test_vagueness_ui()
