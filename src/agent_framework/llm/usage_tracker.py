"""
Token usage and cost tracking for LLM calls.
"""
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime

from .model_config import ModelConfig

logger = logging.getLogger(__name__)


@dataclass
class UsageRecord:
    """Record of a single LLM API call."""

    timestamp: datetime
    model: str
    input_tokens: int
    output_tokens: int
    cost: float
    session_id: Optional[str] = None

    @property
    def total_tokens(self) -> int:
        """Total tokens (input + output)."""
        return self.input_tokens + self.output_tokens


class UsageTracker:
    """
    Tracks token usage and costs across LLM API calls.

    Usage:
        tracker = UsageTracker()
        tracker.record(model_config, input_tokens=100, output_tokens=50)
        print(tracker.get_summary())
    """

    def __init__(self):
        """Initialize the usage tracker."""
        self.records: List[UsageRecord] = []
        self._totals_by_model: Dict[str, Dict[str, float]] = {}

    def record(
        self,
        model_config: ModelConfig,
        input_tokens: int,
        output_tokens: int,
        session_id: Optional[str] = None
    ) -> UsageRecord:
        """
        Record a single LLM API call.

        Args:
            model_config: Configuration for the model used
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            session_id: Optional session identifier

        Returns:
            UsageRecord for this call
        """
        cost = model_config.calculate_cost(input_tokens, output_tokens)

        record = UsageRecord(
            timestamp=datetime.now(),
            model=model_config.model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            session_id=session_id
        )

        self.records.append(record)

        # Update totals
        if model_config.model_name not in self._totals_by_model:
            self._totals_by_model[model_config.model_name] = {
                "input_tokens": 0,
                "output_tokens": 0,
                "cost": 0.0,
                "calls": 0
            }

        totals = self._totals_by_model[model_config.model_name]
        totals["input_tokens"] += input_tokens
        totals["output_tokens"] += output_tokens
        totals["cost"] += cost
        totals["calls"] += 1

        logger.debug(
            f"Usage recorded: {model_config.model_name} - "
            f"in={input_tokens}, out={output_tokens}, cost=${cost:.4f}"
        )

        return record

    def get_summary(self) -> Dict[str, Any]:
        """
        Get a summary of all usage.

        Returns:
            Dictionary with usage statistics
        """
        total_cost = sum(r.cost for r in self.records)
        total_input_tokens = sum(r.input_tokens for r in self.records)
        total_output_tokens = sum(r.output_tokens for r in self.records)

        return {
            "total_calls": len(self.records),
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "total_tokens": total_input_tokens + total_output_tokens,
            "total_cost": total_cost,
            "by_model": dict(self._totals_by_model)
        }

    def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        """
        Get usage summary for a specific session.

        Args:
            session_id: The session ID to filter by

        Returns:
            Dictionary with session statistics
        """
        session_records = [r for r in self.records if r.session_id == session_id]

        if not session_records:
            return {
                "session_id": session_id,
                "total_calls": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_tokens": 0,
                "total_cost": 0.0
            }

        total_cost = sum(r.cost for r in session_records)
        total_input = sum(r.input_tokens for r in session_records)
        total_output = sum(r.output_tokens for r in session_records)

        return {
            "session_id": session_id,
            "total_calls": len(session_records),
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_tokens": total_input + total_output,
            "total_cost": total_cost
        }

    def print_summary(self):
        """Print a formatted summary of usage to the console."""
        summary = self.get_summary()

        print("\n" + "="*60)
        print("LLM USAGE SUMMARY")
        print("="*60)
        print(f"Total API Calls:    {summary['total_calls']}")
        print(f"Total Input Tokens: {summary['total_input_tokens']:,}")
        print(f"Total Output Tokens:{summary['total_output_tokens']:,}")
        print(f"Total Tokens:       {summary['total_tokens']:,}")
        print(f"Total Cost:         ${summary['total_cost']:.4f}")

        if summary['by_model']:
            print("\nBy Model:")
            for model, stats in summary['by_model'].items():
                print(f"  {model}:")
                print(f"    Calls:        {stats['calls']}")
                print(f"    Input:        {stats['input_tokens']:,} tokens")
                print(f"    Output:       {stats['output_tokens']:,} tokens")
                print(f"    Cost:         ${stats['cost']:.4f}")

        print("="*60 + "\n")

    def reset(self):
        """Clear all usage records."""
        self.records.clear()
        self._totals_by_model.clear()
        logger.info("Usage tracker reset")
