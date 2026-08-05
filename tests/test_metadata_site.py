"""Metadata ownership and deterministic site generation tests."""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import book_manifest as books_module  # noqa: E402

spec = importlib.util.spec_from_file_location(
    "site_generator",
    REPO_ROOT / "scripts" / "generate-site-data.py",
)

assert spec and spec.loader
site_generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(site_generator)


class ManifestFixture(unittest.TestCase):
    def make_repository(
        self,
        records: list[dict],
        metadata: dict[str, str] | None = None,
    ) -> tuple[Path, Path]:

        root = Path(self.directory.name)
        for record in records:
            slug = record["slug"]
            book_dir = root / "books" / slug
            book_dir.mkdir(parents=True, exist_ok=True)
            (book_dir / "book.tex").write_text("", encoding="utf-8")
            text = (metadata or {}).get(slug, rf"\newcommand{{\bookslug}}{{{slug}}}" + "\n")
            (book_dir / "metadata.tex").write_text(text, encoding="utf-8")
        manifest = {
            "schema_version": 1,
            "defaults": {"build": True, "check": True, "release": False, "site": False},
            "books": records,
        }
        path = root / "books.yml"
        path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
        return root, path

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self.directory.cleanup()


class ManifestMetadataTests(ManifestFixture):
    def base(self, slug: str, **overrides: object) -> dict:
        record = {"slug": slug, "title": slug.title(), "status": "draft", "order": 10}
        record.update(overrides)
        return record

    def load(self, root: Path, path: Path) -> dict:
        return books_module.load_manifest(path, root)

    def test_site_filter_and_order_then_slug(self) -> None:
        records = [
            self.base("zeta", order=20, site=False),
            self.base("beta", order=10, site=True),
            self.base("alpha", order=10, site=True),
        ]
        root, path = self.make_repository(records)
        manifest = self.load(root, path)
        self.assertEqual([book["slug"] for book in manifest["books"]], ["alpha", "beta", "zeta"])
        self.assertEqual([book["slug"] for book in site_generator.site_books(manifest)], ["alpha", "beta"])

    def test_unknown_status_is_rejected(self) -> None:
        root, path = self.make_repository([self.base("alpha", status="unknown")])
        with self.assertRaisesRegex(ValueError, "invalid status"):
            self.load(root, path)

    def test_matching_bookslug_succeeds(self) -> None:
        root, path = self.make_repository([self.base("alpha")])
        self.load(root, path)

    def test_mismatching_bookslug_fails(self) -> None:
        root, path = self.make_repository([self.base("alpha")], {"alpha": r"\newcommand{\bookslug}{beta}" + "\n"})
        with self.assertRaisesRegex(ValueError, "metadata bookslug"):
            self.load(root, path)

    def test_missing_or_multiple_bookslug_fails(self) -> None:
        for text in ("", r"\newcommand{\bookslug}{alpha}" + "\n" + r"\newcommand{\bookslug}{alpha}" + "\n"):
            with self.subTest(text=text):
                root, path = self.make_repository([self.base("alpha")], {"alpha": text})
                with self.assertRaisesRegex(ValueError, "exactly one bookslug"):
                    self.load(root, path)

    def test_tex_formatted_title_is_advisory_not_fatal(self) -> None:
        record = self.base("analysis", title="Analysis I & II")
        metadata = (
            r"\newcommand{\bookslug}{analysis}"
            "\n"
            r"\title{Analysis \Romannum{1} \& \Romannum{2}}"
            "\n"
            r"\hypersetup{pdftitle={Analysis \Romannum{1} \& \Romannum{2}}}"
            "\n"
        )

        root, path = self.make_repository([record], {"analysis": metadata})
        with mock.patch.object(books_module, "REPO_ROOT", root):
            manifest = books_module.load_manifest(path)
            self.assertEqual(books_module.metadata_title_warnings(manifest), [])


class SiteGenerationTests(unittest.TestCase):
    def manifest(self) -> dict:
        return {"books": [
            {"slug": "alpha", "title": "Alpha", "status": "review", "order": 10, "site": True},
            {"slug": "beta", "title": "Beta", "short_title": "B", "status": "archived", "order": 20, "site": True},
            {"slug": "hidden", "title": "Hidden", "status": "draft", "order": 30, "site": False},
        ]}

    def write_narrative(self, directory: Path, slug: str, body: str = "Narrative text.\n") -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{slug}.md"
        path.write_text(f"---\nlayout: book\nslug: {slug}\n---\n\n{body}", encoding="utf-8")
        return path

    def test_status_mapping_and_short_title_fallback(self) -> None:
        books = site_generator.site_books(self.manifest())
        self.assertEqual([book["status_label"] for book in books], ["In Review", "Archived"])
        self.assertEqual([book["display_short_title"] for book in books], ["Alpha", "B"])
        self.assertEqual([book["slug"] for book in books], ["alpha", "beta"])

    def test_all_status_labels(self) -> None:
        self.assertEqual(site_generator.STATUS_LABELS, {
            "draft": "Draft", "review": "In Review", "published": "Published", "archived": "Archived",
        })

    def test_deterministic_and_narrative_survives(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            alpha = self.write_narrative(directory, "alpha", "Hand-written alpha.\n")
            self.write_narrative(directory, "beta")
            before = alpha.read_text(encoding="utf-8")
            first = site_generator.render_site_data(self.manifest(), directory)
            second = site_generator.render_site_data(self.manifest(), directory)
            self.assertEqual(first, second)
            self.assertEqual(alpha.read_text(encoding="utf-8"), before)

    def test_missing_and_extra_narratives_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            self.write_narrative(directory, "alpha")
            with self.assertRaisesRegex(ValueError, "missing site narrative"):
                site_generator.render_site_data(self.manifest(), directory)
            self.write_narrative(directory, "beta")
            self.write_narrative(directory, "extra")
            with self.assertRaisesRegex(ValueError, "unregistered or site-disabled"):
                site_generator.render_site_data(self.manifest(), directory)

    def test_stale_output_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "books.yml"
            output.write_text("stale\n", encoding="utf-8")
            with (
                mock.patch.object(
                    site_generator,
                    "load_manifest",
                    return_value={},
                ),
                mock.patch.object(
                    site_generator,
                    "render_site_data",
                    return_value="fresh\n",
                ),
            ):

                self.assertEqual(site_generator.generate(check=True, output=output), 1)
                self.assertEqual(output.read_text(encoding="utf-8"), "stale\n")
                self.assertEqual(site_generator.generate(check=False, output=output), 0)
                self.assertEqual(site_generator.generate(check=True, output=output), 0)


if __name__ == "__main__":
    unittest.main()
