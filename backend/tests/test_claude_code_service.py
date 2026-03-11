import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.claude_code_service import ClaudeCodeService


class ClaudeCodeServiceTest(unittest.TestCase):
    def setUp(self):
        self.workspace_root = Path(__file__).resolve().parents[2]
        self.service = ClaudeCodeService()
        self.service.workspace_root = self.workspace_root
        self.service.binary = "claude"
        self.service.permission_mode = "bypassPermissions"
        self.service.default_allowed_tools = ["Read", "Edit", "Bash"]
        self.service.default_system_prompt = "System prompt"

    def test_resolve_working_directory_accepts_workspace_child(self):
        resolved = self.service.resolve_working_directory("backend")
        self.assertEqual(resolved, self.workspace_root / "backend")

    def test_resolve_working_directory_rejects_escape(self):
        with self.assertRaises(ValueError):
            self.service.resolve_working_directory("../..")

    def test_build_command_includes_server_defaults(self):
        command = self.service.build_command(
            "Inspect the backend",
            append_system_prompt="Only summarize changed files.",
            max_budget_usd=2.5,
        )

        self.assertIn("--permission-mode", command)
        self.assertIn("bypassPermissions", command)
        self.assertIn("--allowedTools", command)
        self.assertIn("Read,Edit,Bash", command)
        self.assertIn("--append-system-prompt", command)
        self.assertIn("--max-budget-usd", command)
        self.assertIn("2.5", command)

    def test_extract_result_text_falls_back_cleanly(self):
        text = self.service._extract_result_text(None, fallback="plain output")
        self.assertEqual(text, "plain output")


if __name__ == "__main__":
    unittest.main()
