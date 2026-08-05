PYTHON ?= python3
BOOK ?=

.PHONY: manifest-check test book all readme readme-check site site-check clean check check-strict publish doctor tree

manifest-check:
	@$(PYTHON) scripts/books.py validate

test:
	@$(PYTHON) -m unittest discover -s tests -p 'test_*.py' -v

book: manifest-check
	@test -n "$(BOOK)" || \
		(echo "error: BOOK is required (example: make book BOOK=linear-algebra)" >&2; exit 2)
	@./scripts/build-book.sh "$(BOOK)"

all: manifest-check
	@./scripts/build-all.sh

readme: manifest-check
	@$(PYTHON) scripts/generate-readme-books.py

readme-check: manifest-check
	@$(PYTHON) scripts/generate-readme-books.py --check

site: manifest-check
	@$(PYTHON) scripts/generate-site-data.py

site-check: manifest-check
	@$(PYTHON) scripts/generate-site-data.py --check

clean:
	@./scripts/clean.sh

check: manifest-check
	@./scripts/check.sh

check-strict: manifest-check
	@env CHECK_LOG_STRICT=1 ./scripts/check.sh

publish:
	@test -n "$(BOOK)" || \
		(echo "error: BOOK is required (example: make publish BOOK=mathematical-analysis)" >&2; exit 2)
	@./scripts/publish-release.sh "$(BOOK)"

doctor:
	@./scripts/check-environment.sh

TREE_IGNORE ?= vscode-build|build|context.tex|tree.txt|.git|.vscode|__pycache__

tree:
	@rm -f tree.txt
	@tree \
		--dirsfirst \
		-a \
		-I "$(TREE_IGNORE)" \
		> tree.txt
