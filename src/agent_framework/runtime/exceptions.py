"""
Runtime exception hierarchy.

This module defines all exceptions that can be raised by the runtime system.
"""


class RuntimeException(Exception):
    """
    Base exception for all runtime errors.
    
    All runtime-specific exceptions inherit from this class.
    """
    pass


class TimeoutError(RuntimeException):
    """
    Tool execution exceeded the timeout limit.
    
    Raised when a tool takes longer than the specified timeout to execute.
    """
    
    def __init__(self, message: str, timeout: int):
        super().__init__(message)
        self.timeout = timeout


class ResourceLimitError(RuntimeException):
    """
    Tool execution exceeded resource limits.
    
    Raised when a tool exceeds memory, CPU, or other resource limits.
    """
    
    def __init__(self, message: str, resource_type: str, limit: any, actual: any = None):
        super().__init__(message)
        self.resource_type = resource_type
        self.limit = limit
        self.actual = actual


class SecurityViolation(RuntimeException):
    """
    Tool execution violated security policy.
    
    Raised when a tool attempts to perform an action that is not allowed
    by the security policy (e.g., network access when disabled, writing
    to blocked paths, etc.).
    """
    
    def __init__(self, message: str, violation_type: str):
        super().__init__(message)
        self.violation_type = violation_type


class RuntimeNotFoundError(RuntimeException):
    """
    Requested runtime is not registered or available.
    
    Raised when trying to use a runtime that hasn't been registered
    with the RuntimeManager.
    """
    
    def __init__(self, runtime_name: str):
        super().__init__(f"Runtime not found: {runtime_name}")
        self.runtime_name = runtime_name


class ToolNotFoundError(RuntimeException):
    """
    Requested tool is not found in the registry.
    
    Raised when trying to execute a tool that doesn't exist.
    """
    
    def __init__(self, tool_name: str):
        super().__init__(f"Tool not found: {tool_name}")
        self.tool_name = tool_name


class RuntimeInitializationError(RuntimeException):
    """
    Runtime failed to initialize.
    
    Raised when a runtime cannot be initialized (e.g., Docker daemon
    not running, MCP server failed to start, etc.).
    """
    pass


class ExecutionError(RuntimeException):
    """
    Generic tool execution error.
    
    Raised when tool execution fails for reasons other than timeout
    or resource limits.
    """
    pass
