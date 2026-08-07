"""Static contracts for the release workflow."""
from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class ReleaseWorkflowTests(unittest.TestCase):
    def test_release_workflow_invariants(self) -> None:
        publish = (ROOT / "scripts" / "publish-release.sh").read_text(encoding="utf-8")
        plan = (ROOT / "scripts" / "release-plan.sh").read_text(encoding="utf-8")
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

        self.assertIn('[[ "$head_commit" != "$remote_main_commit" ]]', publish)
        self.assertIn("git tag -a", publish)
        self.assertNotIn("git push origin main", publish)
        self.assertNotIn("--clobber", publish)
        self.assertIn("timeout 15m gh run watch", publish)
        self.assertNotIn("all-books-v", plan)
        self.assertNotRegex(makefile, r"(?m)^dist:")


if __name__ == "__main__":
    unittest.main()
