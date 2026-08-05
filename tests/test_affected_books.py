"""Change-impact planning tests."""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("affected_books", ROOT / "scripts/affected-books.py")
assert spec and spec.loader
affected = importlib.util.module_from_spec(spec)
spec.loader.exec_module(affected)


class AffectedBookTests(unittest.TestCase):
    manifest = {"schema_version": 1, "books": [
        {"slug": "alpha", "build": True},
        {"slug": "beta", "build": True},
        {"slug": "disabled", "build": False},
    ]}
    deps = {
        "alpha": {"books/alpha/book.tex", "books/alpha/metadata.tex",
                  "books/alpha/references.bib", "books/alpha/chapters/one.tex",
                  "common/styles/alpha.sty", "common/bibliography/shared.bib"},
        "beta": {"books/beta/book.tex", "common/styles/beta.sty"},
    }

    def plan(self, paths, old=None):
        with mock.patch.object(affected, "load_manifest", return_value=self.manifest), \
             mock.patch.object(affected, "dependencies", side_effect=lambda slug: self.deps[slug]):
            return affected.plan(paths, old)

    def test_book_inputs_select_one_book(self):
        for path in ("books/alpha/chapters/one.tex", "books/alpha/metadata.tex",
                     "books/alpha/references.bib"):
            with self.subTest(path=path):
                self.assertEqual(self.plan([path])["book"], ["alpha"])

    def test_common_style_selects_only_actual_consumer(self):
        self.assertEqual(self.plan(["common/styles/alpha.sty"])["book"], ["alpha"])

    def test_common_bibliography_selects_only_actual_consumer(self):
        self.assertEqual(self.plan(["common/bibliography/shared.bib"])["book"], ["alpha"])

    def test_ci_only_helpers_select_no_books(self):
        for path in ("scripts/snapshot-base.sh", "scripts/check-image-tag.sh"):
            with self.subTest(path=path):
                self.assertEqual(self.plan([path])["book"], [])

    def test_site_and_document_only_changes_select_no_books(self):
        for path in ("site/index.html", "README.md", "docs/developer-workflow.md", "books/alpha/README.md"):
            with self.subTest(path=path):
                self.assertEqual(self.plan([path])["book"], [])

    def test_multiple_books(self):
        self.assertEqual(
            self.plan(["books/alpha/book.tex", "books/beta/book.tex"])["book"],
            ["alpha", "beta"],
        )

    def test_build_infrastructure_and_unknown_fall_back_to_all(self):
        for path in ("latexmkrc", "new-build-input.cfg"):
            with self.subTest(path=path):
                self.assertEqual(self.plan([path])["book"], ["alpha", "beta"])

    def test_manifest_addition_selects_new_build_book(self):
        old = {"schema_version": 1, "books": [{"slug": "beta", "build": True}]}
        self.assertEqual(self.plan(["books.yml"], old)["book"], ["alpha"])

    def test_manifest_schema_change_falls_back_to_all(self):
        old = {"schema_version": 0, "books": [{"slug": "alpha", "build": True}, {"slug": "beta", "build": True}]}
        self.assertEqual(self.plan(["books.yml"], old)["book"], ["alpha", "beta"])

    def test_manifest_site_only_change_does_not_build(self):
        old = {"schema_version": 1, "books": [
            {"slug": "alpha", "build": True}, {"slug": "beta", "build": True}
        ]}
        result = self.plan(["books.yml"], old)
        self.assertEqual(result["book"], [])
        self.assertTrue(result["site_changed"])

    def test_deleted_or_renamed_book_uses_safe_fallback(self):
        old = {"schema_version": 1, "books": [{"slug": "old-alpha", "build": True}, {"slug": "beta", "build": True}]}
        self.assertEqual(
            self.plan(["books.yml", "books/old-alpha/book.tex"], old)["book"],
            ["alpha", "beta"],
        )

    def test_consecutive_push_planner_uses_cumulative_snapshot_diff(self):
        with mock.patch.object(affected, "git_output", return_value="books/alpha/book.tex\n") as output:
            self.assertEqual(affected.changed_paths("snapshot-sha", "latest-sha"), ["books/alpha/book.tex"])
        output.assert_called_once_with("diff", "--name-only", "--diff-filter=ACDMRTUXB", "snapshot-sha", "latest-sha")

    def test_resolver_tracks_common_bibliography_and_package(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "books" / "alpha" / "book.tex"
            source.parent.mkdir(parents=True)
            (root / "common" / "bibliography").mkdir(parents=True)
            (root / "common" / "styles").mkdir(parents=True)
            (root / "common" / "bibliography" / "shared.bib").write_text("", encoding="utf-8")
            (root / "common" / "styles" / "shared.sty").write_text("", encoding="utf-8")
            with mock.patch.object(affected, "ROOT", root):
                self.assertEqual(
                    affected._resolve_tex(
                        "shared",
                        source,
                        "bibliography",
                    ),
                    [
                        (
                            root
                            / "common"
                            / "bibliography"
                            / "shared.bib"
                        ).resolve()
                    ],
                )
                self.assertEqual(
                    affected._resolve_tex(
                        "shared",
                        source,
                        "RequirePackage",
                    ),
                    [
                        (
                            root
                            / "common"
                            / "styles"
                            / "shared.sty"
                        ).resolve()
                    ],
                )


    def test_empty_change_has_empty_matrix(self):
        self.assertEqual(self.plan([])["count"], 0)

    def test_manual_or_missing_comparison_builds_all(self):
        self.assertEqual(self.plan(None)["book"], ["alpha", "beta"])


if __name__ == "__main__":
    unittest.main()
