"""Regression tests for scripts/check-log.py."""
from __future__ import annotations
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CHECK_LOG = REPO_ROOT / "scripts" / "check-log.py"

class CheckLogTests(unittest.TestCase):
    def run_checker(self, text: str, *, strict: bool = False) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "book.log"
            log.write_text(text, encoding="utf-8")
            command = [sys.executable, str(CHECK_LOG), str(log)]
            if strict:
                command.append("--strict")
            return subprocess.run(command, capture_output=True, text=True, check=False)

    def assert_failure(self, text: str, diagnostic: str) -> None:
        result = self.run_checker(text)
        self.assertEqual(result.returncode, 1)
        self.assertIn(diagnostic, result.stderr)

    def test_undefined_reference(self) -> None:
        self.assert_failure("LaTeX Warning: Reference `x' undefined.\n", "undefined reference")

    def test_undefined_citation(self) -> None:
        self.assert_failure("LaTeX Warning: Citation `x' undefined.\n", "undefined citation")

    def test_multiply_defined_label(self) -> None:
        self.assert_failure("LaTeX Warning: Label `x' multiply defined.\n", "multiply defined label")

    def test_missing_character(self) -> None:
        self.assert_failure("Missing character: There is no x in font nullfont!\n", "missing character")

    def test_fatal_error(self) -> None:
        self.assert_failure("! Undefined control sequence.\n", "fatal LaTeX error")

    def test_rerun_warning(self) -> None:
        self.assert_failure("LaTeX Warning: Rerun to get cross-references right.\n", "rerun required")

    def test_rerunfilecheck_package_description_is_not_a_warning(self) -> None:
        result = self.run_checker("Package: rerunfilecheck 2022-07-10 v1.10 Rerun checks\n")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")

    def test_overfull_box_warns_by_default(self) -> None:
        result = self.run_checker("Overfull \\hbox (1.0pt too wide) detected at line 1\n")
        self.assertEqual(result.returncode, 0)
        self.assertIn("warning: overfull box", result.stderr)

    def test_overfull_box_fails_in_strict_mode(self) -> None:
        result = self.run_checker("Overfull \\vbox (1.0pt too high) detected at line 1\n", strict=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("error: overfull box", result.stderr)

if __name__ == "__main__":
    unittest.main()
