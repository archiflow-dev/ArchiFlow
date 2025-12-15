"""
Tests for the output renderer.
"""

from io import StringIO

import pytest
from rich.console import Console

from agent_cli.output.renderer import OutputRenderer


@pytest.fixture
def test_console() -> Console:
    """Create a test console that writes to a StringIO."""
    return Console(file=StringIO(), width=80, legacy_windows=False)


@pytest.fixture
def renderer(test_console: Console) -> OutputRenderer:
    """Create a renderer with test console."""
    return OutputRenderer(console_instance=test_console)


def test_renderer_init() -> None:
    """Test renderer initialization."""
    r = OutputRenderer()
    assert r.console is not None


def test_renderer_error(renderer: OutputRenderer, test_console: Console) -> None:
    """Test error message rendering."""
    renderer.error("Something went wrong")
    output = test_console.file.getvalue()  # type: ignore[union-attr]
    assert "Error:" in output
    assert "Something went wrong" in output


def test_renderer_error_with_title(
    renderer: OutputRenderer, test_console: Console
) -> None:
    """Test error message with custom title."""
    renderer.error("Bad input", title="Validation Error")
    output = test_console.file.getvalue()  # type: ignore[union-attr]
    assert "Validation Error:" in output
    assert "Bad input" in output


def test_renderer_success(renderer: OutputRenderer, test_console: Console) -> None:
    """Test success message rendering."""
    renderer.success("Operation completed")
    output = test_console.file.getvalue()  # type: ignore[union-attr]
    assert "Operation completed" in output


def test_renderer_success_with_title(
    renderer: OutputRenderer, test_console: Console
) -> None:
    """Test success message with title."""
    renderer.success("File saved", title="Success")
    output = test_console.file.getvalue()  # type: ignore[union-attr]
    assert "Success:" in output
    assert "File saved" in output


def test_renderer_info(renderer: OutputRenderer, test_console: Console) -> None:
    """Test info message rendering."""
    renderer.info("Processing...")
    output = test_console.file.getvalue()  # type: ignore[union-attr]
    assert "Processing..." in output


def test_renderer_info_with_title(
    renderer: OutputRenderer, test_console: Console
) -> None:
    """Test info message with title."""
    renderer.info("Loading data", title="Status")
    output = test_console.file.getvalue()  # type: ignore[union-attr]
    assert "Status:" in output
    assert "Loading data" in output


def test_renderer_warning(renderer: OutputRenderer, test_console: Console) -> None:
    """Test warning message rendering."""
    renderer.warning("This might take a while")
    output = test_console.file.getvalue()  # type: ignore[union-attr]
    assert "This might take a while" in output


def test_renderer_warning_with_title(
    renderer: OutputRenderer, test_console: Console
) -> None:
    """Test warning message with title."""
    renderer.warning("Deprecated feature", title="Warning")
    output = test_console.file.getvalue()  # type: ignore[union-attr]
    assert "Warning:" in output
    assert "Deprecated feature" in output


def test_renderer_text(renderer: OutputRenderer, test_console: Console) -> None:
    """Test plain text rendering."""
    renderer.text("Hello, world!")
    output = test_console.file.getvalue()  # type: ignore[union-attr]
    assert "Hello, world!" in output


def test_renderer_text_with_style(
    renderer: OutputRenderer, test_console: Console
) -> None:
    """Test text with style."""
    renderer.text("Styled text", style="bold blue")
    output = test_console.file.getvalue()  # type: ignore[union-attr]
    assert "Styled text" in output


def test_renderer_markdown(renderer: OutputRenderer, test_console: Console) -> None:
    """Test markdown rendering."""
    renderer.markdown("# Heading\n\n**Bold text**")
    output = test_console.file.getvalue()  # type: ignore[union-attr]
    assert "Heading" in output


def test_renderer_code(renderer: OutputRenderer, test_console: Console) -> None:
    """Test code rendering."""
    renderer.code("def hello():\n    print('Hello')", language="python")
    output = test_console.file.getvalue()  # type: ignore[union-attr]
    assert "def hello():" in output


def test_renderer_panel(renderer: OutputRenderer, test_console: Console) -> None:
    """Test panel rendering."""
    renderer.panel("Content in panel", title="Test Panel")
    output = test_console.file.getvalue()  # type: ignore[union-attr]
    assert "Content in panel" in output
    assert "Test Panel" in output


def test_renderer_table(renderer: OutputRenderer, test_console: Console) -> None:
    """Test table rendering."""
    renderer.table(
        title="Test Table",
        columns=["Name", "Age"],
        rows=[["Alice", 30], ["Bob", 25]],
    )
    output = test_console.file.getvalue()  # type: ignore[union-attr]
    assert "Name" in output
    assert "Age" in output
    assert "Alice" in output
    assert "Bob" in output


def test_renderer_print(renderer: OutputRenderer, test_console: Console) -> None:
    """Test direct print access."""
    renderer.print("Direct print", style="bold")
    output = test_console.file.getvalue()  # type: ignore[union-attr]
    assert "Direct print" in output


def test_global_renderer() -> None:
    """Test global renderer instance."""
    from agent_cli.output import renderer

    assert renderer is not None
    assert isinstance(renderer, OutputRenderer)
