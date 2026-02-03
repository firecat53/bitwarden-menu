VENV = venv
PYTHON = $(VENV)/bin/python
PIP = $(VENV)/bin/pip

all: venv

$(VENV)/bin/activate: requirements.txt
	python3 -m venv $(VENV)
	$(PIP) install -U pip wheel
	$(PIP) install .[test]

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

.PHONY: all venv run clean test test-cov
