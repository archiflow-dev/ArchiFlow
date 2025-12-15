"""Jupyter Notebook reading tool for agents."""
import json
import os
from typing import Any, Dict, List
from .tool_base import BaseTool, ToolResult


class NotebookReadTool(BaseTool):
    """Tool for reading Jupyter notebook files (.ipynb).

    This tool reads Jupyter notebooks and returns all cells with their outputs.
    Jupyter notebooks are interactive documents that combine code, text, and
    visualizations, commonly used for data analysis and scientific computing.
    """

    name: str = "notebook_read"
    description: str = (
        "Reads a Jupyter notebook (.ipynb file) and returns all of the cells "
        "with their outputs. Jupyter notebooks are interactive documents that "
        "combine code, text, and visualizations, commonly used for data analysis "
        "and scientific computing."
    )

    parameters: Dict = {
        "type": "object",
        "properties": {
            "notebook_path": {
                "type": "string",
                "description": "The absolute path to the Jupyter notebook file to read (must be absolute, not relative)"
            }
        },
        "required": ["notebook_path"]
    }

    def _format_cell(self, cell: Dict[str, Any], cell_num: int) -> str:
        """Format a single notebook cell for display.

        Args:
            cell: The cell dictionary from the notebook
            cell_num: The cell number (0-indexed)

        Returns:
            Formatted string representation of the cell
        """
        lines = []
        cell_type = cell.get("cell_type", "unknown")

        # Header
        lines.append(f"{'='*60}")
        lines.append(f"Cell {cell_num + 1} [{cell_type.upper()}]")
        lines.append(f"{'='*60}")

        # Source code
        source = cell.get("source", [])
        if isinstance(source, list):
            source_text = "".join(source)
        else:
            source_text = str(source)

        if source_text.strip():
            lines.append("\nSource:")
            lines.append("-" * 60)
            lines.append(source_text.rstrip())

        # Outputs (only for code cells)
        if cell_type == "code":
            outputs = cell.get("outputs", [])
            execution_count = cell.get("execution_count")

            # Always show execution count for code cells (None means not executed)
            lines.append(f"\nExecution Count: {execution_count}")

            if outputs:
                lines.append("\nOutputs:")
                lines.append("-" * 60)

                for i, output in enumerate(outputs):
                    if i > 0:
                        lines.append("")  # Blank line between outputs

                    output_type = output.get("output_type", "unknown")
                    lines.append(f"Output {i + 1} (type: {output_type})")

                    # Handle different output types
                    if output_type == "stream":
                        stream_name = output.get("name", "stdout")
                        text = output.get("text", [])
                        if isinstance(text, list):
                            text = "".join(text)
                        lines.append(f"[{stream_name}]")
                        lines.append(text.rstrip())

                    elif output_type == "execute_result":
                        data = output.get("data", {})
                        # Try to get plain text representation first
                        if "text/plain" in data:
                            text = data["text/plain"]
                            if isinstance(text, list):
                                text = "".join(text)
                            lines.append(text.rstrip())
                        else:
                            # Show available data types
                            lines.append(f"Available formats: {list(data.keys())}")

                    elif output_type == "display_data":
                        data = output.get("data", {})
                        # Try to get plain text representation first
                        if "text/plain" in data:
                            text = data["text/plain"]
                            if isinstance(text, list):
                                text = "".join(text)
                            lines.append(text.rstrip())
                        else:
                            # Show available data types
                            lines.append(f"Available formats: {list(data.keys())}")

                    elif output_type == "error":
                        ename = output.get("ename", "Error")
                        evalue = output.get("evalue", "")
                        lines.append(f"[ERROR] {ename}: {evalue}")

                        # Optionally include traceback
                        traceback = output.get("traceback", [])
                        if traceback:
                            lines.append("\nTraceback:")
                            lines.append("\n".join(traceback))

        lines.append("")  # Blank line at end of cell
        return "\n".join(lines)

    async def execute(self, notebook_path: str) -> ToolResult:
        """Read a Jupyter notebook and return all cells with outputs.

        Args:
            notebook_path: Absolute path to the .ipynb file to read

        Returns:
            ToolResult with formatted notebook contents or error
        """
        try:
            # Normalize path for cross-platform compatibility
            notebook_path = os.path.normpath(notebook_path)

            # Validate file path is absolute
            if not os.path.isabs(notebook_path):
                return ToolResult(
                    error=f"Notebook path must be absolute, not relative: {notebook_path}"
                )

            # Check if file exists
            if not os.path.exists(notebook_path):
                return ToolResult(
                    error=f"Notebook file does not exist: {notebook_path}"
                )

            # Check if path is a file (not a directory)
            if not os.path.isfile(notebook_path):
                return ToolResult(
                    error=f"Path is not a file: {notebook_path}"
                )

            # Check file extension
            if not notebook_path.lower().endswith('.ipynb'):
                return ToolResult(
                    error=f"File does not have .ipynb extension: {notebook_path}"
                )

            # Read and parse the notebook file
            try:
                with open(notebook_path, 'r', encoding='utf-8') as f:
                    notebook_data = json.load(f)
            except json.JSONDecodeError as e:
                return ToolResult(
                    error=f"Invalid JSON in notebook file: {str(e)}"
                )
            except UnicodeDecodeError:
                return ToolResult(
                    error=f"File appears to be binary or not UTF-8 encoded: {notebook_path}"
                )

            # Validate notebook structure
            if not isinstance(notebook_data, dict):
                return ToolResult(
                    error="Invalid notebook format: root element is not an object"
                )

            cells = notebook_data.get("cells", [])
            if not isinstance(cells, list):
                return ToolResult(
                    error="Invalid notebook format: 'cells' is not an array"
                )

            # Handle empty notebook
            if not cells:
                return ToolResult(
                    output=f"Notebook is empty (no cells)\n\nNotebook: {notebook_path}",
                    system="Warning: Notebook exists but has no cells"
                )

            # Format all cells
            formatted_cells = []
            for i, cell in enumerate(cells):
                if not isinstance(cell, dict):
                    formatted_cells.append(f"Cell {i + 1}: [Invalid cell format]")
                    continue

                formatted_cells.append(self._format_cell(cell, i))

            # Combine all cells
            output = "\n".join(formatted_cells)

            # Add metadata
            metadata_parts = []
            metadata_parts.append(f"\nNotebook: {notebook_path}")
            metadata_parts.append(f"Total Cells: {len(cells)}")

            # Count cell types
            code_cells = sum(1 for c in cells if isinstance(c, dict) and c.get("cell_type") == "code")
            markdown_cells = sum(1 for c in cells if isinstance(c, dict) and c.get("cell_type") == "markdown")
            raw_cells = sum(1 for c in cells if isinstance(c, dict) and c.get("cell_type") == "raw")

            if code_cells > 0:
                metadata_parts.append(f"Code Cells: {code_cells}")
            if markdown_cells > 0:
                metadata_parts.append(f"Markdown Cells: {markdown_cells}")
            if raw_cells > 0:
                metadata_parts.append(f"Raw Cells: {raw_cells}")

            # Notebook format version
            nbformat = notebook_data.get("nbformat")
            nbformat_minor = notebook_data.get("nbformat_minor")
            if nbformat is not None:
                metadata_parts.append(f"Format Version: {nbformat}.{nbformat_minor}")

            metadata = "\n".join(metadata_parts)

            return ToolResult(output=output + "\n" + metadata)

        except PermissionError:
            return ToolResult(
                error=f"Permission denied: {notebook_path}"
            )
        except Exception as e:
            return ToolResult(
                error=f"Error reading notebook: {type(e).__name__}: {str(e)}"
            )
