"""
PPT Agent Implementation.

An intelligent agent for creating professional presentations from ideas.
The agent dynamically determines its workflow based on user input and
existing files in the session directory.
"""

import logging
import json
from typing import Optional, Callable, Dict, Any
from pathlib import Path

from ..messages.types import (
    BaseMessage, UserMessage, SystemMessage, ToolCallMessage,
    ToolResultObservation, LLMRespondMessage, ToolCall
)
from ..tools.tool_base import ToolRegistry
from ..llm.provider import LLMProvider
from .base import BaseAgent

logger = logging.getLogger(__name__)


class PPTAgent(BaseAgent):
    """
    An intelligent presentation generation agent.

    This agent helps users:
    - Create presentations from ideas
    - Generate outlines for review
    - Create detailed slide descriptions
    - Generate consistent slide images
    - Export to PowerPoint and PDF formats

    The agent adapts its workflow based on available inputs:
    - Idea only: Generate outline → descriptions → images → export
    - Idea + outline: Generate descriptions → images → export
    - Idea + outline + descriptions: Generate images → export
    - Files provided: Load and process accordingly
    """

    # Core identity (always active)
    CORE_IDENTITY = """You are an expert Presentation Designer and Visual Storyteller. Your role is to:
- Transform ideas into compelling visual presentations
- Create logical, engaging slide structures
- Generate consistent, professional imagery
- Bridge the gap between concepts and visual communication

Your session directory is: {session_directory}

You always:
- Think about visual impact and storytelling flow
- Maintain consistent styling throughout presentations
- Consider the audience and presentation goals
- Provide options for user review and approval"""

    # Mode detection (first priority)
    MODE_DETECTION = """## MODE DETECTION (Always check this first)

Before any other action, assess what the user has provided:

### Step 1: Parse User Input for File Paths
Look for file paths mentioned in the user's message:
- Outline files: "outline.json", "presentation.md", etc.
- Description files: "descriptions.json", "slides.json"
- Image directories: "images/", "slides/"
- Common patterns:
  * "Use outline from data/my_outline.json"
  * "Load the descriptions file"
  * "Create presentation from 'outline.json' and 'descriptions.json'"
  * "Images are in the 'generated/' directory"

### Step 2: Validate and Load External Files
For each file path found:
1. Check if the file/directory exists
2. Validate file format (.json, .md, .yaml)
3. Load content into session directory if valid
4. Report any issues to user

### Step 3: Check Session Directory
Use `list` and `read` to check for existing files:
- outline.json or outline.md
- descriptions.json
- Any generated slide images (slide_*.png)

### Step 4: Determine Your Mode

**IF** user provided only an idea AND no files exist anywhere:
→ ENTER IDEA MODE
- Generate comprehensive outline first
- Save for review and approval
- Then generate descriptions
- Finally generate images and export

**IF** user provided idea + outline (in message OR file OR session):
→ ENTER OUTLINE MODE
- Load/use existing outline (prioritize: message > session > external)
- Generate detailed slide descriptions
- Save for review and approval
- Then generate images and export

**IF** user provided idea + outline + descriptions (in message OR file OR session):
→ ENTER GENERATION MODE
- Load existing outline and descriptions
- Proceed directly to image generation
- Export to PPTX and PDF formats

**IF** user provides feedback on outline/descriptions:
→ ENTER REVISION MODE
- Load current version
- Apply feedback to regenerate
- Save as new revision
- Continue from appropriate stage

**ALWAYS** announce your mode when starting:
- "I'm entering IDEA MODE - I'll create an outline from your idea..."
- "I'm entering OUTLINE MODE - I'll work with your outline..."
- "I'm entering GENERATION MODE - I'll create your presentation..."
- "I'm entering REVISION MODE - I'll update based on your feedback..."
"""

    # Idea mode workflow
    IDEA_MODE = """## IDEA MODE

User provided only an idea. Here's your complete workflow:

### Phase 1: Generate Outline
1. **Create Comprehensive Outline**
   - Generate 8 slides (adjust 6-12 as appropriate)
   - Include for each slide:
     * Clear, engaging title
     * 2-4 key bullet points
     * Visual style notes
     * Slide type (title, content, conclusion, etc.)
   - Consider: audience, duration, key messages

2. **Save and Present**
   - Save as outline.json in session directory
   - Present structure to user:
     * Title and subtitle
     * Slide titles in order
     * Brief flow description
   - Ask: "Does this outline capture your vision?"

3. **Wait for Approval or Feedback**
   - If approved: proceed to Phase 2
   - If feedback: apply changes, save revision, ask again
   - Never proceed without user confirmation

### Phase 2: Generate Descriptions (after outline approved)
1. **Create Detailed Slide Descriptions**
   - For each slide in outline:
     * Refine title for impact
     * Organize content into clear bullet points
     * Generate detailed image prompt
     * Specify visual elements (colors, layout, icons)
     * Consider consistency with other slides

2. **Save and Sample**
   - Save all descriptions as descriptions.json
   - Show 2-3 sample descriptions:
     * Text content
     * Image prompt
     * Visual style notes
   - Ask: "Are these descriptions ready for image generation?"

3. **Wait for Approval or Revision**
   - If approved: proceed to Phase 3
   - If revisions: regenerate descriptions as requested

### Phase 3: Generate Images and Export
1. **Generate Slide Images**
   - Use generate_image tool for each description
   - First slide establishes visual style
   - Maintain consistency in subsequent slides
   - Show progress: "[1/8] Generating title slide..."

2. **Export Presentations**
   - Export to PPTX using export_pptx tool
   - Export to PDF using export_pdf tool
   - Provide file locations and sizes
   - Offer to open files

Exit condition: When user has presentation files OR requests different approach"""

    # Outline mode workflow
    OUTLINE_MODE = """## OUTLINE MODE

User provided outline. Here's your complete workflow:

### Phase 1: Process Outline
1. **Load or Parse Outline**
   - If file path provided: use read tool to load
   - If inline content: parse from message
   - Validate structure (has title, slides array)
   - Ensure each slide has title and content

2. **Save and Confirm**
   - Save as outline.json if not already
   - Present quick summary:
     * Slide count and titles
     * Overall flow
   - Ask: "Should I proceed with generating detailed descriptions?"

3. **Wait for Confirmation**
   - If confirmed: proceed to Phase 2
   - If changes needed: apply and save revision

### Phase 2: Generate Descriptions
[Same Phase 2 as IDEA MODE]

### Phase 3: Generate Images and Export
[Same Phase 3 as IDEA MODE]

Exit condition: When presentation is generated"""

    # Generation mode workflow
    GENERATION_MODE = """## GENERATION MODE

User provided outline and descriptions. Here's your workflow:

### Phase 1: Load and Validate
1. **Load Materials**
   - Use read tool to load outline.json
   - Use read tool to load descriptions.json
   - Validate compatibility (same slide count)
   - Check descriptions completeness

2. **Quick Confirmation**
   - Report: "Found outline with X slides and complete descriptions"
   - Show title and first slide example
   - Ask: "Proceed with generating your presentation?"

3. **Wait for Go-Ahead**
   - If ready: proceed to Phase 2
   - If need changes: enter REVISION MODE

### Phase 2: Generate Images and Export
[Same Phase 3 from IDEA MODE]

Exit condition: When both PPTX and PDF are generated"""

    # Revision mode workflow
    REVISION_MODE = """## REVISION MODE

User provided feedback. Here's your workflow:

### Phase 1: Understand Feedback
1. **Identify Target**
   - Determine if feedback is about outline or descriptions
   - Load current version from appropriate file
   - Parse specific feedback points

2. **Apply Changes**
   - If outline: regenerate with feedback incorporated
   - If descriptions: regenerate specific slides or all
   - Maintain consistency with unchanged parts
   - Save as revision (outline_v2.json, descriptions_v2.json)

3. **Present Changes**
   - Highlight what was modified
   - Show before/after if helpful
   - Ask: "Does this revision address your feedback?"

### Phase 2: Continue Workflow
- If approved: return to appropriate phase (descriptions or generation)
- If more feedback: repeat revision cycle
- Track revision count to avoid infinite loops

Exit condition: When user approves revision"""

    # Universal guidelines for all modes
    UNIVERSAL_GUIDELINES = """## UNIVERSAL GUIDELINES

### Communication Style
- Be conversational but professional
- Show enthusiasm for their presentation topic
- Explain what you're doing and why
- Ask clear questions when you need input

### Progress Reporting
- Always indicate your current phase
- Use progress indicators: "[3/8] Generating images..."
- For long operations: estimate time remaining
- Confirm before proceeding to major steps

### Visual Design Principles
- First slide establishes visual style
- Maintain consistent color palette
- Use similar composition approach
- Consider audience (professional, academic, casual)
- Ensure text is readable on backgrounds

### File Management
- Always save intermediate results
- Use consistent naming: outline.json, descriptions.json
- Keep revision history in revisions/ subdirectory
- Copy external files to session directory for consistency
- Clean up temporary files after completion

### User Approval Workflow
- Never proceed without approval at key points
- Always provide the option to revise
- Explain what will happen next
- Save work at each approval point

### Error Handling
- If file not found: ask for correct path
- If generation fails: offer to retry with different approach
- If feedback unclear: ask for specific examples
- Never lose user's work or progress

### External File Handling
- When user provides file paths:
  * Validate file exists before using
  * Copy to session directory to maintain consistency
  * Report file loading status clearly
  * Handle different formats (.json, .md, .yaml)
- When file cannot be found:
  * Ask user to verify the path
  * Offer to continue without that file
  * Suggest creating the file if needed"""

    # Tool usage guidelines
    TOOL_GUIDELINES = """## TOOL USAGE

### Available Tools
- **read**: Load outline.json, descriptions.json
- **write**: Save generated content
- **list**: Check session directory contents
- **bash**: Execute shell commands (rename/remove files, file management)
- **web_search**: Search the web for information to include in presentations
- **web_fetch**: Fetch content from URLs (images, reference material)
- **generate_image**: Create slide images
- **export_pptx**: Create PowerPoint presentation
- **export_pdf**: Create PDF version

### Tool Usage Patterns

**Outline Generation**:
1. Use LLM to create outline content
2. Use write("outline.json", outline_data)

**Description Generation**:
1. Read outline.json
2. For each slide: use LLM for descriptions
3. Accumulate all descriptions
4. Write descriptions.json

**Image Generation**:
1. Read descriptions.json
2. For each slide, call generate_image with ALL available fields:
   - prompt: Basic description (required)
   - title: Slide title (for context in image)
   - content: List of bullet points (for context in image)
   - image_prompt: Detailed visual description
   - visual_style: Style and aesthetic approach
   - slide_type: "title", "content", or "conclusion"
   - slide_number: Slide number (1-based)
   - session_id: Session ID for organizing images
3. Track generated image paths
4. Call export_pptx(session_id=session_id)
5. Call export_pdf(session_id=session_id)

**File Operations**:
- Always check if files exist before reading
- Use session directory for all saves
- Maintain consistent file formats"""

    # Completion criteria
    COMPLETION_CRITERIA = """## COMPLETION CRITERIA

Call `finish_task` when you have delivered:

**Must Have:**
1. [DONE] Generated or loaded outline
2. [DONE] Generated or loaded descriptions
3. [DONE] Generated all slide images
4. [DONE] Exported to PPTX and PDF
5. [DONE] Provided file locations to user

**Before finishing:**
1. Summarize what was created
2. Provide file paths and sizes
3. Offer to open presentations
4. Ask if they need anything else

**Success Message Example:**
"[SUCCESS] Your presentation is ready! I've created:
- PPTX: data/ppt_exports/Your_Title_20241220_143022.pptx (2.1 MB)
- PDF: data/ppt_exports/Your_Title_20241220_143022.pdf (1.8 MB)
- All images saved in: data/sessions/session_123/images/

Would you like me to open the presentation or make any adjustments?"""

    def step(self, message: BaseMessage) -> BaseMessage:
        """Process a single message."""
        if not self.is_running:
            return None

        # 1. Update Memory
        self._update_memory(message)

        # 2. Check for external files in user input
        if hasattr(message, 'content') and message.content:
            file_paths = self._extract_file_paths(message.content)

            # Process any found files
            if any(file_paths.values()):
                return self._handle_external_files(file_paths, message)

        # 3. Add system message if not already added
        if not self._system_added:
            system_msg = SystemMessage(
                session_id=self.session_id,
                sequence=self._next_sequence(),
                content=self.get_system_message()
            )
            self.history.add(system_msg)
            self._system_added = True

        # 3. Generate response
        # Convert history to LLM format
        messages = self.history.to_llm_format()

        # Get tools schema
        tools_schema = self._get_tools_schema()

        # Call LLM
        response = self.llm.generate(messages, tools=tools_schema)

        # 4. Process Response
        # Handle tool calls
        if response.tool_calls:
            # Create ToolCallMessage
            tool_calls = []
            for tc in response.tool_calls:
                tool_calls.append(ToolCall(
                    id=tc.id,
                    tool_name=tc.name,
                    arguments=json.loads(tc.arguments) if isinstance(tc.arguments, str) else tc.arguments
                ))

            tool_msg = ToolCallMessage(
                session_id=self.session_id,
                sequence=self._next_sequence(),
                tool_calls=tool_calls,
                thought=response.content
            )

            # Update history and publish tool call
            self._update_memory(tool_msg)
            if self.publish_callback:
                self.publish_callback(tool_msg)

            # Execute tools (simplified - in real implementation,
            # this would be handled by the runtime)
            # For now, we'll just return the tool call message
            return tool_msg
        else:
            # Create response message
            response_msg = LLMRespondMessage(
                session_id=self.session_id,
                sequence=self._next_sequence(),
                content=response.content
            )

            # Update history
            self._update_memory(response_msg)

            return response_msg

    def _update_memory(self, message: BaseMessage) -> None:
        """Update memory components based on the message."""
        self.history.add(message)

        # Update tracker if it's a tool result
        if isinstance(message, ToolResultObservation):
            # Find the matching tool call in history
            for msg in reversed(self.history.get_messages()):
                if isinstance(msg, ToolCallMessage):
                    for tc in msg.tool_calls:
                        if tc.id == message.call_id:
                            self.tracker.update(tc.tool_name, tc.arguments, message.content)
                            return

    def _next_sequence(self) -> int:
        """Get next sequence number."""
        seq = self.sequence_counter
        self.sequence_counter += 1
        return seq

    def _extract_file_paths(self, user_message: str) -> dict:
        """
        Extract file paths mentioned in user message.

        Args:
            user_message: The user's input text

        Returns:
            Dictionary with keys 'outline_files', 'description_files', 'image_files'
        """
        import re

        # Common file patterns to look for
        outline_patterns = [
            r'outline[:\s]+(["\']?)([^"\'\s]+\.json)(["\']?)',
            r'outline[:\s]+(["\']?)([^"\'\s]+\.md)(["\']?)',
            r'(?:use|load|from)\s+["\']?([^"\'\s]+\.json)["\']?\s+(?:outline|presentation)',
            r'(?:use|load|from)\s+["\']?([^"\'\s]+\.md)["\']?\s+(?:outline|presentation)',
            r'["\']([^"\']*(?:outline|presentation)[^"\']*\.(?:json|md))["\']',
        ]

        description_patterns = [
            r'descriptions?[:\s]+(["\']?)([^"\'\s]+\.json)(["\']?)',
            r'(?:use|load|from)\s+["\']?([^"\'\s]+\.json)["\']?\s+(?:descriptions?|slides?)',
            r'["\']([^"\']*(?:description|slide)[^"\']*\.(?:json|yaml))["\']',
        ]

        image_patterns = [
            r'images?\s+(?:from|in)\s+(["\']?)([^"\'\s]+)(["\']?)',
            r'(?:use|load)\s+images?\s+from\s+["\']?([^"\'\s]+)["\']?',
        ]

        found = {
            'outline_files': [],
            'description_files': [],
            'image_files': []
        }

        # Find outline files
        for pattern in outline_patterns:
            matches = re.findall(pattern, user_message, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    # Get the captured group (file path)
                    file_path = match[1] if len(match) > 1 else match[0]
                else:
                    file_path = match
                if file_path and file_path not in found['outline_files']:
                    found['outline_files'].append(file_path)

        # Find description files
        for pattern in description_patterns:
            matches = re.findall(pattern, user_message, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    file_path = match[1] if len(match) > 1 else match[0]
                else:
                    file_path = match
                if file_path and file_path not in found['description_files']:
                    found['description_files'].append(file_path)

        # Find image directories
        for pattern in image_patterns:
            matches = re.findall(pattern, user_message, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    dir_path = match[1] if len(match) > 1 else match[0]
                else:
                    dir_path = match
                if dir_path and dir_path not in found['image_files']:
                    found['image_files'].append(dir_path)

        return found

    def _validate_file_path(self, file_path: str) -> Optional[Path]:
        """
        Validate and resolve a file path.

        Args:
            file_path: The file path to validate

        Returns:
            Path object if valid and exists, None otherwise
        """
        # Convert to Path object
        path = Path(file_path)

        # If relative, try to resolve from current directory
        if not path.is_absolute():
            path = Path.cwd() / path

        # Check if file exists
        if path.exists():
            return path.resolve()

        return None

    def _load_file_content(self, file_path: Path) -> Optional[dict]:
        """
        Load content from JSON or YAML file.

        Args:
            file_path: Path to the file

        Returns:
            Parsed content as dictionary, None if error
        """
        try:
            if file_path.suffix.lower() == '.json':
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            elif file_path.suffix.lower() in ['.yaml', '.yml']:
                import yaml
                with open(file_path, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f)
            elif file_path.suffix.lower() == '.md':
                # For markdown, just read the content
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    return {'content': content, 'format': 'markdown'}
            else:
                logger.warning(f"Unsupported file format: {file_path.suffix}")
                return None
        except Exception as e:
            logger.error(f"Error loading file {file_path}: {e}")
            return None

    def _handle_external_files(self, file_paths: dict, message: BaseMessage) -> BaseMessage:
        """
        Handle external files mentioned in user message.

        Args:
            file_paths: Dictionary of found file paths
            message: Original user message

        Returns:
            Response message about file handling
        """
        results = {
            'loaded': [],
            'not_found': [],
            'errors': []
        }

        # Handle outline files
        for file_path in file_paths['outline_files']:
            validated_path = self._validate_file_path(file_path)
            if validated_path:
                content = self._load_file_content(validated_path)
                if content:
                    # Save to session directory
                    session_path = Path(self.project_directory) / "outline.json"
                    import json
                    with open(session_path, 'w', encoding='utf-8') as f:
                        json.dump(content, f, indent=2)
                    results['loaded'].append({
                        'type': 'outline',
                        'original_path': str(validated_path),
                        'session_path': str(session_path),
                        'slides': len(content.get('slides', [])) if 'slides' in content else 'N/A'
                    })
                else:
                    results['errors'].append(f"Failed to load outline file: {file_path}")
            else:
                results['not_found'].append(file_path)

        # Handle description files
        for file_path in file_paths['description_files']:
            validated_path = self._validate_file_path(file_path)
            if validated_path:
                content = self._load_file_content(validated_path)
                if content:
                    # Save to session directory
                    session_path = Path(self.project_directory) / "descriptions.json"
                    import json
                    with open(session_path, 'w', encoding='utf-8') as f:
                        json.dump(content, f, indent=2)
                    results['loaded'].append({
                        'type': 'descriptions',
                        'original_path': str(validated_path),
                        'session_path': str(session_path),
                        'slides': len(content) if isinstance(content, list) else 'N/A'
                    })
                else:
                    results['errors'].append(f"Failed to load descriptions file: {file_path}")
            else:
                results['not_found'].append(file_path)

        # Create response message
        response_lines = [f"I found the following files in your message:"]

        if results['loaded']:
            response_lines.append("\n[OK] Successfully loaded:")
            for item in results['loaded']:
                response_lines.append(f"  - {item['type']} file: {item['original_path']}")
                response_lines.append(f"    → Saved to session directory ({item['slides']} slides)")

        if results['not_found']:
            response_lines.append("\n[ERROR] Files not found:")
            for file_path in results['not_found']:
                response_lines.append(f"  - {file_path}")

        if results['errors']:
            response_lines.append("\n[WARNING] Errors:")
            for error in results['errors']:
                response_lines.append(f"  - {error}")

        # Determine next step
        if results['loaded']:
            response_lines.append("\nI'll now proceed with creating your presentation based on these files.")
        elif results['not_found'] and not results['loaded']:
            response_lines.append("\nPlease verify the file paths and try again. Would you like to:")
            response_lines.append("1. Create a presentation from an idea instead?")
            response_lines.append("2. Provide correct file paths?")

        # Return LLM response message
        return LLMRespondMessage(
            session_id=self.session_id,
            sequence=self._next_sequence(),
            content='\n'.join(response_lines)
        )

    def __init__(
        self,
        session_id: str,
        llm: LLMProvider,
        google_api_key: str,
        project_directory: Optional[str] = None,
        tools: Optional[ToolRegistry] = None,
        publish_callback: Optional[Callable[[BaseMessage], None]] = None,
        debug_log_path: Optional[str] = None
    ):
        """
        Initialize the PPT Agent.

        Args:
            session_id: The session identifier.
            llm: The LLM provider for intelligent conversation.
            google_api_key: API key for Google image generation.
            project_directory: Directory for session files.
                              Defaults to data/sessions/{session_id}.
            tools: Optional custom tools. If None, uses global registry.
            publish_callback: Callback for publishing messages to broker.
            debug_log_path: Optional path to debug log file.
        """
        # Set project directory to session directory
        if project_directory is None:
            project_directory = f"data/sessions/{session_id}"

        # Define allowed tools
        self.allowed_tools = [
            "read", "write",              # File operations
            "list",                      # Directory operations
            "bash",                      # Shell commands (rename/remove files)
            "web_search", "web_fetch",   # Web research capabilities
            "generate_image",            # Image generation
            "export_pptx", "export_pdf", # Presentation export
            "finish_task"                # Completion signal
        ]

        # Store Google API key for image provider
        self.google_api_key = google_api_key

        # Set additional attributes BEFORE calling parent constructor
        if tools is None:
            # Get the global registry with all registered tools
            from ..tools.all_tools import registry
            self.tools = registry
        else:
            self.tools = tools
        self.tool_registry = self.tools
        self.session_id = session_id
        self.project_directory = project_directory or f"data/sessions/{session_id}"
        self.publish_callback = publish_callback
        self.is_running = True
        self._system_added = False
        self.sequence_counter = 0

        # Call parent constructor
        super().__init__(
            llm=llm,
            config={
                "name": "PPTAgent",
                "version": "1.0.0",
                "session_id": session_id
            }
        )

        logger.info(
            f"PPTAgent initialized for session {session_id}, "
            f"project: {self.project_directory}"
        )

    def get_system_message(self) -> str:
        """
        Dynamically build system prompt based on current context.

        Returns:
            Complete system message with appropriate mode instructions
        """
        # Build the prompt parts
        prompt_parts = [
            self.CORE_IDENTITY.format(session_directory=self.project_directory),
            self.MODE_DETECTION,
        ]

        # Check what exists in session directory
        session_path = Path(self.project_directory)
        has_outline = (session_path / "outline.json").exists()
        has_descriptions = (session_path / "descriptions.json").exists()
        has_images = len(list(session_path.glob("images/slide_*.png"))) > 0

        # Add appropriate mode instructions
        if not has_outline and not has_descriptions and not has_images:
            prompt_parts.append(self.IDEA_MODE)
        elif has_outline and not has_descriptions:
            prompt_parts.append(self.OUTLINE_MODE)
        elif has_outline and has_descriptions:
            prompt_parts.append(self.GENERATION_MODE)

        # Always include revision mode possibility
        prompt_parts.append(self.REVISION_MODE)

        # Add universal guidelines
        prompt_parts.extend([
            self.UNIVERSAL_GUIDELINES,
            self.TOOL_GUIDELINES,
            self.COMPLETION_CRITERIA
        ])

        # Add session-specific context
        prompt_parts.append(
            f"\n\nCurrent Session Context:\n"
            f"Session ID: {self.session_id}\n"
            f"Session Directory: {self.project_directory}\n"
            f"Has Outline: {has_outline}\n"
            f"Has Descriptions: {has_descriptions}\n"
            f"Has Images: {has_images}"
        )

        return "\n\n".join(prompt_parts)

    def _setup_tools(self):
        """
        Setup and configure tools for the PPT Agent.

        The agent uses tools for:
        - File operations (read, write, list)
        - Image generation with Google API
        - Presentation export (PPTX, PDF)
        """
        # Set up Google image provider for generate_image tool
        from ..llm.google_image_provider import GoogleImageProvider
        image_provider = GoogleImageProvider(api_key=self.google_api_key)

        # Configure the generate_image tool with the provider
        if "generate_image" in self.tools:
            self.tools["generate_image"].image_provider = image_provider

        logger.info(f"PPTAgent configured {len(self.allowed_tools)} tools")

    def _get_tools_schema(self) -> list[dict]:
        """
        Get filtered tool schema for PPT operations.

        Returns:
            List of tool schemas for allowed PPT tools
        """
        return self.tools.to_llm_schema(tool_names=self.allowed_tools)

    def _format_finish_message(self, reason: str, result: str) -> str:
        """
        Format finish message to include presentation details.

        Args:
            reason: Reason for finishing
            result: Summary of created presentations

        Returns:
            Formatted message with presentation details
        """
        return f"{reason}\n\n{result}"