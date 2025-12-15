import unittest
import os
import tempfile
import sys

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../src')))

from agent_framework.config.env_loader import load_env

class TestEnvLoader(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.env_file = os.path.join(self.test_dir, ".env")
        
    def tearDown(self):
        import shutil
        shutil.rmtree(self.test_dir)
        # Clean up env vars
        if "TEST_VAR" in os.environ:
            del os.environ["TEST_VAR"]
        if "TEST_QUOTED" in os.environ:
            del os.environ["TEST_QUOTED"]

    def test_load_valid_env(self):
        with open(self.env_file, "w") as f:
            f.write("TEST_VAR=test_value\n")
            f.write("# This is a comment\n")
            f.write("TEST_QUOTED=\"quoted value\"\n")
            
        load_env(self.env_file)
        
        self.assertEqual(os.environ.get("TEST_VAR"), "test_value")
        self.assertEqual(os.environ.get("TEST_QUOTED"), "quoted value")

    def test_no_override(self):
        os.environ["TEST_VAR"] = "original"
        
        with open(self.env_file, "w") as f:
            f.write("TEST_VAR=new_value\n")
            
        load_env(self.env_file)
        
        self.assertEqual(os.environ.get("TEST_VAR"), "original")

    def test_missing_file_silent(self):
        # Should not raise exception
        load_env("nonexistent.env")

if __name__ == '__main__':
    unittest.main()
