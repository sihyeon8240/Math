# Undergraduate Mathematics Textbooks

This book-oriented monorepo manages undergraduate mathematics textbooks written in LaTeX as versioned works in progress. Textbook content and repository code use different licenses; see [Licensing and institutional logo](#licensing-and-institutional-logo).

Every book can continue to change and expand. A successful build confirms that the current source compiles, not that its mathematics is complete or free of errors.

## Books

<!-- BEGIN GENERATED BOOKS -->

| Book | Slug | Build command |
|---|---|---|
| Elementary Number Theory | `elementary-number-theory` | `make book BOOK=elementary-number-theory` |
| Linear Algebra | `linear-algebra` | `make book BOOK=linear-algebra` |
| Mathematical Analysis I & II | `mathematical-analysis` | `make book BOOK=mathematical-analysis` |

<!-- END GENERATED BOOKS -->

`books.yml` is the machine-readable central registry. Each book README contains its chapter list, scope notes, and references.

## Quick start

The supported compiler is LuaLaTeX through `latexmk`, with TeX Live 2026 as the official toolchain. Install TeX Live with `latexmk` and `biber`, Python 3 with PyYAML, GNU Make, Bash, ripgrep, Ghostscript, and `tree`, then run:

```sh
make doctor
make book BOOK=linear-algebra
```

VS Code users can instead reopen the repository in its development container. It uses the same immutable GHCR image tag as PDF CI and runs the environment check after creation.

## Main Make commands

- `make test` runs the Python unit-test suite.
- `make doctor` checks required commands, repository structure, and tool versions.
- `make book BOOK=<slug>` builds one registered book, regardless of its `build` flag.
- `make all` builds every book whose manifest `build` flag is `true`. Use `BOOK_BUILD_JOBS=N` to cap its parallel builds; the automatic default is at most four.
- `make readme` regenerates the root README book table from `books.yml`; `make readme-check` fails when it is stale.
- `make site` regenerates committed site metadata from `books.yml`; `make site-check` fails when it is stale.
- `make check` checks repository sources, builds books whose `check` flag is `true`, and validates their LaTeX logs.
- `make check-strict` performs the same checks and additionally fails on overfull boxes.
- `make publish BOOK=<slug>` builds and publishes an official release from an authorized local workspace containing the institutional logo.
- `make clean` removes generated `build/`.

## Generated files

The book table in this README is a committed generated section; edit `books.yml` and run `make readme` instead of editing the table directly.

Development output, including `book.pdf` and the LaTeX log, is written under the ignored `build/<slug>/` directory. Release artifacts are assembled in an automatically cleaned temporary directory.

A release version is read from exactly one macro in the book metadata:

```tex
\newcommand{\bookversion}{0.1.0}
```

The accepted value is `MAJOR.MINOR.PATCH`, optionally followed by a SemVer-style prerelease suffix. Release assets are immutable and are never overwritten by the publish command.

## Repository structure

- `books/<slug>/`: one registered textbook, with `book.tex` as its entry point
- `common/styles/`: shared LaTeX styles
- `common/templates/`: starter files used by `scripts/new-book.sh`
- `common/bibliography/`: shared bibliography entries
- `scripts/`: manifest, build, check, packaging, and release tools
- `.github/workflows/`: source checks, builds, Pages, and tagged releases
- `site/`: static download-page source
- `build/`: ignored development output

A directory under `books/` is not a managed textbook unless it is registered in `books.yml`. Explicit `make book` commands also require registration.

## Book status and manifest flags

Statuses describe publication state:

- `draft`: being written and not an official distribution
- `review`: planned material is largely present but under review and correction
- `published`: an official versioned PDF is public
- `archived`: no longer actively maintained

`published` does not mean writing has ended permanently.

The `build`, `check`, `release`, and `site` flags control participation in bulk automation or publication: respectively the all-books build, repository-wide check, official release eligibility, and site publication. A book with `site: true` must also have `build: true`. They do not disable an explicit build for a registered slug. Thus `make book BOOK=x` may run when the build flag is `false`, while `make publish` requires `release: true`.

## Website and PDF releases

On each relevant `main` push, CI uses `scripts/affected-books.py` to build only textbooks whose book-local files or recursively resolved `\input`, `\include`, local `\usepackage`/`\RequirePackage`, and `\bibliography`/`\addbibresource` dependencies changed. Unclassified build inputs, unavailable comparisons, and incompatible manifest schema changes fall back to every `build: true` book. The `generated-pdfs` branch records the last covered main SHA; each run plans the cumulative diff from that SHA, and a stale run refuses to publish after a newer main push. This prevents canceled pending runs from dropping changes. A manual Build textbooks dispatch on `main` forces all books and bootstraps the branch. Successful site PDFs replace fixed-name snapshot files; site-disabled and removed files are pruned. Pull requests never write the branch. GitHub Pages combines site source from the successful source commit with the complete branch snapshot and exposes `site: true` books at stable `/pdf/<slug>.pdf` URLs. A `build: true`, `site: false` book may still have a CI artifact, but it is omitted from Pages. The site book list, titles, status, and order are generated from `books.yml`; individual site pages retain only editorial descriptions. Change status or `site` in the manifest, run `make site`, and commit the generated data. A missing `short_title` falls back to `title`. Repository checks reject stale generated metadata. GitHub Releases are the canonical download location for their official versioned PDFs.

Official release PDFs are built only in an authorized maintainer workspace containing `common/assets/logos/unist-logo.png`; GitHub Actions never builds or uploads release PDFs. To publish an individual book, run:

```sh
make publish BOOK=mathematical-analysis
```

The command fetches `origin/main` and requires local `HEAD` to match it exactly; it never pushes source code. It validates the logo, clean tree, branch, manifest, release eligibility, and version; builds and packages the PDF with strict log checks in a temporary directory; creates and pushes an annotated `<slug>-v<bookversion>` tag; waits with a timeout for the corresponding GitHub Actions run to succeed; and uploads the PDF and checksum without replacing existing assets. GitHub Actions stops after creating the empty Release, so its assets can only come from the authorized local build. See [CONTRIBUTING.md](CONTRIBUTING.md#releases) for maintenance details.

## Contributing

Report typos, mathematical errors, missing citations, and build failures in a GitHub Issue with the book and source location. Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request. New textbooks can be scaffolded and registered with `scripts/new-book.sh <slug> "<title>"`; the underlying `books.py add` command only registers an already-created book directory.

## Licensing and institutional logo

Textbook content remains under the terms recorded in [LICENSE-CONTENT](LICENSE-CONTENT), currently CC BY-NC-SA 4.0. Repository code and automation are under the [MIT License](LICENSE-CODE), including `scripts/`, the `Makefile`, repository-authored build, validation, distribution and release automation, repository-authored workflow and development-environment configuration, and `common/styles/`. This does not apply MIT to textbook content, the institutional logo, trademarks, or third-party material. External dependencies remain under their own licenses.

Third-party names, trademarks, and the institutional logo are outside both repository licenses. `common/assets/logos/unist-logo.png` is deliberately ignored and is not part of the GitHub repository or ordinary source distributions. The title pages include it only when that exact file exists, using `\includeconditionalgraphics`; ordinary local and CI builds therefore succeed without it. The repository owner may place an authorized copy at that path in a local workspace and use `make publish BOOK=<slug>` to build and upload the logo-bearing PDF. The repository has no workflow that downloads it or reconstructs it from a secret, and the build does not bypass the conditional inclusion logic.

Detailed writing conventions are in [docs/writing-guide.md](docs/writing-guide.md).

## Maintainer documentation

The stable contract is documented in [ARCHITECTURE.md](ARCHITECTURE.md). Its rationale, workflows, maintenance checklists, and incremental roadmap live under [`docs/`](docs/developer-workflow.md); these documents cross-reference the canonical policy rather than redefining it.
