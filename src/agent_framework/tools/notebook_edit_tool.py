"""Jupyter Notebook editing tool for agents."""
import json
import os
from typing import Dict, Literal, Optional
from .tool_base import BaseTool, ToolResult


class NotebookEditTool(BaseTool):
    """Tool for editing Jupyter notebook cells (.ipynb files).

    This tool allows editing notebook cells by replacing, inserting, or deleting them.
    Jupyter notebooks are interactive documents that combine code, text, and
    visualizations, commonly used for data analysis and scientific computing.
    """

    name: str = "notebook_edit"
    description: str = (
        "Completely replaces the contents of a specific cell in a Jupyter notebook "
        "(.ipynb file) with new source. Supports replace, insert, and delete operations. "
        "The notebook_path parameter must be an absolute path. The cell_number is 0-indexed."
    )

    parameters: Dict = {
        "type": "object",
        "properties": {
            "notebook_path": {
                "type": "string",
                "description": "The absolute path to the Jupyter notebook file to edit (must be absolute, not relative)"
            },
            "cell_number": {
                "type": "integer",
                "description": "The index of the cell to edit (0-based)",
                "minimum": 0
            },
            "new_source": {
                "type": "string",
                "description": "The new source for the cell. Required for replace and insert modes. Ignored for delete mode."
            },
            "cell_type": {
                "type": "string",
                "enum": ["code", "markdown"],
                "description": "The type of the cell (code or markdown). If not specified, defaults to the current cell type. Required for insert mode."
            },
            "edit_mode": {
                "type": "string",
                "enum": ["replace", "insert", "delete"],
                "description": "The type of edit to make. Defaults to 'replace'. Use 'insert' to add a new cell at the index, 'delete' to remove the cell.",
                "default": "replace"
            }
        },
        "required": ["notebook_path", "cell_number", "new_source"]
    }

    def _create_new_cell(
        self,
        cell_type: Literal["code", "markdown"],
        source: str
    ) -> Dict:
        """Create a new notebook cell.

        Args:
            cell_type: Type of cell to create (code or markdown)
            source: Source code/text for the cell

        Returns:
            Dictionary representing the cell
        """
        # Split source into lines for notebook format
        if isinstance(source, str):
            # Keep the source as a single string initially, will split if needed
            source_lines = source.splitlines(keepends=True)
            # If no line has a newline, the source might not have any
            if source_lines and not source_lines[-1].endswith('\n'):
                # Don't add newline to last line if it doesn't have one
                pass
            elif not source_lines:
                source_lines = [source]
        else:
            source_lines = source

        cell = {
            "cell_type": cell_type,
            "metadata": {},
            "source": source_lines if source_lines else [""]
        }

        # Add execution-specific fields for code cells
        if cell_type == "code":
            cell["execution_count"] = None
            cell["outputs"] = []

        return cell

    async def execute(
        self,
        notebook_path: str,
        cell_number: int,
        new_source: str = "",
        cell_type: Optional[Literal["code", "markdown"]] = None,
        edit_mode: Literal["replace", "insert", "delete"] = "replace"
    ) -> ToolResult:
        """Edit a cell in a Jupyter notebook.

        Args:
            notebook_path: Absolute path to the .ipynb file to edit
            cell_number: Index of the cell to edit (0-based)
            new_source: New source code/text for the cell
            cell_type: Type of cell (code or markdown). Required for insert mode.
            edit_mode: Type of edit - replace, insert, or delete

        Returns:
            ToolResult with success message or error
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

            # Validate cell_number is non-negative
            if cell_number < 0:
                return ToolResult(
                    error=f"cell_number must be >= 0, got: {cell_number}"
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

            # Handle different edit modes
            if edit_mode == "delete":
                # Delete mode
                if cell_number >= len(cells):
                    return ToolResult(
                        error=f"Cell index {cell_number} is out of range. Notebook has {len(cells)} cell(s)."
                    )

                deleted_cell = cells[cell_number]
                deleted_type = deleted_cell.get("cell_type", "unknown")
                cells.pop(cell_number)

                success_msg = f"Successfully deleted cell {cell_number} (type: {deleted_type}) from {notebook_path}\n"
                success_msg += f"Notebook now has {len(cells)} cell(s)"

            elif edit_mode == "insert":
                # Insert mode
                if cell_type is None:
                    return ToolResult(
                        error="cell_type is required when edit_mode='insert'"
                    )

                if cell_type not in ["code", "markdown"]:
                    return ToolResult(
                        error=f"cell_type must be 'code' or 'markdown', got: {cell_type}"
                    )

                # Allow inserting at the end
                if cell_number > len(cells):
                    return ToolResult(
                        error=f"Cell index {cell_number} is out of range for insert. "
                        f"Notebook has {len(cells)} cell(s). You can insert at index 0 to {len(cells)}."
                    )

                new_cell = self._create_new_cell(cell_type, new_source)
                cells.insert(cell_number, new_cell)

                success_msg = f"Successfully inserted new {cell_type} cell at index {cell_number} in {notebook_path}\n"
                success_msg += f"Notebook now has {len(cells)} cell(s)"

            else:  # replace mode (default)
                # Replace mode
                if cell_number >= len(cells):
                    return ToolResult(
                        error=f"Cell index {cell_number} is out of range. Notebook has {len(cells)} cell(s)."
                    )

                # Get the existing cell
                existing_cell = cells[cell_number]

                # Determine cell type: use provided type, or keep existing type
                if cell_type is None:
                    cell_type = existing_cell.get("cell_type", "code")
                    if cell_type not in ["code", "markdown"]:
                        # If cell type is 'raw' or unknown, default to code
                        cell_type = "code"

                # Create new cell with the same structure
                new_cell = self._create_new_cell(cell_type, new_source)

                # Preserve metadata from original cell if same type
                if existing_cell.get("cell_type") == cell_type:
                    new_cell["metadata"] = existing_cell.get("metadata", {})

                cells[cell_number] = new_cell

                success_msg = f"Successfully replaced cell {cell_number} in {notebook_path}\n"
                success_msg += f"Cell type: {cell_type}"

            # Update the notebook data
            notebook_data["cells"] = cells

            # Write the modified notebook back to file
            try:
                with open(notebook_path, 'w', encoding='utf-8') as f:
                    json.dump(notebook_data, f, indent=1, ensure_ascii=False)
            except PermissionError:
                return ToolResult(
                    error=f"Permission denied: Cannot write to {notebook_path}"
                )

            return ToolResult(output=success_msg)

        except PermissionError:
            return ToolResult(
                error=f"Permission denied: {notebook_path}"
            )
        except Exception as e:
            return ToolResult(
                error=f"Error editing notebook: {type(e).__name__}: {str(e)}"
            )
