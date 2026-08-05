"""Tests for the generated-pdfs branch layout."""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location(
    "site_pdf_snapshot",
    ROOT / "scripts/stage-site-pdfs.py",
)

assert spec and spec.loader
staging = importlib.util.module_from_spec(spec)
spec.loader.exec_module(staging)


class PdfSnapshotTests(unittest.TestCase):
    def test_complete_snapshot_is_staged_with_fixed_names(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pdf = root / "snapshot" / "pdf"
            pdf.mkdir(parents=True)
            (pdf / "alpha.pdf").write_bytes(b"alpha")
            (pdf / "hidden.pdf").write_bytes(b"hidden")
            destination = root / "site"
            with mock.patch.object(
                staging, "registered_and_site_slugs",
                return_value=({"alpha", "hidden"}, {"alpha"}),
            ):
                staging.stage(root / "snapshot", destination)
            self.assertEqual([path.name for path in destination.iterdir()], ["alpha.pdf"])

    def test_snapshot_rejects_unknown_empty_and_non_pdf_entries(self):
        cases = (
            ("unknown.pdf", b"pdf", "unknown snapshot PDF slug"),
            ("alpha.pdf", b"", "snapshot PDF is empty"),
            ("notes.txt", b"x", "unknown snapshot entry"),
        )

        for name, data, message in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                pdf = root / "snapshot" / "pdf"
                pdf.mkdir(parents=True)
                (pdf / name).write_bytes(data)
                with mock.patch.object(
                    staging,
                    "registered_and_site_slugs",
                    return_value=({"alpha"}, {"alpha"}),
                ):

                    with self.assertRaisesRegex(ValueError, message):
                        staging.stage(root / "snapshot", root / "site")

    def test_destination_is_cleaned(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pdf = root / "snapshot" / "pdf"
            pdf.mkdir(parents=True)
            (pdf / "alpha.pdf").write_bytes(b"new")
            destination = root / "site"
            destination.mkdir()
            (destination / "stale.pdf").write_bytes(b"old")
            with mock.patch.object(
                staging,
                "registered_and_site_slugs",
                return_value=({"alpha"}, {"alpha"}),
            ):

                staging.stage(root / "snapshot", destination)
            self.assertEqual([path.name for path in destination.iterdir()], ["alpha.pdf"])

    def test_incomplete_snapshot_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "snapshot" / "pdf").mkdir(parents=True)
            with mock.patch.object(
                staging, "registered_and_site_slugs",
                return_value=({"alpha"}, {"alpha"}),
            ):
                with self.assertRaisesRegex(ValueError, "missing PDF artifact.*alpha"):
                    staging.stage(root / "snapshot", root / "site")


if __name__ == "__main__":
    unittest.main()
