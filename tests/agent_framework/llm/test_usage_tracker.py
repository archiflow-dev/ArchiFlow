"""
Tests for UsageTracker.
"""
import unittest
from datetime import datetime

from src.agent_framework.llm.usage_tracker import UsageTracker, UsageRecord
from src.agent_framework.llm.model_config import ModelConfig


class TestUsageRecord(unittest.TestCase):
    """Test UsageRecord class."""

    def test_usage_record_creation(self):
        """Test creating a UsageRecord."""
        record = UsageRecord(
            timestamp=datetime.now(),
            model="gpt-4o",
            input_tokens=1000,
            output_tokens=500,
            cost=7.50,
            session_id="session_1"
        )

        self.assertEqual(record.model, "gpt-4o")
        self.assertEqual(record.input_tokens, 1000)
        self.assertEqual(record.output_tokens, 500)
        self.assertEqual(record.cost, 7.50)
        self.assertEqual(record.session_id, "session_1")

    def test_total_tokens_property(self):
        """Test total_tokens property."""
        record = UsageRecord(
            timestamp=datetime.now(),
            model="gpt-4o",
            input_tokens=1000,
            output_tokens=500,
            cost=7.50
        )

        self.assertEqual(record.total_tokens, 1500)


class TestUsageTracker(unittest.TestCase):
    """Test UsageTracker class."""

    def setUp(self):
        """Set up test fixtures."""
        self.tracker = UsageTracker()

        self.model_config = ModelConfig(
            model_name="test-model",
            context_window=100_000,
            max_output_tokens=4_096,
            cost_per_1k_input=2.50,
            cost_per_1k_output=10.00
        )

    def test_initial_state(self):
        """Test tracker initial state."""
        self.assertEqual(len(self.tracker.records), 0)
        self.assertEqual(self.tracker._totals_by_model, {})

    def test_record_usage(self):
        """Test recording a single usage."""
        record = self.tracker.record(
            model_config=self.model_config,
            input_tokens=1000,
            output_tokens=500,
            session_id="session_1"
        )

        # Check record
        self.assertEqual(record.model, "test-model")
        self.assertEqual(record.input_tokens, 1000)
        self.assertEqual(record.output_tokens, 500)
        self.assertEqual(record.session_id, "session_1")
        # Cost: (1000/1000 * 2.50) + (500/1000 * 10.00) = 2.50 + 5.00 = 7.50
        self.assertEqual(record.cost, 7.50)

        # Check tracker state
        self.assertEqual(len(self.tracker.records), 1)

    def test_record_multiple_usages(self):
        """Test recording multiple usages."""
        self.tracker.record(self.model_config, 1000, 500, "session_1")
        self.tracker.record(self.model_config, 2000, 800, "session_1")
        self.tracker.record(self.model_config, 1500, 600, "session_2")

        self.assertEqual(len(self.tracker.records), 3)

    def test_get_summary(self):
        """Test getting overall summary."""
        self.tracker.record(self.model_config, 1000, 500)
        self.tracker.record(self.model_config, 2000, 800)

        summary = self.tracker.get_summary()

        self.assertEqual(summary["total_calls"], 2)
        self.assertEqual(summary["total_input_tokens"], 3000)
        self.assertEqual(summary["total_output_tokens"], 1300)
        self.assertEqual(summary["total_tokens"], 4300)
        # Cost: (1000+2000)/1000*2.50 + (500+800)/1000*10.00 = 7.50 + 13.00 = 20.50
        self.assertAlmostEqual(summary["total_cost"], 20.50, places=2)

    def test_get_summary_by_model(self):
        """Test summary grouped by model."""
        model1 = ModelConfig("model-1", 100_000, 4_096, 1.00, 2.00)
        model2 = ModelConfig("model-2", 100_000, 4_096, 3.00, 6.00)

        self.tracker.record(model1, 1000, 500)
        self.tracker.record(model2, 2000, 800)
        self.tracker.record(model1, 1500, 600)

        summary = self.tracker.get_summary()

        # Check by_model breakdown
        self.assertIn("model-1", summary["by_model"])
        self.assertIn("model-2", summary["by_model"])

        model1_stats = summary["by_model"]["model-1"]
        self.assertEqual(model1_stats["calls"], 2)
        self.assertEqual(model1_stats["input_tokens"], 2500)  # 1000 + 1500
        self.assertEqual(model1_stats["output_tokens"], 1100)  # 500 + 600

        model2_stats = summary["by_model"]["model-2"]
        self.assertEqual(model2_stats["calls"], 1)
        self.assertEqual(model2_stats["input_tokens"], 2000)
        self.assertEqual(model2_stats["output_tokens"], 800)

    def test_get_session_summary(self):
        """Test getting summary for a specific session."""
        self.tracker.record(self.model_config, 1000, 500, session_id="session_1")
        self.tracker.record(self.model_config, 2000, 800, session_id="session_1")
        self.tracker.record(self.model_config, 1500, 600, session_id="session_2")

        session1_summary = self.tracker.get_session_summary("session_1")

        self.assertEqual(session1_summary["session_id"], "session_1")
        self.assertEqual(session1_summary["total_calls"], 2)
        self.assertEqual(session1_summary["total_input_tokens"], 3000)
        self.assertEqual(session1_summary["total_output_tokens"], 1300)
        self.assertEqual(session1_summary["total_tokens"], 4300)

    def test_get_session_summary_no_records(self):
        """Test getting summary for session with no records."""
        summary = self.tracker.get_session_summary("nonexistent_session")

        self.assertEqual(summary["session_id"], "nonexistent_session")
        self.assertEqual(summary["total_calls"], 0)
        self.assertEqual(summary["total_cost"], 0.0)

    def test_reset(self):
        """Test resetting the tracker."""
        self.tracker.record(self.model_config, 1000, 500)
        self.tracker.record(self.model_config, 2000, 800)

        self.assertEqual(len(self.tracker.records), 2)

        self.tracker.reset()

        self.assertEqual(len(self.tracker.records), 0)
        self.assertEqual(self.tracker._totals_by_model, {})

    def test_print_summary(self):
        """Test print_summary doesn't crash."""
        self.tracker.record(self.model_config, 1000, 500)
        self.tracker.record(self.model_config, 2000, 800)

        # Just ensure it doesn't crash
        try:
            self.tracker.print_summary()
        except Exception as e:
            self.fail(f"print_summary raised {e}")


if __name__ == "__main__":
    unittest.main()
