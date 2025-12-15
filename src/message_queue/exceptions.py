"""
Custom exceptions for the message queue system.
"""


class MessageQueueError(Exception):
    """Base exception for message queue errors."""
    pass


class QueueNotFoundError(MessageQueueError):
    """Raised when attempting to access a non-existent queue."""
    pass


class TopicNotFoundError(MessageQueueError):
    """Raised when attempting to access a non-existent topic."""
    pass


class QueueAlreadyExistsError(MessageQueueError):
    """Raised when attempting to create a queue that already exists."""
    pass


class InvalidCallbackError(MessageQueueError):
    """Raised when an invalid callback is provided."""
    pass


class BrokerNotRunningError(MessageQueueError):
    """Raised when attempting operations on a stopped broker."""
    pass


class BrokerAlreadyRunningError(MessageQueueError):
    """Raised when attempting to start an already running broker."""
    pass


class MessageNotFoundError(MessageQueueError):
    """Raised when a specific message cannot be found."""
    pass
