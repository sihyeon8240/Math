"""Regression tests for strict release packaging."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class PackageBookTests(unittest.TestCase):
    def test_overfull_log_prevents_release_pdf(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scripts = root / "scripts"
            scripts.mkdir()
            shutil.copy2(ROOT / "scripts/package-book.sh", scripts / "package-book.sh")
            shutil.copy2(ROOT / "scripts/check-log.py", scripts / "check-log.py")
            (scripts / "books.py").write_text(
                "import sys\nif sys.argv[1] == 'version': print('1.2.3')\n",
                encoding="utf-8",
            )
            build = root / "build" / "alpha"
            build.mkdir(parents=True)
            (build / "book.pdf").write_bytes(b"pdf")
            (build / "book.log").write_text(
                "Overfull \\hbox (1.0pt too wide) detected at line 1\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [str(scripts / "package-book.sh"), "alpha", str(root / "release")], cwd=root,
                env={**os.environ, "PYTHON": sys.executable},
                capture_output=True, text=True, check=False,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("error: overfull box", result.stderr)
            self.assertFalse((root / "release" / "alpha-v1.2.3.pdf").exists())

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
