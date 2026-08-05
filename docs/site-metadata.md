# Site metadata

`books.yml` is the single source of repository and site publication metadata. `make site` selects normalized `site: true` books and writes committed `site/_data/books.yml`; `make site-check` fails if that output is stale.

Publishing a book on the site requires `build: true`, `site: true`, and a matching `site/books/<slug>.md` narrative. After changing those sources, run `make site` and the repository checks. Manifest validation rejects `site: true` with `build: false`.

The Pages job downloads the build artifacts but stages PDFs only for `site: true` books as `pdf/<slug>.pdf`. Artifacts for registered `build: true`, `site: false` books are ignored. Book-page presentation rules live in `site/assets/site.css`; edit that stylesheet when changing the shared book layout appearance or responsive behavior.

The index and common book layout consume generated canonical titles, compact-title fallbacks, machine statuses, display labels, and manifest order. `site/books/<slug>.md` files contain only their join slug and hand-written narrative prose; generation validates but never rewrites them.

Status labels and the `short_title` fallback are defined once in the generator. See `docs/metadata-architecture.md` for the field audit, ownership rules, validation policy, and update workflow.
