"""Regression tests for architecture policy validation."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location(
    "check_architecture", ROOT / "scripts/check-architecture.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ArchitectureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.book = self.root / "books/sample"
        chapter = self.book / "chapters/01-start"
        front = self.book / "frontmatter"
        chapter.mkdir(parents=True)
        front.mkdir()
        (self.root / "ARCHITECTURE.md").write_text(
            "contract\n", encoding="utf-8"
        )
        self.write_manifest()
        self.metadata(
            r"\newcommand{\bookslug}{sample}" "\n"
            r"\newcommand{\bookversion}{1.0.0}" "\n"
            r"\newcommand{\bookcoursecode}{MATH}" "\n"
        )
        self.entry(
            r"\addbibresource{references.bib}" "\n"
            r"\include{frontmatter/title-and-copyright}" "\n"
            r"\include{frontmatter/preface}" "\n"
            r"\include{chapters/01-start/index}" "\n"
            r"\nocite{*}" "\n"
        )
        (chapter / "index.tex").write_text(
            r"\chapter{Start}" "\n" r"\input{01-section}" "\n",
            encoding="utf-8",
        )
        (chapter / "01-section.tex").write_text(
            r"\section{One}" "\n", encoding="utf-8"
        )
        (self.book / "references.bib").write_text(
            "@book{one, title={One}}\n", encoding="utf-8"
        )
        (self.book / "README.md").write_text(
            "# Sample\n\nmake book BOOK=sample\n\n1. Start\n",
            encoding="utf-8",
        )
        (front / "title-and-copyright.tex").write_text(
            r"\input{../../common/templates/title-and-copyright}" "\n",
            encoding="utf-8",
        )
        (front / "preface.tex").write_text(
            r"\input{../../common/templates/preface}" "\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_manifest(self, **book_overrides: object) -> None:
        book = {
            "slug": "sample",
            "title": "Sample",
            "status": "draft",
            "order": 10,
        }
        book.update(book_overrides)
        manifest = {
            "schema_version": 1,
            "defaults": {
                "build": True,
                "check": True,
                "release": False,
                "site": False,
            },
            "books": [book],
        }
        (self.root / "books.yml").write_text(
            yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
        )

    def entry(self, text: str) -> None:
        (self.book / "book.tex").write_text(text, encoding="utf-8")

    def metadata(self, text: str) -> None:
        (self.book / "metadata.tex").write_text(text, encoding="utf-8")

    def findings(self):
        return MODULE.validate_repository(self.root)

    def assert_error(self, fragment: str) -> None:
        errors = self.findings().errors
        self.assertTrue(
            any(fragment in error for error in errors), "\n".join(errors)
        )

    def add_chapter(self, name: str, title: str = "Next") -> None:
        chapter = self.book / "chapters" / name
        chapter.mkdir()
        (chapter / "index.tex").write_text(
            rf"\chapter{{{title}}}" + "\n", encoding="utf-8"
        )

    def rename_first_chapter(self, name: str) -> None:
        old = self.book / "chapters/01-start"
        old.rename(self.book / "chapters" / name)
        entry = (self.book / "book.tex").read_text(encoding="utf-8")
        self.entry(entry.replace("chapters/01-start", f"chapters/{name}"))

    def restore_first_chapter(self, name: str) -> None:
        current = self.book / "chapters" / name
        current.rename(self.book / "chapters/01-start")
        entry = (self.book / "book.tex").read_text(encoding="utf-8")
        self.entry(entry.replace(f"chapters/{name}", "chapters/01-start"))

    def test_current_repository_complies(self) -> None:
        findings = MODULE.validate_repository(ROOT)
        self.assertEqual(findings.errors, [], "\n".join(findings.errors))

    def test_minimal_fixture_complies(self) -> None:
        self.assertEqual(self.findings().errors, [])

    def test_two_consecutive_chapters_comply(self) -> None:
        self.add_chapter("02-next")
        entry = (self.book / "book.tex").read_text(encoding="utf-8")
        self.entry(entry + r"\include{chapters/02-next/index}" + "\n")
        self.assertEqual(self.findings().errors, [])

    def test_one_digit_chapter_number_is_error(self) -> None:
        self.rename_first_chapter("1-start")
        self.assert_error("chapter directory name must match")

    def test_three_digit_chapter_number_is_error(self) -> None:
        self.rename_first_chapter("001-start")
        self.assert_error("chapter directory name must match")

    def test_invalid_chapter_name_characters_are_errors(self) -> None:
        for name in ("01-Start", "01-vector_spaces", "01-vector--spaces"):
            with self.subTest(name=name):
                self.rename_first_chapter(name)
                self.assert_error("chapter directory name must match")
                self.restore_first_chapter(name)

    def test_skipped_chapter_number_is_error(self) -> None:
        self.add_chapter("03-third")
        self.assert_error("chapter numbers are 01, 03; expected 01, 02")

    def test_first_chapter_number_must_be_one(self) -> None:
        self.rename_first_chapter("02-start")
        self.assert_error("chapter numbers are 02; expected 01")

    def test_duplicate_chapter_number_is_error(self) -> None:
        self.add_chapter("01-again", "Again")
        self.assert_error("duplicate chapter number 01")

    def test_reversed_chapter_include_order_is_error(self) -> None:
        self.add_chapter("02-next")
        self.entry(
            r"\addbibresource{references.bib}" "\n"
            r"\include{chapters/02-next/index}" "\n"
            r"\include{chapters/01-start/index}" "\n"
            r"\nocite{*}" "\n"
        )
        self.assert_error(
            "chapter include order is 02, 01; expected 01, 02"
        )

    def test_manifest_validation_error_is_reported(self) -> None:
        self.write_manifest(unexpected_field="value")
        self.assert_error("unknown field(s): unexpected_field")

    def test_orphan_section_is_error(self) -> None:
        (self.book / "chapters/01-start/02-orphan.tex").write_text(
            "", encoding="utf-8"
        )
        self.assert_error("orphan section file")

    def test_orphan_chapter_directory_is_error(self) -> None:
        self.add_chapter("02-orphan", "Orphan")
        self.assert_error("orphan chapter directory")

    def test_chapter_target_must_be_index(self) -> None:
        self.entry(
            r"\addbibresource{references.bib}" "\n"
            r"\include{chapters/01-start/01-section}" "\n"
        )
        self.assert_error("chapter target is not index.tex")

    def test_chapter_requires_exactly_one_declaration(self) -> None:
        (self.book / "chapters/01-start/index.tex").write_text(
            r"\chapter{One}" "\n"
            r"\chapter{Two}" "\n"
            r"\input{01-section}" "\n",
            encoding="utf-8",
        )
        self.assert_error("expected one chapter declaration")

    def test_missing_required_bibliography_is_error(self) -> None:
        (self.book / "references.bib").unlink()
        self.assert_error("required bibliography is missing")

    def test_missing_configured_bibliography_is_error(self) -> None:
        self.entry(
            r"\addbibresource{missing.bib}" "\n"
            r"\include{chapters/01-start/index}" "\n"
        )
        self.assert_error("configured bibliography does not exist")

    def test_duplicate_bibliography_key_is_error(self) -> None:
        (self.book / "second.bib").write_text(
            "@book{one, title={Again}}\n", encoding="utf-8"
        )
        self.entry(
            r"\addbibresource{references.bib}" "\n"
            r"\addbibresource{second.bib}" "\n"
            r"\include{chapters/01-start/index}" "\n"
        )
        self.assert_error("duplicate bibliography key 'one'")

    def test_wrapper_drift_is_only_a_warning(self) -> None:
        (self.book / "frontmatter/preface.tex").write_text(
            "custom\n" * 7, encoding="utf-8"
        )
        findings = self.findings()
        self.assertTrue(
            any("template drift" in warning for warning in findings.warnings)
        )
        self.assertFalse(
            any("template drift" in error for error in findings.errors)
        )

    def test_readme_drift_is_only_a_warning(self) -> None:
        (self.book / "README.md").write_text("# Wrong\n", encoding="utf-8")
        findings = self.findings()
        self.assertEqual(findings.errors, [])
        self.assertGreaterEqual(len(findings.warnings), 3)

    def test_course_code_missing_duplicate_and_empty_are_errors(self) -> None:
        base = (
            r"\newcommand{\bookslug}{sample}" "\n"
            r"\newcommand{\bookversion}{1.0.0}" "\n"
        )
        cases = [
            ("", "bookcoursecode"),
            (
                r"\newcommand{\bookcoursecode}{A}" "\n"
                r"\newcommand{\bookcoursecode}{B}" "\n",
                "bookcoursecode",
            ),
            (r"\newcommand{\bookcoursecode}{}" "\n", "course code is empty"),
        ]
        for declaration, diagnostic in cases:
            with self.subTest(declaration=declaration):
                self.metadata(base + declaration)
                self.assert_error(diagnostic)

    def test_duplicate_include_and_input_target_is_error(self) -> None:
        (self.book / "chapters/01-start/index.tex").write_text(
            r"\chapter{Start}" "\n"
            r"\input{01-section}" "\n"
            r"\include{01-section}" "\n",
            encoding="utf-8",
        )
        self.assert_error("duplicate include/input target")


    def set_sections(self, filenames: list[str], inputs: list[str] | None = None) -> None:
        chapter = self.book / "chapters/01-start"
        for path in chapter.glob("*.tex"):
            if path.name != "index.tex":
                path.unlink()
        for filename in filenames:
            (chapter / filename).write_text("body\n", encoding="utf-8")
        targets = inputs if inputs is not None else filenames
        lines = [r"\chapter{Start}"] + [rf"\input{{{target}}}" for target in targets]
        (chapter / "index.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def test_consecutive_single_sections_comply(self) -> None:
        self.set_sections(["01-introduction.tex", "02-main-result.tex"])
        self.assertEqual(self.findings().errors, [])

    def test_split_sections_and_mixed_input_extensions_comply(self) -> None:
        self.set_sections(
            ["01-introduction.tex", "02-main-result-a.tex", "02-main-result-b.tex", "03-applications.tex"],
            ["01-introduction", "02-main-result-a", "02-main-result-b.tex", "03-applications"],
        )
        self.assertEqual(self.findings().errors, [])

    def test_three_part_first_section_compiles_without_overwrite(self) -> None:
        self.set_sections(["01-topic-a.tex", "01-topic-b.tex", "01-topic-c.tex", "02-next-topic.tex"])
        findings = self.findings()
        self.assertEqual(findings.errors, [])
        parsed = MODULE.parse_section_sources(
            list((self.book / "chapters/01-start").glob("0*-*.tex")), "01-start", MODULE.Findings()
        )
        self.assertEqual([(item.number, item.slug, item.part) for item in parsed[:3]],
                         [(1, "topic", "a"), (1, "topic", "b"), (1, "topic", "c")])

    def test_same_number_with_different_slugs_is_error(self) -> None:
        self.set_sections(["01-first-topic-a.tex", "01-second-topic-b.tex"])
        self.assert_error("logical section 01 uses multiple slugs")

    def test_lone_suffixed_part_is_error(self) -> None:
        self.set_sections(["01-topic-a.tex"])
        self.assert_error("must contain at least two parts")

    def test_split_must_start_at_a(self) -> None:
        self.set_sections(["01-topic-b.tex", "01-topic-c.tex"])
        self.assert_error("must start at part a")

    def test_split_part_gap_is_error(self) -> None:
        self.set_sections(["01-topic-a.tex", "01-topic-c.tex"])
        self.assert_error("has a gap; expected part b")

    def test_plain_and_split_files_cannot_mix(self) -> None:
        self.set_sections(["01-topic.tex", "01-topic-b.tex"])
        self.assert_error("mixes an unsuffixed file with split parts")

    def test_split_parts_must_be_adjacent(self) -> None:
        self.set_sections(
            ["01-topic-a.tex", "01-topic-b.tex", "02-other.tex"],
            ["01-topic-a", "02-other", "01-topic-b"],
        )
        self.assert_error("parts of 01-topic must be adjacent")

    def test_split_parts_must_be_in_suffix_order(self) -> None:
        self.set_sections(["01-topic-a.tex", "01-topic-b.tex"],
                          ["01-topic-b", "01-topic-a"])
        self.assert_error("must follow logical section number and part suffix order")

    def test_logical_section_number_gap_is_error(self) -> None:
        self.set_sections(["01-first.tex", "03-third.tex"])
        self.assert_error("logical section numbers are 01, 03; expected 01, 02")

    def test_logical_sections_must_be_in_numeric_order(self) -> None:
        self.set_sections(["01-first.tex", "02-second.tex"], ["02-second", "01-first"])
        self.assert_error("must follow logical section number and part suffix order")

    def test_missing_orphan_and_duplicate_split_inputs_are_errors(self) -> None:
        cases = [
            (["01-topic-a.tex", "01-topic-b.tex"], ["01-topic-a"], "orphan section file"),
            (
                ["01-topic-a.tex", "01-topic-b.tex"],
                ["01-topic-a", "01-topic-b", "01-missing-c"],
                "target does not exist",
            ),
            (
                ["01-topic-a.tex", "01-topic-b.tex"],
                ["01-topic-a", "01-topic-a", "01-topic-b"],
                "duplicate include/input target",
            ),
        ]
        for files, inputs, diagnostic in cases:
            with self.subTest(diagnostic=diagnostic):
                self.set_sections(files, inputs)
                self.assert_error(diagnostic)

    def test_duplicate_part_suffix_is_preserved_and_rejected(self) -> None:
        findings = MODULE.Findings()
        sources = [
            MODULE.SectionSource(Path("01-topic-a.tex"), 1, "topic", "a"),
            MODULE.SectionSource(Path("copy/01-topic-a.tex"), 1, "topic", "a"),
        ]
        MODULE.check_section_sources("01-start", sources, findings)
        self.assertTrue(any("duplicate part suffixes: a" in error
                            for error in findings.errors))

    def test_invalid_section_filename_forms_are_errors(self) -> None:
        for filename in ("01-topic-A.tex", "01-topic--name.tex", "1-topic.tex", "01-section-part-2.tex"):
            with self.subTest(filename=filename):
                self.set_sections([filename])
                self.assertTrue(self.findings().errors)


if __name__ == "__main__":
    unittest.main()
