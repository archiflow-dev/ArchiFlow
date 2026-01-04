"""
Command validation for bash tools.

Validates bash commands for dangerous patterns.
"""

import logging
import re
from typing import Optional, Set

logger = logging.getLogger(__name__)


class CommandValidationError(Exception):
    """Raised when command validation fails."""

    def __init__(self, message: str, command: str = "", pattern: str = ""):
        """
        Initialize command validation error.

        Args:
            message: Error message
            command: The command that failed validation
            pattern: The pattern that matched
        """
        self.command = command
        self.pattern = pattern
        super().__init__(message)

    def __str__(self) -> str:
        """Format error with details."""
        if self.pattern:
            return f"{super().__str__()}: pattern='{self.pattern}' in command='{self.command}'"
        return super().__str__()


class CommandValidator:
    """
    Validates bash commands for dangerous patterns.

    Blocks:
    - Destructive commands (rm -rf /, dd, mkfs)
    - Privilege escalation (sudo)
    - Command injection (curl | bash)
    - Device writes (> /dev/sda)

    Usage:
        validator = CommandValidator(mode="strict")

        try:
            validator.validate("ls -la")  # Passes
            validator.validate("rm -rf /")  # Raises CommandValidationError
        except CommandValidationError:
            # Command blocked
            pass
    """

    # Default blocked patterns (regex)
    DEFAULT_BLOCKED_PATTERNS = {
        r"\brm\s+-rf\s+/",  # rm -rf /
        r"\bdd\s+if=",  # dd commands (disk destruction)
        r"\bmkfs\b",  # Filesystem creation
        r"\bformat\b",  # Windows format
        r">\s*/dev/",  # Writing to devices
        r"\bsudo\b",  # Sudo commands
        r"\bchmod\s+777\b",  # World writable
        r"\bcurl\b.*\|\s*bash",  # Pipe to bash
        r"\bwget\b.*\|\s*bash",  # Pipe to bash
        r"\bnc\s+",  # Netcat (potential backdoor)
        r"\bncat\s+",  # Ncat
    }

    def __init__(
        self,
        mode: str = "strict",
        allowed_commands: Optional[Set[str]] = None,
        blocked_patterns: Optional[Set[str]] = None,
    ):
        """
        Initialize command validator.

        Args:
            mode: Validation mode
                - "strict": Block all dangerous patterns
                - "permissive": Only block critical patterns
                - "disabled": No validation
            allowed_commands: Whitelist of allowed command names
                If set, only these commands are allowed
            blocked_patterns: Additional regex patterns to block
        """
        self.mode = mode
        self.allowed_commands = allowed_commands

        # Compile patterns for efficiency
        if mode == "permissive":
            # Only block most critical patterns
            critical = {r"\brm\s+-rf\s+/", r">\s*/dev/", r"\bsudo\b"}
            self.blocked_patterns = self._compile_patterns(critical)
        elif mode == "strict":
            patterns = blocked_patterns or self.DEFAULT_BLOCKED_PATTERNS
            self.blocked_patterns = self._compile_patterns(patterns)
        else:  # disabled
            self.blocked_patterns = set()

        logger.info(
            f"CommandValidator initialized: mode={mode}, "
            f"blocked_patterns={len(self.blocked_patterns)}, "
            f"allowed_commands={allowed_commands}"
        )

    def _compile_patterns(self, patterns: Set[str]) -> Set:
        """Compile regex patterns for efficiency."""
        compiled = set()
        for pattern in patterns:
            try:
                compiled.add(re.compile(pattern, re.IGNORECASE))
            except re.error as e:
                logger.warning(f"Invalid regex pattern: {pattern} - {e}")
        return compiled

    def validate(self, command: str) -> None:
        """
        Validate a bash command.

        Args:
            command: Command string to validate

        Raises:
            CommandValidationError: If command is dangerous
        """
        if self.mode == "disabled":
            return

        if not command or not command.strip():
            raise CommandValidationError("Empty command not allowed", command)

        # Check blocked patterns
        for pattern in self.blocked_patterns:
            if pattern.search(command):
                raise CommandValidationError(
                    "Dangerous command pattern blocked",
                    command=command,
                    pattern=pattern.pattern,
                )

        # Check whitelist if provided
        if self.allowed_commands is not None:
            # Extract first word (command name)
            match = re.match(r'^\s*(\S+)', command)
            if match:
                cmd_name = match.group(1)
                if cmd_name not in self.allowed_commands:
                    raise CommandValidationError(
                        f"Command not in allowed list: {cmd_name}",
                        command=command,
                    )

    def is_safe(self, command: str) -> bool:
        """
        Check if a command is safe without raising exception.

        Args:
            command: Command to check

        Returns:
            True if safe, False otherwise
        """
        try:
            self.validate(command)
            return True
        except CommandValidationError:
            return False

    def add_blocked_pattern(self, pattern: str) -> None:
        """
        Add a blocked pattern at runtime.

        Args:
            pattern: Regex pattern to block
        """
        try:
            compiled = re.compile(pattern, re.IGNORECASE)
            self.blocked_patterns.add(compiled)
            logger.info(f"Added blocked pattern: {pattern}")
        except re.error as e:
            logger.error(f"Invalid regex pattern: {pattern} - {e}")

    def set_allowed_commands(self, commands: Set[str]) -> None:
        """
        Set the whitelist of allowed commands.

        Args:
            commands: Set of allowed command names
        """
        self.allowed_commands = commands.copy()
        logger.info(f"Set allowed commands: {commands}")
