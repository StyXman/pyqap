all: test lint mypy

lint:
	time pylint pyqap.py

mypy:
	time mypy pyqap.py

test:
	time ./pyqap.py test -v
