import unittest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))
from agent_framework.context import TopicContext

class TestTopicContext(unittest.TestCase):
    def test_default_context(self):
        session_id = "test_session"
        context = TopicContext.default(session_id)
        
        self.assertEqual(context.agent_topic, "agent.test_session")
        self.assertEqual(context.runtime_topic, "runtime.test_session")
        self.assertEqual(context.client_topic, "client.test_session")

    def test_custom_context(self):
        context = TopicContext(
            agent_topic="my.agent",
            runtime_topic="my.runtime",
            client_topic="my.client"
        )
        
        self.assertEqual(context.agent_topic, "my.agent")
        self.assertEqual(context.runtime_topic, "my.runtime")
        self.assertEqual(context.client_topic, "my.client")

if __name__ == '__main__':
    unittest.main()
