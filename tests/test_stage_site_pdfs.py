"""Tests for staging site PDFs from artifact and snapshot layouts."""
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
    "site_pdf_staging", ROOT / "scripts/stage-site-pdfs.py"
)
assert spec and spec.loader
site_pdf_staging = importlib.util.module_from_spec(spec)
spec.loader.exec_module(site_pdf_staging)

class SnapshotLayoutTests(unittest.TestCase):
    def test_complete_snapshot_is_staged_with_fixed_names(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pdf = root / "snapshot" / "pdf"
            pdf.mkdir(parents=True)
            (pdf / "alpha.pdf").write_bytes(b"alpha")
            (pdf / "hidden.pdf").write_bytes(b"hidden")
            destination = root / "site"
            with mock.patch.object(
                site_pdf_staging, "registered_and_site_slugs",
                return_value=({"alpha", "hidden"}, {"alpha"}),
            ):
                site_pdf_staging.stage(root / "snapshot", destination)
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
                    site_pdf_staging,
                    "registered_and_site_slugs",
                    return_value=({"alpha"}, {"alpha"}),
                ):

                    with self.assertRaisesRegex(ValueError, message):
                        site_pdf_staging.stage(root / "snapshot", root / "site")

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
                site_pdf_staging,
                "registered_and_site_slugs",
                return_value=({"alpha"}, {"alpha"}),
            ):

                site_pdf_staging.stage(root / "snapshot", destination)
            self.assertEqual([path.name for path in destination.iterdir()], ["alpha.pdf"])

    def test_incomplete_snapshot_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "snapshot" / "pdf").mkdir(parents=True)
            with mock.patch.object(
                site_pdf_staging, "registered_and_site_slugs",
                return_value=({"alpha"}, {"alpha"}),
            ):
                with self.assertRaisesRegex(ValueError, "missing PDF artifact.*alpha"):
                    site_pdf_staging.stage(root / "snapshot", root / "site")


class ArtifactLayoutTests(unittest.TestCase):
    def stage(self, site_slugs, registered=None, artifacts=None):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        downloaded = root / "downloaded"
        destination = root / "destination"
        downloaded.mkdir()
        for slug, files in (artifacts or {}).items():
            artifact = downloaded / f"{slug}-pdf"
            artifact.mkdir()
            for name, contents in files.items():
                (artifact / name).write_bytes(contents)
        registered = set(site_slugs) if registered is None else set(registered)
        selection = (registered, set(site_slugs))
        with mock.patch.object(
            site_pdf_staging, "registered_and_site_slugs", return_value=selection
        ):
            site_pdf_staging.stage(downloaded, destination)
        return destination

    def test_only_site_pdf_is_staged_and_named_by_slug(self):
        destination = self.stage(
            {"public"}, {"public", "hidden"},
            {"public": {"book.pdf": b"pdf"}, "hidden": {"book.pdf": b"hidden"}},
        )
        self.assertEqual([path.name for path in destination.iterdir()], ["public.pdf"])
        self.assertEqual((destination / "public.pdf").read_bytes(), b"pdf")

    def test_site_disabled_artifact_contents_are_ignored(self):
        destination = self.stage(set(), {"hidden"}, {"hidden": {"unexpected.txt": b""}})
        self.assertEqual(list(destination.iterdir()), [])

    def test_duplicate_site_artifact_fails(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        downloaded = root / "downloaded"
        destination = root / "destination"
        artifact = downloaded / "public-pdf"
        artifact.mkdir(parents=True)
        (artifact / "book.pdf").write_bytes(b"pdf")
        original_iterdir = Path.iterdir

        def repeated_artifact(path):
            if path == downloaded:
                return iter((artifact, artifact))
            return original_iterdir(path)

        with mock.patch.object(
            site_pdf_staging, "registered_and_site_slugs",
            return_value=({"public"}, {"public"}),
        ), mock.patch.object(Path, "iterdir", repeated_artifact):
            with self.assertRaisesRegex(ValueError, "duplicate PDF artifact slug: public"):
                site_pdf_staging.stage(downloaded, destination)

    def test_missing_site_artifact_fails(self):
        with self.assertRaisesRegex(ValueError, "missing PDF artifact.*public"):
            self.stage({"public"}, {"public"})

    def test_unregistered_pdf_artifact_fails(self):
        with self.assertRaisesRegex(ValueError, "unknown PDF artifact slug: unknown"):
            self.stage(set(), set(), {"unknown": {"book.pdf": b"pdf"}})

    def test_site_artifact_must_contain_only_book_pdf(self):
        with self.assertRaisesRegex(ValueError, "must contain only book.pdf"):
            self.stage({"public"}, {"public"}, {"public": {"book.pdf": b"pdf", "extra": b"x"}})

    def test_empty_site_pdf_fails(self):
        with self.assertRaisesRegex(ValueError, "artifact PDF is empty"):
            self.stage({"public"}, {"public"}, {"public": {"book.pdf": b""}})

    def test_no_site_books_succeeds_with_empty_destination(self):
        destination = self.stage(set(), set())
        self.assertTrue(destination.is_dir())
        self.assertEqual(list(destination.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
