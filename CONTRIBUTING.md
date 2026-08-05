# Contributing

Thank you for helping improve these textbooks. Keep mathematical-content changes separate from repository maintenance whenever possible.

## Reporting errors

Open a GitHub Issue for typographical errors, mathematical errors, missing citations, broken references, or build failures. Include:

- the textbook and chapter or section;
- the source path or PDF page when known;
- the current statement;
- the proposed correction and mathematical justification.

Use a Pull Request for a focused correction after checking that an Issue does not already cover it. Discuss a new chapter, major reorganization, notation change, or shared-style redesign in an Issue before implementation.

## Development checks

After preparing the dependencies documented in the root README, run `make doctor` to check the environment. Use `make book BOOK=<slug>` for one registered book, `make all` for the manifest bulk-build set, `make check` for repository and LaTeX validation. Book registration and bulk participation are controlled by `books.yml`; do not bypass it. Site publication metadata is also manifest-owned: run `make site` after changing it and `make site-check` before submitting.

The institutional logo is optional for compilation and must not be contributed to the repository. A missing `common/assets/logos/unist-logo.png` is expected in ordinary contributor and CI environments.

## Pull requests

Every PR must compile and should run:

    make check

Describe affected books, validation performed, source or rights information for new material, and any intentionally unresolved warnings. Do not commit build or dist output.

## Copyright and sources

- Do not submit text, problems, solutions, or figures whose copyright status is unclear.
- Cite external sources appropriately when they informed a contribution.
- Distinguish mathematical facts from a particular author's wording or exposition.
- Do not include lecture notes, assignments, examinations, or solution manuals that you do not have permission to publish.
- Confirm the source and publication rights of every new theorem exposition, proof, figure, and exercise.
- AI-generated material must be checked by a human for mathematical correctness, provenance, and licensing. Do not submit unverified generated results verbatim.

## File naming

- Use lowercase English names with hyphens.
- Book slugs contain no year, semester, or instructor name.
- Chapter directories use NN-meaningful-title.
- Chapter entry points are index.tex.
- Section files use NN-meaningful-title.tex.
- Read the actual LaTeX heading before naming a file; do not infer an uncertain title.
- Put shared assets under common/assets and book-only assets under books/<slug>/figures.

## Labels

New labels use:

    <book-prefix>:<kind>:<lowercase-hyphenated-description>

Book prefixes are la, an, and nt. Supported kinds include ch, sec, def, thm, lem, prop, cor, ex, exc, eq, fig, and tab. Examples:

    la:thm:rank-nullity
    an:def:compactness
    nt:thm:fermat-little

Legacy labels are retained until references can be migrated safely in one coordinated change.

See `docs/writing-guide.md` for the section-writing checklist, environment
semantics, examples of the label policy, and the public-PDF behavior of draft
annotations.

## Starting a new textbook

Run `scripts/new-book.sh <slug> "<title>"`. It copies the files in
`common/templates/` and registers the new book in `books.yml` as a draft. The
script never overwrites an existing directory. Assign a label prefix, review the
generated metadata and README, then run:

    make manifest-check
    make book BOOK=<slug>
    make check

CI build and release matrices are generated from `books.yml`; set the manifest
flags deliberately when the new book is ready for those workflows. To publish it on the site, set `site: true`, add a narrative `site/books/<slug>.md` source, run `make site`, and commit the generated data. Do not add status or title fields to the narrative page.

## Releases

Each book version is defined by exactly one `\newcommand{\bookversion}{X.Y.Z}` macro in `books/<slug>/metadata.tex`. Individual release tags use `<slug>-v<bookversion>` and must match it exactly. Official releases include only books with `release: true`.

For an official release, first merge and push the reviewed commit to `main`. Place the authorized institutional logo at `common/assets/logos/unist-logo.png` and run `make publish BOOK=<slug>` from a clean local `main` checkout whose `HEAD` exactly matches fetched `origin/main`. The command never publishes source code. It builds and packages locally in a temporary directory, creates and pushes an annotated tag, waits with a timeout for the matching Actions run, and uploads the PDF and `SHA256SUMS` without overwriting assets. GitHub Actions validates tags and creates Releases but never builds or uploads official release PDFs.

The institutional logo is not tracked. The conditional LaTeX command omits `common/assets/logos/unist-logo.png` when absent, so ordinary contributor and CI builds work without it. The repository owner may place an authorized copy at that path locally, build the PDF, and upload it manually to GitHub Releases. Current GitHub workflows do not download, copy, or decode a logo secret. Never commit the logo or include it in an ordinary source distribution.

## Commit messages

Use a concise scope and imperative description. Examples:

    feat(analysis): add uniform continuity section
    proof(linear-algebra): revise rank-nullity proof
    fix(number-theory): correct Euler theorem hypothesis
    style(common): unify theorem environments
    refactor(analysis): rename chapter source files

## Repository architecture and metadata

Read [ARCHITECTURE.md](ARCHITECTURE.md) before structural or metadata work. `books.yml` owns repository title, short title, status, order, and build/check/release/site participation. `metadata.tex` owns LaTeX-facing titles, course code, version, slug, author declarations, and PDF metadata. README files are human-facing and never canonical; descriptive differences produce warnings, while missing files, invalid slug/version declarations, and broken assembly links fail validation.

## Adding a chapter or section

Create a chapter at `books/<slug>/chapters/NN-descriptive-name/index.tex`. It declares exactly one `\chapter`, includes numbered section files in order, and is included once from `book.tex`. Add sections beside it as `NN-section-name.tex`, containing mathematical content and a section heading but no document setup. Run `make book BOOK=<slug>` and `make check`; checks reject missing targets, duplicate includes, and orphan chapter or section files.

## Completing a new book

After `scripts/new-book.sh <slug> "<title>"`, replace scaffold placeholders and review `book.tex`, `metadata.tex`, `README.md`, `references.bib`, and the initial chapter. Set the version, slug, course code, display/PDF titles, and a unique label prefix. Keep the registry title and README heading aligned and set manifest flags deliberately.

## Releasing a version

Update the single `\bookversion` declaration, document the change when appropriate, and run `make check`. After the change reaches `main`, the repository owner publishes it with `make publish BOOK=<slug>` from the authorized logo-bearing workspace; do not bypass release flags or overwrite release assets.

See [docs/developer-workflow.md](docs/developer-workflow.md) for supported development, review, CI, and release commands.
