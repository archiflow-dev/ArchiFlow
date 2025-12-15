"""
Integration tests for project directory feature.

Tests the complete flow from CodingAgent initialization through
tool execution with relative paths.
"""

import pytest
from pathlib import Path
import tempfile
import asyncio


class TestProjectDirectoryIntegration:
    """End-to-end tests for project directory feature."""

    @pytest.mark.asyncio
    async def test_full_workflow_with_relative_paths(self):
        """Test complete workflow: init agent, write file, read file with relative paths."""
        from agent_framework.agents.coding_agent import CodingAgent
        from agent_framework.llm.mock import MockLLMProvider

        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            # 1. Create CodingAgent with project directory
            llm = MockLLMProvider()
            agent = CodingAgent(
                session_id="integration_test",
                llm=llm,
                project_directory=str(project_dir)
            )

            # 2. Get write tool and set its context
            write_tool = agent.tools.get("write")
            write_tool.execution_context = agent.execution_context

            # 3. Write a file using relative path
            result = await write_tool.execute(
                file_path="test.txt",
                content="Hello from integration test!"
            )

            assert not result.error, f"Write failed: {result.error}"

            # 4. Verify file was created in project directory
            created_file = project_dir / "test.txt"
            assert created_file.exists()
            assert created_file.read_text() == "Hello from integration test!"

            # 5. Read the file back using relative path
            read_tool = agent.tools.get("read")
            read_tool.execution_context = agent.execution_context

            result = await read_tool.execute(file_path="test.txt")

            assert not result.error, f"Read failed: {result.error}"
            assert "Hello from integration test!" in result.output

    @pytest.mark.asyncio
    async def test_nested_directory_creation(self):
        """Test creating files in nested directories with relative paths."""
        from agent_framework.agents.coding_agent import CodingAgent
        from agent_framework.llm.mock import MockLLMProvider

        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            # Create agent
            llm = MockLLMProvider()
            agent = CodingAgent(
                session_id="nested_test",
                llm=llm,
                project_directory=str(project_dir)
            )

            # Write file in nested directory
            write_tool = agent.tools.get("write")
            write_tool.execution_context = agent.execution_context

            result = await write_tool.execute(
                file_path="src/utils/helper.py",
                content="def helper(): pass"
            )

            assert not result.error

            # Verify nested structure
            created_file = project_dir / "src" / "utils" / "helper.py"
            assert created_file.exists()
            assert "def helper(): pass" in created_file.read_text()

    @pytest.mark.asyncio
    async def test_absolute_paths_still_work(self):
        """Ensure absolute paths continue to work alongside relative paths."""
        from agent_framework.agents.coding_agent import CodingAgent
        from agent_framework.llm.mock import MockLLMProvider

        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            external_dir = Path(tmpdir) / "external"
            external_dir.mkdir()

            # Create agent with project directory
            llm = MockLLMProvider()
            agent = CodingAgent(
                session_id="absolute_test",
                llm=llm,
                project_directory=str(project_dir)
            )

            # Write to external location using absolute path
            write_tool = agent.tools.get("write")
            write_tool.execution_context = agent.execution_context

            external_file = external_dir / "external.txt"
            result = await write_tool.execute(
                file_path=str(external_file),
                content="External file"
            )

            assert not result.error
            assert external_file.exists()

    @pytest.mark.asyncio
    async def test_edit_tool_with_relative_paths(self):
        """Test that edit tool works with relative paths."""
        from agent_framework.agents.coding_agent import CodingAgent
        from agent_framework.llm.mock import MockLLMProvider

        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            # Create agent
            llm = MockLLMProvider()
            agent = CodingAgent(
                session_id="edit_test",
                llm=llm,
                project_directory=str(project_dir)
            )

            # Create a test file first
            test_file = project_dir / "config.py"
            test_file.write_text("DEBUG = False\nVERSION = '1.0.0'")

            # Mark file as read for WriteTool's read-before-write check
            from agent_framework.tools.write_tool import WriteTool
            WriteTool.mark_as_read(str(test_file))

            # Edit the file using relative path
            edit_tool = agent.tools.get("edit")
            edit_tool.execution_context = agent.execution_context

            result = await edit_tool.execute(
                file_path="config.py",
                old_string="DEBUG = False",
                new_string="DEBUG = True"
            )

            assert not result.error, f"Edit failed: {result.error}"

            # Verify the edit
            content = test_file.read_text()
            assert "DEBUG = True" in content
            assert "VERSION = '1.0.0'" in content

    @pytest.mark.asyncio
    async def test_read_write_edit_cycle(self):
        """Test complete read -> edit -> write cycle with relative paths."""
        from agent_framework.agents.coding_agent import CodingAgent
        from agent_framework.llm.mock import MockLLMProvider

        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            # Create agent
            llm = MockLLMProvider()
            agent = CodingAgent(
                session_id="cycle_test",
                llm=llm,
                project_directory=str(project_dir)
            )

            # Set execution context on all tools
            write_tool = agent.tools.get("write")
            read_tool = agent.tools.get("read")
            edit_tool = agent.tools.get("edit")

            write_tool.execution_context = agent.execution_context
            read_tool.execution_context = agent.execution_context
            edit_tool.execution_context = agent.execution_context

            # 1. Write a file
            result = await write_tool.execute(
                file_path="data.json",
                content='{"name": "test", "value": 42}'
            )
            assert not result.error

            # 2. Read the file
            result = await read_tool.execute(file_path="data.json")
            assert not result.error
            assert '"name": "test"' in result.output

            # 3. Edit the file
            result = await edit_tool.execute(
                file_path="data.json",
                old_string='"value": 42',
                new_string='"value": 100'
            )
            assert not result.error

            # 4. Read again to verify
            result = await read_tool.execute(file_path="data.json")
            assert not result.error
            assert '"value": 100' in result.output

    @pytest.mark.asyncio
    async def test_parent_directory_navigation(self):
        """Test relative paths with parent directory navigation."""
        from agent_framework.agents.coding_agent import CodingAgent
        from agent_framework.llm.mock import MockLLMProvider

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create nested structure
            project_dir = Path(tmpdir) / "project"
            project_dir.mkdir()
            sibling_dir = Path(tmpdir) / "sibling"
            sibling_dir.mkdir()

            # Create agent with nested project directory
            llm = MockLLMProvider()
            agent = CodingAgent(
                session_id="parent_test",
                llm=llm,
                project_directory=str(project_dir)
            )

            # Try to write to sibling directory using ..
            write_tool = agent.tools.get("write")
            write_tool.execution_context = agent.execution_context

            result = await write_tool.execute(
                file_path="../sibling/file.txt",
                content="Sibling file"
            )

            # Should succeed (we're not in strict mode)
            assert not result.error

            # Verify file created in sibling directory
            sibling_file = sibling_dir / "file.txt"
            assert sibling_file.exists()

    @pytest.mark.asyncio
    async def test_multiple_tools_share_context(self):
        """Test that multiple tools can share the same execution context."""
        from agent_framework.agents.coding_agent import CodingAgent
        from agent_framework.llm.mock import MockLLMProvider

        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            # Create agent
            llm = MockLLMProvider()
            agent = CodingAgent(
                session_id="shared_context_test",
                llm=llm,
                project_directory=str(project_dir)
            )

            # All tools should share the same execution context
            write_tool = agent.tools.get("write")
            read_tool = agent.tools.get("read")
            edit_tool = agent.tools.get("edit")

            # Set same context on all
            for tool in [write_tool, read_tool, edit_tool]:
                tool.execution_context = agent.execution_context

            # Verify they all have the same working directory
            assert write_tool.get_working_directory() == str(project_dir)
            assert read_tool.get_working_directory() == str(project_dir)
            assert edit_tool.get_working_directory() == str(project_dir)

            # Verify they all resolve paths the same way
            assert write_tool.resolve_path("test.txt") == str(project_dir / "test.txt")
            assert read_tool.resolve_path("test.txt") == str(project_dir / "test.txt")
            assert edit_tool.resolve_path("test.txt") == str(project_dir / "test.txt")


class TestProjectDirectoryEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_empty_relative_path(self):
        """Test behavior with empty path."""
        from agent_framework.tools.read_tool import ReadTool
        from agent_framework.runtime.context import ExecutionContext
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            tool = ReadTool()
            tool.execution_context = ExecutionContext(
                session_id="test",
                working_directory=tmpdir
            )

            # Empty path should raise error
            with pytest.raises(ValueError, match="Path cannot be empty"):
                tool.resolve_path("")

    @pytest.mark.asyncio
    async def test_whitespace_path(self):
        """Test behavior with whitespace-only path."""
        from agent_framework.tools.read_tool import ReadTool
        from agent_framework.runtime.context import ExecutionContext
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            tool = ReadTool()
            tool.execution_context = ExecutionContext(
                session_id="test",
                working_directory=tmpdir
            )

            # Whitespace path should raise error
            with pytest.raises(ValueError, match="Path cannot be empty"):
                tool.resolve_path("   ")

    @pytest.mark.asyncio
    async def test_tool_without_context(self):
        """Test that tools work without execution context (backward compatibility)."""
        from agent_framework.tools.read_tool import ReadTool
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("No context test")

            # Tool without execution context
            tool = ReadTool()
            assert tool.execution_context is None
            assert tool.get_working_directory() is None

            # Should still work with absolute paths
            result = await tool.execute(file_path=str(test_file))
            assert not result.error
            assert "No context test" in result.output
