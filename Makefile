.PHONY: install-dev test build check clean

VENV ?= .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

install-dev:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements-dev.txt
	$(PIP) install --editable .

test:
	$(PYTHON) -m pytest -q

check: test
	$(PYTHON) -m skillcheck.cli lint examples/hello-skill --strict
	$(PYTHON) -m skillcheck.cli test examples/hello-skill --strict

build:
	$(PYTHON) -m build
	$(PYTHON) -m twine check dist/*

clean:
	$(PYTHON) -c "from pathlib import Path; import shutil; [shutil.rmtree(p) for p in (Path('build'), Path('dist')) if p.exists()]"
