.PHONY: data build test all

data:
	python scripts/download_public_data.py

build:
	python scripts/build_studies.py
	python scripts/build_gallery.py

test:
	python -m pytest -q

all: data build test
