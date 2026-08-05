"""README book-table generation tests."""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

spec = importlib.util.spec_from_file_location(
    "readme_generator", REPO_ROOT / "scripts" / "generate-readme-books.py"
)
assert spec and spec.loader
readme_generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(readme_generator)


class ReadmeBooksTests(unittest.TestCase):
    def manifest(self) -> dict:
        return {"books": [
            {"slug": "alpha", "title": "Alpha | Complete", "short_title": "A",
             "build": False, "check": False, "release": False, "site": False},
            {"slug": "beta", "title": "Beta", "build": True, "check": True,
             "release": True, "site": True},
        ]}

    def readme(self, body: str = "old table") -> str:
        return (
            "# Before\r\n\r\n"
            f"{readme_generator.BEGIN_MARKER}{body}"
            f"{readme_generator.END_MARKER}"
            "\r\n\r\nAfter\r\n"
        )

    def test_render_uses_normalized_order_title_and_all_books(self) -> None:
        table = readme_generator.render_books_table(self.manifest())
        self.assertLess(table.index("alpha"), table.index("beta"))
        self.assertIn("Alpha \\| Complete", table)
        self.assertNotIn("| A |", table)
        self.assertIn("make book BOOK=alpha", table)
        self.assertIn("make book BOOK=beta", table)

    def test_render_is_deterministic(self) -> None:
        self.assertEqual(
            readme_generator.render_books_table(self.manifest()),
            readme_generator.render_books_table(self.manifest()),
        )

    def test_replacement_preserves_everything_outside_markers(self) -> None:
        current = self.readme("\r\nOLD\r\n")
        updated = readme_generator.replace_generated_books(current, "NEW")
        begin_end = current.index(readme_generator.BEGIN_MARKER) + len(
            readme_generator.BEGIN_MARKER
        )
        end = current.index(readme_generator.END_MARKER)
        self.assertEqual(updated[:begin_end], current[:begin_end])
        self.assertEqual(updated[updated.index(readme_generator.END_MARKER):], current[end:])

    def test_generate_and_check_modes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "README.md"
            path.write_bytes(self.readme().encode("utf-8"))
            stale = path.read_bytes()
            self.assertEqual(readme_generator.generate(
                check=True, readme_path=path, manifest=self.manifest()), 1)
            self.assertEqual(path.read_bytes(), stale)
            self.assertEqual(readme_generator.generate(
                readme_path=path, manifest=self.manifest()), 0)
            fresh = path.read_bytes()
            self.assertEqual(readme_generator.generate(
                check=True, readme_path=path, manifest=self.manifest()), 0)
            self.assertEqual(path.read_bytes(), fresh)

    def test_missing_begin_marker_fails(self) -> None:
        with self.assertRaisesRegex(ValueError, "BEGIN.*found 0"):
            readme_generator.replace_generated_books(readme_generator.END_MARKER, "table")

    def test_missing_end_marker_fails(self) -> None:
        with self.assertRaisesRegex(ValueError, "END.*found 0"):
            readme_generator.replace_generated_books(readme_generator.BEGIN_MARKER, "table")

    def test_duplicate_markers_fail(self) -> None:
        cases = (
            readme_generator.BEGIN_MARKER * 2 + readme_generator.END_MARKER,
            readme_generator.BEGIN_MARKER + readme_generator.END_MARKER * 2,
        )
        for readme in cases:
            with self.subTest(readme=readme), self.assertRaisesRegex(ValueError, "exactly one"):
                readme_generator.replace_generated_books(readme, "table")

    def test_reversed_markers_fail(self) -> None:
        with self.assertRaisesRegex(ValueError, "wrong order"):
            readme_generator.replace_generated_books(
                readme_generator.END_MARKER + readme_generator.BEGIN_MARKER, "table")


if __name__ == "__main__":
    unittest.main()
