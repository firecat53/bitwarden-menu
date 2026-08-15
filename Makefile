VENV = .venv
PYTHON = $(VENV)/bin/python
PIP = $(VENV)/bin/pip

all: venv

$(VENV)/bin/activate: pyproject.toml
	python3 -m venv $(VENV)
	$(PIP) install -U pip wheel
	$(PIP) install '.[autotype,test]'

venv: $(VENV)/bin/activate

run: venv
	$(VENV)/bin/bwm

clean:
	rm -rf __pycache__
	rm -rf $(VENV)
	rm -rf .pytest_cache
	rm -rf .coverage
	rm -rf htmlcov
	rm -rf *.egg-info

man: bwm.1.md
	pandoc bwm.1.md -s -t man -o bwm.1

test: venv
	$(VENV)/bin/pytest

test-cov: venv
	$(VENV)/bin/pytest --cov=bwm --cov-report=html --cov-report=term-missing

# Print the version recorded in bwm/__init__.py
version:
	@grep -Po '^__version__ = "\K[^"]+' bwm/__init__.py

# Bump __version__, refresh the man page footer/date, commit, and create an
# annotated tag. $EDITOR prefilled with version and commits since the last tag.
# Tags are v-prefixed (v0.5.4), so pass VERSION without the leading v.
# Usage: make release VERSION=0.5.4
release:
	@test -n "$(VERSION)" || { echo "Usage: make release VERSION=x.y.z"; exit 1; }
	@echo "$(VERSION)" | grep -Pq '^\d+\.\d+\.\d+$$' || \
		{ echo "VERSION must be x.y.z, with no leading v"; exit 1; }
	@command -v pandoc >/dev/null || \
		{ echo "pandoc is required to regenerate the man page"; exit 1; }
	@test -z "$$(git status --porcelain -uno)" || \
		{ echo "Tracked files have uncommitted changes; commit or stash first"; exit 1; }
	@git rev-parse -q --verify refs/tags/v$(VERSION) >/dev/null && \
		{ echo "Tag v$(VERSION) already exists"; exit 1; } || true
	sed -i 's/^__version__ = ".*"$$/__version__ = "$(VERSION)"/' bwm/__init__.py
	sed -i -e 's/^footer: Bitwarden-menu .*/footer: Bitwarden-menu v$(VERSION)/' \
		-e "s/^date: .*/date: $$(date '+%Y-%m-%d')/" bwm.1.md
	$(MAKE) man
	@test "$$($(MAKE) -s version)" = "$(VERSION)" || \
		{ echo "Failed to set version"; exit 1; }
	git commit -m "Bump version to $(VERSION)" \
		bwm/__init__.py bwm.1.md bwm.1
	# Open the tag message prefilled with the version as the subject and one
	# bullet per commit since the last tag.
	@notes=$$(mktemp); \
	prev=$$(git describe --tags --abbrev=0 2>/dev/null); \
	{ echo "v$(VERSION)"; echo; \
	  git log --no-merges --invert-grep \
		--grep='^Bump version to ' --format='* %s' \
		$${prev:+$$prev..}HEAD; } > $$notes; \
	git tag -a -e -F $$notes v$(VERSION); status=$$?; \
	rm -f $$notes; \
	test $$status -eq 0 || exit $$status; \
	test -n "$$(git for-each-ref --format='%(contents:body)' \
		refs/tags/v$(VERSION))" || { \
		git tag -d v$(VERSION) >/dev/null; \
		echo "Tag message body is empty, so the release notes would be too."; \
		echo "Tag not created. The version bump commit is still there;"; \
		echo "undo it with: git reset --hard HEAD^"; \
		exit 1; }
	@echo
	@echo "Tagged v$(VERSION). Push with:"
	@echo "    git push origin $$(git rev-parse --abbrev-ref HEAD) --follow-tags"

.PHONY: all venv run clean test test-cov man version release
