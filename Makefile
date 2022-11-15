all: mypy test lint

lint:
	time pylint pyqap.py

mypy:
	time mypy pyqap.py

test:
	time ./pyqap.py test

