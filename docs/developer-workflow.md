# Developer workflow

This guide describes ordinary repository operations. [ARCHITECTURE.md](../ARCHITECTURE.md) remains authoritative for structure and metadata ownership.

## Development

Start from `main` on an isolated task branch. Run `make doctor`, make a focused change, and build the affected book with `make book BOOK=<slug>`. Run `make check` before review; use `make check-strict` for typography-sensitive work. Generated build files stay under the ignored `build/` directory; release staging uses an automatically cleaned temporary directory.

Use Make targets as the public interface: `make test`, `make manifest-check`, `make book BOOK=<slug>`, `make all`, `make check`, `make check-strict`, `make site`, `make site-check`. Run `python3 scripts/repository-report.py` for an informational health report.

Bulk builds run enabled books in a bounded worker pool and report every failed slug after all targets finish. Set `BOOK_BUILD_JOBS` to a positive integer to cap concurrency, for example `BOOK_BUILD_JOBS=2 make all`; an invalid or explicitly empty value is an error. Without an override, the runner uses the detected CPU count capped at four, falling back to two when detection is unavailable. When a book finishes, its captured console output is printed as one block and the freed slot starts the next book, while persistent LaTeX output remains under `build/<slug>/`.

Do not normally call `build-book.sh`, `build-all.sh`, `check.sh`, `books.py add`, or `generate-site-data.py` directly. They are implementation layers used by Make targets and automation. Maintainers may call read-only query/check commands such as `scripts/books.py list`, `scripts/books.py version`, `scripts/check-architecture.py`, and `scripts/check-log.py` when debugging their specific output.

## Review

Review for scope, mathematical correctness, source rights, metadata ownership, and accidental generated files. Confirm every new chapter and section is included, labels use the book prefix, bibliography keys are unique, and frontmatter remains a thin customization wrapper. Pull requests state affected books, validation commands, unresolved pre-existing warnings, and unavailable local-only assets.

## CI

The development container and GitHub Actions textbook builds, including strict pull-request builds, use `ghcr.io/sihyeon8240/latex:sha-c8bbcc1`. Official release PDFs are built locally as described below; the tag workflow does not compile them. The image is built from `.devcontainer/Dockerfile`; the tag is immutable and the GHCR package must remain public so local Dev Containers can pull it without credentials. To update the toolchain, choose a new date-versioned `RELEASE_TAG`, publish it by dispatching `build-image.yml` from the task branch, verify that the package is public, then update the pinned image reference in `.devcontainer/devcontainer.json` and `.github/workflows/build.yml` as well as the documented reference here before merge. A later main-branch run detects the existing immutable tag and does not overwrite it. `scripts/check-image-tag.sh` distinguishes Dockerfile/environment-script changes from workflow-only maintenance: an existing tag fails only when an actual image input changed, while workflow-only pushes and manual dispatches succeed without overwriting it. Never store a registry token in the repository.

GitHub Actions remain on reviewed major tags and are updated by the existing Dependabot configuration. Full action commit-SHA pinning was considered but is not adopted here because it would add a second manual pin-update system; maintainers should revisit this if policy requires every third-party action to be content-addressed.


Source checks validate the manifest, site data, architecture, assembly targets, orphan files, metadata declarations, bibliography integrity, label policy, template wrappers, Python syntax, and tracked generated files. README and descriptive metadata drift is advisory. On pushes and pull requests, `scripts/affected-books.py` selects changed book-local inputs and consumers of changed shared TeX dependencies; ambiguous build inputs fall back to all `build: true` books. The matrix compiles only that set through LuaLaTeX/`latexmk` and applies the strict log check, so no second all-book strict build runs. Extend the existing repository checker for new source rules; do not edit workflows merely to add one.

### Development PDF publication

Only the single publish job on a successful `main` build has `contents: write`. It downloads the affected matrix artifacts, checks out (or initializes) `generated-pdfs`, replaces only those `pdf/<slug>.pdf` files, verifies every `site: true` PDF exists, and pushes one ordinary commit. The branch stores the covered source commit in `.source-sha`. Each main run computes its matrix from that commit rather than only the immediately preceding push, so replacement of a pending concurrency run cannot omit an intermediate change. A publish step re-fetches `main` and exits without writing if its source is stale; serialized publishers therefore cannot overwrite a newer snapshot. PRs and fork PRs cannot publish. Ordinary commits were chosen instead of force-pushed one-commit history to remain compatible with branch protection and avoid destructive recovery semantics. Binary history can be pruned later as an explicit maintenance operation if repository size warrants it.

The first snapshot is bootstrapped by manually dispatching **Build textbooks**. Manual dispatch deliberately selects every `build: true` book, so the publish job can create `generated-pdfs` and verify the complete site set. Pages manual dispatch requires that branch to exist. Later site-only pushes create an empty PDF matrix, advance the snapshot source marker, and deploy Pages with the existing validated PDFs. Pages is invoked only when the planner reports a site change or at least one PDF was rebuilt; documentation-only and other Pages-irrelevant changes do not invoke it. The snapshot keeps only current `site: true` PDFs. Delete `.source-sha` or manually dispatch Build textbooks on `main` to force a safe full rebuild; the latter is also the initial bootstrap procedure.

## Releases

Update the book's single semantic `\bookversion` in `metadata.tex` and run `make check`. From a clean `main` workspace containing the authorized institutional logo, run `make publish BOOK=<slug>`. The individual tag is `<slug>-v<version>` and must match metadata. Release happens only after the reviewed commit is merged and pushed. The local command fetches `origin/main`, requires exact equality with local `HEAD`, and never pushes source code. It requires `release: true`, builds and packages in a temporary directory with strict checks, creates and pushes an annotated tag, waits with a timeout for the corresponding successful Actions run, then uploads the locally built PDF and checksum without overwriting assets. CI does not build or attach release PDFs. The repository owner performs final publication, review, and merge.

## Bug fixes and content writing

For a bug, reproduce it with the smallest relevant build or checker, correct only the owning file, add a regression test when tooling failed to detect it, then run the focused build and `make check`. For content writing, work in one book and section, preserve notation and labels, verify sources and rights, build frequently, and avoid combining exposition with infrastructure changes.

## New contributors

Begin with the root README, [CONTRIBUTING.md](../CONTRIBUTING.md), and [ARCHITECTURE.md](../ARCHITECTURE.md). Choose a bounded issue, keep work on a task branch, use public Make commands, and ask before changing shared interfaces. `python3 scripts/book-doctor.py <slug>` offers advisory local diagnostics; it does not replace `make check`.
