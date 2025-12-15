"""
Source package for the message queue system.
"""

from .message import Message, QueueConfig
from .metrics import MetricsCollector
from .exceptions import (
    MessageQueueError,
    QueueNotFoundError,
    TopicNotFoundError,
    QueueAlreadyExistsError,
    InvalidCallbackError,
    BrokerNotRunningError,
    BrokerAlreadyRunningError,
)

__all__ = [
    'Message',
    'QueueConfig',
    'MetricsCollector',
    'MessageQueueError',
    'QueueNotFoundError',
    'TopicNotFoundError',
    'QueueAlreadyExistsError',
    'InvalidCallbackError',
    'BrokerNotRunningError',
    'BrokerAlreadyRunningError',
]
